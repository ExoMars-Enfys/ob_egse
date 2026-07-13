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
        """Class constructor - just save the info."""

        self.table = relative_movements.copy()
        self.before_table = before_table
        self.after_table = after_table

        self.forward = self._calc_positions(relative_movements, 1)
        self.backward = list(reversed(self._calc_positions(relative_movements, -1)))

    def _calc_positions(self, relative_movements, direction):
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

    def range(self, backward=False):
        if backward:
            return (self.backward[0], self.backward[-1])
        else:
            return (self.forward[0], self.forward[-1])

    @staticmethod
    def from_abs_position_list(abs_positions):
        prev = MeasurementTable.LOW
        rel_positions = []
        for pos in sorted(list(set(abs_positions))):
            if pos > MeasurementTable.HIGH:
                raise ValueError(f"Position {pos} is out of range")
            rel_positions.append(pos - prev)
            prev = pos

        return MeasurementTable(rel_positions)

    def __str__(self):
        return str(self.table)


def nyquist_range(
    nyquist_factor, 
    start_wavelength,
    wavelength_to_motor_steps,
    end_motor_steps=9960,
    filter_bandwidth=0.01,
):
    steps = []
    while True:
        ms = round(wavelength_to_motor_steps(start_wavelength))
        if ms > end_motor_steps:
            break
        steps.append(ms)
        start_wavelength += start_wavelength*(filter_bandwidth/nyquist_factor)
    return steps

def swir_nyquist_range(
    nyquist_factor, 
    start_wavelength = 900,
    end_wavelength = 1650,
):
    return nyquist_range(
        nyquist_factor, 
        start_wavelength,
        wavelength_to_motor_steps = lambda w: (w - 614.2)/0.1211
    )

def mwir_nyquist_range(
    nyquist_factor, 
    start_wavelength = 1650,
    end_wavelength = 2500,
):
    return nyquist_range(
        nyquist_factor, 
        start_wavelength,
        end_wavelength,
        wavelength_to_motor_steps = lambda w: (w - 1084.1)/0.2224
    )

mwir_binary_chop_check = list(range(7990, 8011, 2))

dark0 = MeasurementTable.from_abs_position_list(
    range(1250, 1450, 20)
)

dark1 = MeasurementTable.from_abs_position_list(
        list(range(9100, 9301, 20)) + # Edge of SWIR
        list(range(9940, 9961, 2))    # SWIR BC
)

# Some example tables. The first two are the reserved dark "low" and
# "high" end tables.
predefined = [
    # Dark table 0: Fine resolution to capture the low edge in SWIR.
    dark0.table,

    # Dark table 1: Fine resolution to capture the high edge in SWIR,
    # along with a chunk at the end to capture SWIR BC.
    dark1.table,

    # Measurement table 2: End of DT0 thru start of DT1 in steps of 2
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 2))
    ).table,

    # Measurement table 3: End of DT0 thru start of DT1 in steps of
    # 3, with extra resolution around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 3)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 4: End of DT0 thru start of DT1 in steps of
    # 4, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 4)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 5: End of DT0 thru start of DT1 in steps of
    # 5, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 5)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 6: End of DT0 thru start of DT1 in steps of
    # 6, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 6)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 7: End of DT0 thru start of DT1 in steps of
    # 7, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 7)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 8: End of DT0 thru start of DT1 in steps of
    # 8, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 8)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 9: End of DT0 thru start of DT1 in steps of
    # 9, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 9)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 10: End of DT0 thru start of DT1 in steps of
    # 10, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 10)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 11: End of DT0 thru start of DT1 in steps of
    # 20, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 20)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 12: End of DT0 thru start of DT1 in steps of
    # 30, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 30)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 13: End of DT0 thru start of DT1 in steps of
    # 40, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 40)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 14: End of DT0 thru start of DT1 in steps of
    # 50, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 50)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 15: End of DT0 thru start of DT1 in steps of
    # 60, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 60)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 16: End of DT0 thru start of DT1 in steps of
    # 70, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 70)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 17: End of DT0 thru start of DT1 in steps of
    # 80, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 80)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 18: End of DT0 thru start of DT1 in steps of
    # 90, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 90)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 19: End of DT0 thru start of DT1 in steps of
    # 100, with an extra bit around MWIR BC location.
    MeasurementTable.from_abs_position_list(
        list(range(dark0.range()[1], dark1.range()[0], 100)) + 
        mwir_binary_chop_check 
    ).table,

    # Measurement table 20: Nyquist spacing with bandwidth 1% and 
    # factor 2.3 using SW wavelengths.
    MeasurementTable.from_abs_position_list(
        swir_nyquist_range(2.3) + 
        mwir_binary_chop_check
    ).table
]

if __name__ == '__main__':
    table = 20
    m = MeasurementTable(predefined[table],
            before_table=MeasurementTable(predefined[0]), 
            after_table=MeasurementTable(predefined[1])
    )
    print(f"Measurement table {table}")
    print(f"Length: {len(m.table)}")
    print(f"Table: {m.table}")
    print(f"Forward range: {m.range()}")
    print(f"Backward range: {m.range(backward=True)}")
