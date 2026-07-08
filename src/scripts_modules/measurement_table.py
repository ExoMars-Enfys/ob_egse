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
            end = len(self.table)-1

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
            yield (table[table_pos]-prev, table[table_pos])
            prev = table[table_pos]
            if table_pos == table_end:
                break
            table_pos += step

        if self.after_table is not None:
            for relative_pos, abs_pos in self.after_table.scan(start_motor_steps=prev):
                yield (relative_pos, abs_pos)
                prev = abs_pos

# Some example tables. The first two are the reserved dark "low" and
# "high" end tables.
predefined = [
    # Dark table 0: 11 points from 1600-1700
    # to capture the low edge in SWIR.
    [
        600, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10
    ],

    # Dark table 1: captures points at the top edge of
    # SWIR and around the two binary chop locations.
    [
        6990, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,           # 11 points from 7990-8010
        1690, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, # 11 points from 9700-9800
        140, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,            # 11 points from 9940-9960
    ],

    # The entire range in intervals of 5 motor steps.
    [0] + [5]*(8960//5),

    # The entire range in intervals of 20 motor steps.
    [0] + [20]*(8960//20),

    # The entire range in intervals of 30 motor steps.
    [0] + [30]*(8960//30),
]

if __name__ == '__main__':

    m = MeasurementTable(predefined[4],
            before_table=MeasurementTable(predefined[0]), 
            after_table=MeasurementTable(predefined[1])
    )
    for rel, abs_pos in m.scan():
        print(f"Relative {rel} steps, position is now {abs_pos}")
