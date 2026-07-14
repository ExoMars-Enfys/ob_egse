"""
Measurement tables, being potentially made up of two "dark" tables
and a "science" table, are complicated. There's the possibility for
overlap and, since they use relative positiions, rather than absolute,
driving the tables backwards can give completely different results
from driving them forwards. It's possible that the combination of dark
and measurement tables could cause overlap, and it's not completely
clear how this would be handled - would it cause backtracking, or is
the combined table sorted in absolute position (or reverse absolute
position) order?

The current implementation assumes that dark tables are iterated
independently of the measurement tables, and so will generate backward
movements when overlap happens.
"""

class MeasurementTable:
    """An encapsulation of how the EB does measurement tables.

    The constructor takes a list of relative movements, in the form that Ben
    has described (first move is relative to 1000, or 9960 if the table is
    being run in reverse).

    Optionally, you can hand it two more tables, dark0 and dark1, which will
    be (non-recursively) pasted onto the front and back of the current table
    when scan is called.
    """

    LOW = 1000
    HIGH = 9960

    def __init__(self, relative_movements, before_table=None, after_table=None):
        """Class constructor

        We take a list of relative movements and construct two tables: a
        forward table of absolute positions, based at 1000, and a suimilar
        backward table based at 9960. It's easier to work in absolute
        numbers and back-convert to relative movements during scanning.

        Optionally, two "dark" tables can be specified and, during scanning,
        these will be merged with the current table.
        """

        self.table = relative_movements.copy()
        self.before_table = before_table
        self.after_table = after_table

        self.forward = self._calc_positions(relative_movements, 1)
        self.backward = list(reversed(self._calc_positions(relative_movements, -1)))

    @classmethod
    def from_abs_position_list(cls, abs_positions, before_table=None, after_table=None):
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
        """

        prev = MeasurementTable.LOW
        rel_positions = []
        for pos in sorted(list(set(abs_positions))):
            if pos > MeasurementTable.HIGH:
                raise ValueError(f"Position {pos} is out of range")
            rel_positions.append(pos - prev)
            prev = pos

        return cls(rel_positions, before_table, after_table)

    @classmethod
    def regular_steps_between(cls, before_table, after_table, step_size, extra_positions=[]):
        """Alternative constructor.

        Quite a lot of our predefined tables are of the form "between dark0
        dark0 and dark1 in regular intervals". Let's have a helper function which
        implements that.
        """

        return cls.from_abs_position_list(
            list(range(before_table.forward[-1], after_table.forward[0]+1,
                step_size)) + extra_positions,
            before_table = before_table,
            after_table = after_table
        )

    @classmethod
    def nyquist_steps_between(cls,
        before_table, after_table, nyquist_factor,
        motor_steps_to_wavelength,
        filter_bandwidth=0.01,
        extra_positions=[]
    ):
        """Alternative constructor.

        This one generates steps between before_table and after_table in
        steps that are determined by the specified LVF bandwidth, the
        over-sampling factor (nyquist_factor) and a calibrated function
        for getting from motor steps to wavelength.
        """

        positions = []

        position = before_table.forward[-1]
        positions.append(position)
        next_wavelength = motor_steps_to_wavelength(position)*(1+filter_bandwidth/nyquist_factor)
        while position <= after_table.forward[0]:
            wavelength = motor_steps_to_wavelength(position)
            if wavelength >= next_wavelength:
                positions.append(position)
                next_wavelength = wavelength*(1+filter_bandwidth/nyquist_factor)
            position += 1
        return cls.from_abs_position_list(
            positions + extra_positions,
            before_table=before_table,
            after_table=after_table
        )


    def scan(self, start=None, end=None, start_motor_steps=LOW):
        """Run through the table, yielding resulting movements and positions.

        If dark0/dark1 are present, these will be iterated before, and after
        the current table respectively.

        If start and/or end is supplied, iteration over this table (not
        darks) will only cover the specified range of positions.  Calculated
        positions will, however, be calculated from the relevant starting
        point. If end is lower than start, a reverse traversal is assumed.

        Darks are always traversed in full, in a forward directiob.

        start_motor_steps, if supplied, supplies the absolute motor
        steps position at the start of traversal, for relative movement
        calculation. If not supplied, this assumes LOW, the outer endstop.

        The function yields a tuple containing the relative movement and
        resulting absolute position.
        """

        if start is None:
            start = 0

        if end is None:
            end = len(self.table) - 1

        if end < 0 or end >= len(self.table) or start < 0 or start >= len(self.table):
            raise RuntimeError("Table start/end is out of range")

        prev = start_motor_steps

        if self.before_table is not None:
            for relative_pos, abs_pos in self.before_table.scan(start_motor_steps=prev):
                yield (relative_pos, abs_pos)
                prev = abs_pos

        if end < start:
            table = self.backward
            table_pos = start
            table_end = end
            step = -1
        else:
            table = self.forward
            table_pos = start
            table_end = end
            step = 1

        while True:
            yield (table[table_pos] - prev, table[table_pos])
            prev = table[table_pos]
            if table_pos == table_end:
                break
            table_pos += step

        if self.after_table is not None:
            for relative_pos, abs_pos in self.after_table.scan(start_motor_steps=prev):
                yield (relative_pos, abs_pos)
                prev = abs_pos

    def _calc_positions(self, relative_movements, direction):
        """
        Given a set of relative movements, return a forward or backward
        absolute position list.
        """
        table = []
        if direction < 0:
            abs_pos = self.HIGH
            for entry in reversed(relative_movements):
                abs_pos -= entry
                table.append(abs_pos)
        else:
            abs_pos = self.LOW
            for entry in relative_movements:
                abs_pos += entry
                table.append(abs_pos)
        return table

    def __str__(self):
        """
        Print the table as a list of relative movements.
        """
        return str(self.table)

# The section below generates a list of predefined measurement tables that
# we expect to be present on the instrument. If you run the module as a
# script, it will report the total number of tables and points within them,
# and it you supply a table number, it will give information about that
# predefined table.
#
# When this file is imported as a module, you can access our nominal
# measurement table list as the "predefined" list below.

# We'll give these three special names as they're used in constructing
# other tables.
_dark0 = MeasurementTable.from_abs_position_list(
    range(1100, 1350, 40)        # Edge of SWIR
)

_dark1 = MeasurementTable.from_abs_position_list(
    list(range(9100, 9301, 40))  # Edge of SWIR
    + [9600]                     # SWIR BC
)

# 21 points around the MWIR binary chop location.
_mwir_binary_chop_check = list(range(7990, 8011, 2))

# Some example tables. The first two are the reserved dark "low" and
# "high" end tables.
#
# N.B. These are *NOT* MeasurementTable objects. They are the lists of
# relative steps that would be used to create tables. MeasurementTable
# is used to construct them, but we then extract its "table" attribute
# when building the list. This is because the lists below are actually
# merged with the predefined dark tables inside the EGSE, and because
# this list is the form we'd expect to give to Ben.
predefined = [
    # Dark table 0: Fine resolution to capture the low edge in SWIR.
    _dark0.table,

    # Dark table 1: Fine resolution to capture the high edge in SWIR,
    # along with a chunk at the end to capture SWIR BC.
    _dark1.table,

    # Measurement table 2: End of DT0 thru start of DT1 in steps of 2
    MeasurementTable.regular_steps_between(_dark0, _dark1, 2).table,

    # Measurement table 3: End of DT0 thru start of DT1 in steps of
    # 3, with extra resolution around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 3, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 4: End of DT0 thru start of DT1 in steps of
    # 4, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 4, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 5: End of DT0 thru start of DT1 in steps of
    # 5, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 5, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 6: End of DT0 thru start of DT1 in steps of
    # 6, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 6, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 7: End of DT0 thru start of DT1 in steps of
    # 7, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 7, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 8: End of DT0 thru start of DT1 in steps of
    # 8, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 8, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 9: End of DT0 thru start of DT1 in steps of
    # 9, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 9, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 10: End of DT0 thru start of DT1 in steps of
    # 10, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 10, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 11: End of DT0 thru start of DT1 in steps of
    # 20, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 20, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 12: End of DT0 thru start of DT1 in steps of
    # 30, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 30, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 13: End of DT0 thru start of DT1 in steps of
    # 40, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 40, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 14: End of DT0 thru start of DT1 in steps of
    # 50, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 50, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 15: End of DT0 thru start of DT1 in steps of
    # 60, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 60, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 16: End of DT0 thru start of DT1 in steps of
    # 70, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 70, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 17: End of DT0 thru start of DT1 in steps of
    # 80, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 80, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 18: End of DT0 thru start of DT1 in steps of
    # 90, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 90, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 19: End of DT0 thru start of DT1 in steps of
    # 100, with an extra bit around MWIR BC location.
    MeasurementTable.regular_steps_between(
        _dark0, _dark1, 100, extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 20: Nyquist spacing with bandwidth 1% and
    # factor 2.3 using SWIR wavelengths.
    MeasurementTable.nyquist_steps_between(_dark0, _dark1,
        2.3,
        motor_steps_to_wavelength = lambda ms: 0.1225*ms + 664.6,
        extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 21: Nyquist spacing with bandwidth 1% and
    # factor 2.3 using MWIR wavelengths.
    MeasurementTable.nyquist_steps_between(_dark0, _dark1,
        2.3,
        motor_steps_to_wavelength = lambda ms: 0.2228*ms + 1174.8,
        extra_positions = _mwir_binary_chop_check
    ).table,

    # Measurement table 22: Nyquist spacing as determined by Matt
    # (email 2026-07-13)
    #
    # Starting point of 1922 equates to 900nm in SWIR.
    MeasurementTable.from_abs_position_list([x + 1922 for x in [
            0, 37, 74, 111, 149, 186, 223, 261, 298, 336, 373, 411, 448, 486,
            523, 561, 598, 636, 674, 711, 749, 787, 825, 863, 900, 938, 976,
            1014, 1052, 1090, 1128, 1167, 1205, 1243, 1281, 1320, 1358, 1396,
            1435, 1473, 1512, 1550, 1589, 1628, 1666, 1705, 1744, 1783, 1822,
            1861, 1900, 1939, 1978, 2017, 2056, 2096, 2135, 2174, 2214, 2253,
            2293, 2333, 2373, 2412, 2452, 2492, 2532, 2573, 2613, 2653, 2693,
            2734, 2774, 2815, 2856, 2896, 2937, 2978, 3019, 3060, 3102, 3143,
            3184, 3226, 3267, 3309, 3351, 3393, 3435, 3477, 3519, 3562, 3604,
            3647, 3689, 3732, 3775, 3818, 3861, 3905, 3948, 3992, 4035, 4079,
            4123, 4167, 4212, 4256, 4301, 4345, 4390, 4435, 4480, 4526, 4571,
            4617, 4663, 4709, 4755, 4801, 4848, 4894, 4941, 4988, 5036, 5083,
            5131, 5178, 5227, 5275, 5323, 5372, 5421, 5470, 5519, 5569, 5618,
            5667, 5717, 5766, 5816, 5865, 5915, 5965, 6015, 6066, 6116, 6167,
            6217, 6268, 6319, 6370, 6422, 6473,
        ]
    ]).table,
]

if __name__ == "__main__":
    import sys

    print(f"Total predefined tables: {len(predefined)}")
    print(f"Total points in predefined tables: {sum([len(t) for t in predefined])}")

    # If a table number is given on the command line, dump info about it.
    # No error checking of the argument is done - give it garbage, you'll
    # get an exception.
    if len(sys.argv) == 2:
        table = int(sys.argv[1])
        m = MeasurementTable(
            predefined[table], before_table=MeasurementTable(predefined[0]), after_table=MeasurementTable(predefined[1])
        )
        print(f"Measurement table {table}")
        print(f"Length: {len(m.table)}")
        print(f"Positions: {m.forward}")
        print(f"Movements: {m.table}")
