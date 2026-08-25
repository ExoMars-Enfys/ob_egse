"""
Measurement tables, being potentially made up of two "dark" tables
and a "science" table, are complicated. There's the possibility for
overlap (with potential reverse movements) and driving the tables
backwards involves handling the dark tables differently. Transitions
between the tables, and table startup, involves changing the initial
move, since that assumes a specific starting location, which may
not be the actual true case.
"""

from itertools import accumulate


class MeasurementTable:
    """An encapsulation of how the EB does measurement tables.

    The constructor takes a list of relative movements, in the form that Ben
    has described (first move is relative to 1000, or 9640 if the table is
    being run in reverse).

    Optionally, you can hand it two more tables, dark0 and dark1, which will
    be iterated as appropriate when scan() is called.
    """

    LOW = 1000
    HIGH = 9640

    def __init__(self, relative_movements, dark0=None, dark1=None, name=None, is_dark_table=False):
        """Class constructor

        We take a list of relative movements, assuming an origin of 1000,
        since that's what a measurement table consists of. For all but the
        most trivial operations, though, it's easier to work in terms of
        absolute positions.

        Optionally, two "dark" tables can be specified and, during scanning,
        these will be merged with the current table.
        """

        # No backward movements.
        if min(relative_movements) < 0:
            raise ValueError("Relative movements list must not contain negative moves")

        # No recursion. I'm not sure this restriction is actually required,
        # in terms of this class. But in terms of what the instrument needs,
        # it's sensible to ban it.
        if is_dark_table and (dark0 is not None or dark1 is not None):
            raise ValueError("Dark tables must not themselves have dark tables")

        # Save options.
        self.dark0 = dark0
        self.dark1 = dark1
        self.name = name

        # Dark tables are special, since they don't have "bookend" readings
        # like normal measurement tables do. So we need to remember that
        # we're handling a dark table.
        self.is_dark_table = is_dark_table

        # Store the list we've been given.
        self._table = relative_movements.copy()

        # Get the end positions.
        end = self.absolute_table[-1]

        # Can't go beyond the bounds in either case.
        if end > self.HIGH:
            raise ValueError("Relative movements exceed the full range")

        # If it's not a dark table, the relative movements must
        # exactly cover the range.
        if not is_dark_table and self.absolute_table[-1] != self.HIGH:
            raise ValueError("Relative movements do not span exactly the full range")

    @property
    def absolute_table(self):
        """Return the list of absolute positions resulting from this table.

        Using itertools.accumulate, we can get a list of absolute positions
        from the relative positions in _table. itertools.accumulate, when
        given an initial position, inserts that position into the list. This
        is just what we want for normal tables. Dark tables need it
        stripping off.
        """
        positions = list(accumulate(self._table, initial=self.LOW))
        if self.is_dark_table:
            return positions[1:]
        return positions

    @property
    def relative_table(self):
        """Return the list of relative positions.

        We'll return a copy so that modifications to the relative table
        aren't propagated back into the class.
        """
        return self._table.copy()

    @classmethod
    def from_abs_position_list(cls, abs_positions, dark0=None, dark1=None, name=None, is_dark_table=False):
        """Alternative "constructor".

        For the most part, it's easier for us to give the class a set of
        absolute positions than to calculate the relative steps. So this
        class method handles that.

        N.B. Positions can be supplied in any order, and they are
        sorted and de-duplicated before converting to relative movements.
        This means that you can't specify duplicate positions through
        this constructor. But it does make it very easy to merge pre-defined
        lists (e.g. when doing the "fine grained" bit around the chop
        point).

        Also N.B. If LOW or HIGH is present explicitly these will be
        represented as 0 step movements (only at the low end, for
        dark tables) in the relative table. I've decided this is the
        most sensible way of doing things for this outlier case. In
        practise, to avoid backwards movements, we'll tend to skip the
        first and last items in a normal table. If we actually want those
        points for some reason, having them explicitly present is probably
        less surprising.
        """

        prev = MeasurementTable.LOW
        rel_positions = []
        for pos in sorted(list(set(abs_positions))):
            if pos < MeasurementTable.LOW or pos > MeasurementTable.HIGH:
                raise ValueError(f"Position {pos} is out of range")
            rel_positions.append(pos - prev)
            prev = pos

        # Since self.LOW is implicitly present in a (non-dark-)table, I
        # think it makes sense for self.HIGH to be implicitly added too.
        if not is_dark_table:
            rel_positions.append(MeasurementTable.HIGH - prev)

        return cls(rel_positions, dark0=dark0, dark1=dark1, name=name, is_dark_table=is_dark_table)

    @classmethod
    def regular_steps_between(cls, dark0, dark1, step_size, extra_positions=[], name=None, is_dark_table=False):
        """Alternative constructor.

        Quite a lot of our predefined tables are of the form "between dark0
        and dark1 in regular intervals". Let's have a helper function which
        implements that.
        """

        if name is None:
            name = f"Regular steps, step = {step_size}"

        # Since dark0 contains the start point, the first entry
        # will be step_size away from it. Similarly, we'll stop
        # before the start of dark1, rather than running into it.
        return cls.from_abs_position_list(
            list(range(dark0.absolute_table[-1] + step_size, dark1.absolute_table[0], step_size)) + extra_positions,
            dark0=dark0,
            dark1=dark1,
            name=name,
            is_dark_table=is_dark_table,
        )

    @classmethod
    def nyquist_steps_between(
        cls,
        dark0,
        dark1,
        nyquist_factor,
        motor_steps_to_wavelength,
        filter_bandwidth=0.01,
        extra_positions=[],
        name=None,
        is_dark_table=False,
    ):
        """Alternative constructor.

        This one generates steps between dark0 and dark1 in
        steps that are determined by the specified LVF bandwidth, the
        over-sampling factor (nyquist_factor) and a calibrated function
        for getting from motor steps to wavelength.
        """

        positions = []

        position = dark0.absolute_table[-1]
        next_wavelength = motor_steps_to_wavelength(position) * (1 + filter_bandwidth / nyquist_factor)
        while position < dark1.absolute_table[0]:
            wavelength = motor_steps_to_wavelength(position)
            if wavelength >= next_wavelength:
                positions.append(position)
                next_wavelength = wavelength * (1 + filter_bandwidth / nyquist_factor)
            position += 1
        return cls.from_abs_position_list(
            positions + extra_positions,
            dark0=dark0,
            dark1=dark1,
            name=name,
            is_dark_table=is_dark_table,
        )

    def scan(self, start=None, end=None, start_motor_steps=LOW):
        """Run through the table, yielding movements and positions.

        If dark0/dark1 are present, these will be iterated as needed.

        If start and/or end is supplied, iteration over this table (not
        darks) will only cover the specified range of positions. Calculated
        positions will, however, be calculated from the relevant starting
        point. If end is lower than start, a reverse traversal is assumed.

        Darks are always traversed in full, in the direction and order
        implied by start and end.

        start_motor_steps, if supplied, supplies the absolute motor
        steps position at the start of traversal, for relative movement
        calculation. If not supplied, this assumes LOW, the outer endstop.
        """

        # Get a copy of the table of absolute positions. Since this
        # is a calculated property, it's better to get it once than
        # to calculate it multiple times below.
        abs_table = self.absolute_table

        # No start point specified.
        if start is None:
            start = 0

        # No end point specified.
        if end is None:
            end = len(abs_table) - 1

        # Check the start/end range.
        if end < 0 or end >= len(abs_table) or start < 0 or start >= len(abs_table):
            raise RuntimeError("Table start/end is out of range")

        # We need to keep track of the current positions, so we can
        # calculate the relative movements that are actually needed.
        # When iterating a single table, these will match the initialisation
        # data, but transitions (startup and into/out of darks) need to be
        # calculated.
        prev = start_motor_steps

        if end < start:
            # Reverse order.
            if self.dark1 is not None:
                for pos in reversed(self.dark1.absolute_table):
                    yield pos - prev, pos
                    prev = pos

            for pos in reversed(abs_table[end : start + 1]):
                yield pos - prev, pos
                prev = pos

            if self.dark0 is not None:
                for pos in reversed(self.dark0.absolute_table):
                    yield pos - prev, pos
                    prev = pos
        else:
            # Forward order.
            if self.dark0 is not None:
                for pos in self.dark0.absolute_table:
                    yield pos - prev, pos
                    prev = pos

            for pos in abs_table[start : end + 1]:
                yield pos - prev, pos
                prev = pos

            if self.dark1 is not None:
                for pos in self.dark1.absolute_table:
                    yield pos - prev, pos
                    prev = pos

    def __str__(self):
        """Stringify the table as a list of relative movements."""
        return str(self._table)

    def __len__(self):
        """Return the number of entries in the table.

        As would be seen by the EB - i.e. the number of relative movements.
        """
        return len(self._table)


# The section below generates a list of predefined measurement tables that
# we expect to be present on the instrument. If you run the module as a
# script, it will report the total number of tables and points within them,
# and it you supply a table number, it will give information about that
# predefined table.
#
# When this file is imported as a module, you can access our nominal
# measurement table list as the "predefined" list below.

## We'll give these three special names as they're used in constructing
## other tables.
_dark0 = MeasurementTable.from_abs_position_list(
    range(1040, 1321, 40),  # Edge of SWIR
    name="Dark table 0",
    is_dark_table=True,
)

_dark1 = MeasurementTable.from_abs_position_list(
    list(range(8800, 9321, 40))  # Edge of SWIR
    + [9600],  # SWIR BC
    name="Dark table 1",
    is_dark_table=True,
)

## Force a measurement at MWIR binary chop location.
_mwir_binary_chop_check = [8000]

# Some example tables. The first two are the reserved dark "low" and
# "high" end tables.
predefined = [
    # Dark table 0: Capture the low edge in SWIR.
    _dark0,
    # Dark table 1: Capture the high edge in SWIR, along with a
    # chunk at the end to capture SWIR BC.
    _dark1,
    # Measurement table 2: End of DT0 thru start of DT1 in steps of 2
    MeasurementTable.regular_steps_between(_dark0, _dark1, 2, extra_positions=_mwir_binary_chop_check),
    # Measurement table 3: End of DT0 thru start of DT1 in steps of
    # 3, with extra resolution around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 3, extra_positions=_mwir_binary_chop_check),
    # Measurement table 4: End of DT0 thru start of DT1 in steps of
    # 4, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 4, extra_positions=_mwir_binary_chop_check),
    # Measurement table 5: End of DT0 thru start of DT1 in steps of
    # 5, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 5, extra_positions=_mwir_binary_chop_check),
    # Measurement table 6: End of DT0 thru start of DT1 in steps of
    # 6, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 6, extra_positions=_mwir_binary_chop_check),
    # Measurement table 7: End of DT0 thru start of DT1 in steps of
    # 7, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 7, extra_positions=_mwir_binary_chop_check),
    # Measurement table 8: End of DT0 thru start of DT1 in steps of
    # 8, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 8, extra_positions=_mwir_binary_chop_check),
    # Measurement table 9: End of DT0 thru start of DT1 in steps of
    # 9, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 9, extra_positions=_mwir_binary_chop_check),
    # Measurement table 10: End of DT0 thru start of DT1 in steps of
    # 10, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 10, extra_positions=_mwir_binary_chop_check),
    # Measurement table 11: End of DT0 thru start of DT1 in steps of
    # 20, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 20, extra_positions=_mwir_binary_chop_check),
    # Measurement table 12: End of DT0 thru start of DT1 in steps of
    # 30, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 30, extra_positions=_mwir_binary_chop_check),
    # Measurement table 13: End of DT0 thru start of DT1 in steps of
    # 40, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 40, extra_positions=_mwir_binary_chop_check),
    # Measurement table 14: End of DT0 thru start of DT1 in steps of
    # 50, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 50, extra_positions=_mwir_binary_chop_check),
    # Measurement table 15: End of DT0 thru start of DT1 in steps of
    # 60, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 60, extra_positions=_mwir_binary_chop_check),
    # Measurement table 16: End of DT0 thru start of DT1 in steps of
    # 70, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 70, extra_positions=_mwir_binary_chop_check),
    # Measurement table 17: End of DT0 thru start of DT1 in steps of
    # 80, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 80, extra_positions=_mwir_binary_chop_check),
    # Measurement table 18: End of DT0 thru start of DT1 in steps of
    # 90, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 90, extra_positions=_mwir_binary_chop_check),
    # Measurement table 19: End of DT0 thru start of DT1 in steps of
    # 100, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(_dark0, _dark1, 100, extra_positions=_mwir_binary_chop_check),
    # Measurement table 20: Nyquist spacing with bandwidth 1% and
    # factor 2.3 using SWIR wavelengths.
    MeasurementTable.nyquist_steps_between(
        _dark0,
        _dark1,
        2.3,
        motor_steps_to_wavelength=lambda ms: 0.1225 * ms + 664.6,
        extra_positions=_mwir_binary_chop_check,
        name="Nyquist 2.3 using SWIR wavelengths",
    ),
    # Measurement table 21: Nyquist spacing with bandwidth 1% and
    # factor 2.3 using MWIR wavelengths.
    MeasurementTable.nyquist_steps_between(
        _dark0,
        _dark1,
        2.3,
        motor_steps_to_wavelength=lambda ms: 0.2228 * ms + 1174.8,
        extra_positions=_mwir_binary_chop_check,
        name="Nyquist 2.3 using MWIR wavelengths",
    ),
    # Measurement table 22: Nyquist spacing as determined by Matt
    # (email 2026-07-13)
    #
    # Starting point of 1832 equates to 900nm in SWIR.
    MeasurementTable.from_abs_position_list(
        [
            x + 1832
            for x in [
                0,
                37,
                74,
                111,
                149,
                186,
                223,
                261,
                298,
                336,
                373,
                411,
                448,
                486,
                523,
                561,
                598,
                636,
                674,
                711,
                749,
                787,
                825,
                863,
                900,
                938,
                976,
                1014,
                1052,
                1090,
                1128,
                1167,
                1205,
                1243,
                1281,
                1320,
                1358,
                1396,
                1435,
                1473,
                1512,
                1550,
                1589,
                1628,
                1666,
                1705,
                1744,
                1783,
                1822,
                1861,
                1900,
                1939,
                1978,
                2017,
                2056,
                2096,
                2135,
                2174,
                2214,
                2253,
                2293,
                2333,
                2373,
                2412,
                2452,
                2492,
                2532,
                2573,
                2613,
                2653,
                2693,
                2734,
                2774,
                2815,
                2856,
                2896,
                2937,
                2978,
                3019,
                3060,
                3102,
                3143,
                3184,
                3226,
                3267,
                3309,
                3351,
                3393,
                3435,
                3477,
                3519,
                3562,
                3604,
                3647,
                3689,
                3732,
                3775,
                3818,
                3861,
                3905,
                3948,
                3992,
                4035,
                4079,
                4123,
                4167,
                4212,
                4256,
                4301,
                4345,
                4390,
                4435,
                4480,
                4526,
                4571,
                4617,
                4663,
                4709,
                4755,
                4801,
                4848,
                4894,
                4941,
                4988,
                5036,
                5083,
                5131,
                5178,
                5227,
                5275,
                5323,
                5372,
                5421,
                5470,
                5519,
                5569,
                5618,
                5667,
                5717,
                5766,
                5816,
                5865,
                5915,
                5965,
                6015,
                6066,
                6116,
                6167,
                6217,
                6268,
                6319,
                6370,
                6422,
                6473,
            ]
        ]
        + _mwir_binary_chop_check,
        name="Nyquist spacing from mmg",
    ),
]

if __name__ == "__main__":
    import argparse
    import csv
    import sys

    parser = argparse.ArgumentParser(description="Simple front end to Enfys measurement tables.")
    parser.add_argument("-dump", type=str, default=None, metavar="file.csv", help="Dump all predefined tables as csv.")
    parser.add_argument("-show", type=int, default=None, metavar="table-number", help="Show info about specified table")
    args = parser.parse_args()

    if args.dump is not None and args.show is not None:
        print("-dump and -show are mutually exclusive.", file=sys.stderr)
        sys.exit(1)

    if args.dump is None:
        print(f"Total predefined tables: {len(predefined)}")
        print(f"Total points in predefined tables: {sum([len(t) for t in predefined])}")

    if args.show is not None:
        if args.show < 0 or args.show >= len(predefined):
            print("Requested table number is out of range.", file=sys.stderr)
            sys.exit(1)

        m = MeasurementTable(
            predefined[args.show].relative_table,
            dark0=predefined[0] if not predefined[args.show].is_dark_table else None,
            dark1=predefined[1] if not predefined[args.show].is_dark_table else None,
            name=predefined[args.show].name,
            is_dark_table=predefined[args.show].is_dark_table,
        )
        print(f"Measurement table {args.show}: {m.name}")
        print(f"Length: {len(m)}")
        print(f"Positions: {m.absolute_table}")
        print(f"Movements: {m.relative_table}")
        print(f"Including dt0 and dt1: {[abs_pos for rel, abs_pos in m.scan()]}")

    if args.dump is not None:
        print(f"Dumping table info to {args.dump}")
        try:
            f = open(args.dump, "w")
            writer = csv.writer(f)
            writer.writerow(["Table", "Name", "Relative moves"])
            for n, t in enumerate(predefined):
                writer.writerow([n, t.name] + t.relative_table)
            writer.writerow([])
            writer.writerow(["Table", "Name", "Absolute Positions"])
            for n, t in enumerate(predefined):
                writer.writerow([n, t.name] + t.absolute_table)
            f.close()
        except (PermissionError, IsADirectoryError, OSError) as e:
            print(f"Failed to open {args.dump}: {str(e)}", file=sys.stderr)
            sys.exit(1)
