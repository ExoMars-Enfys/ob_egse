#!/usr/bin/env python3

import sys
import re
import argparse

import crc8
import tm

class EGSEDumpDecoder:
    """
    This class implements an iterator which can be used to decode an EGSE log
    containing timestamps and hex data.
    """

    struct_pattern = None
    struct_names = None
    struct_expected_length = None

    # This list isn't used directly in the class, but we need
    # somewhere sensible to store a default field list for decodes
    # and here seems as good as anywhere.
    default_fields_per_type = {
        tm.SCI: [
            "MOD_ID", "CMD_CNT", "ERROR_BYTE", "MTR_ABS_STEPS", "THRM_STATUS",
            "SWIR_OFFSET", "MWIR_OFFSET", "SCI_ADC_SAMPLES", "SCI_ADC_SKIP",
            "SWIR_HIGH", "SWIR_MED", "SWIR_LOW", "MWIR_HIGH", "MWIR_MED",
            "MWIR_LOW", "HT_SINK_TEMP", "SWIR_TEMP", "CRC"
        ]
    }

    def __init__(self, log_file_name: str):
        """Initialise the iterator.

        Arguments:
        log_file_name -- The name of the EGSE log file to read.
        """

        # Open the hex dump file.
        try:
            self.in_file = open(log_file_name, "r")
        except (FileNotFoundError, PermissionError) as e:
            raise Exception(f"Failed to open file: {e.strerror}")

    def __iter__(self):
        """The iterator.

        This function reads the file, a line at a time and validates the
        CRC. If this are OK, the hex data is decoded using the parser in tm.py
        and the date and resulting TM object are yielded.

        Usage would be something like:

           log_reader = EGSEDumpDecoder("something_SCI.LOG")
           for timestamp, entry in log_reader:
               # Do something with timestamp and entry

        """

        line_number = 0
        for line in self.in_file:
            line_number += 1
            if m := re.match(r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) - (?P<hex>[0-9a-f ]*)\s*$", line):
                matched = m.groupdict()
                bytedata = bytes.fromhex(matched["hex"])

                # Check the CRC. The TM class doesn't raise any error for
                # a bad CRC.
                if crc8.crc8().update(bytedata).hexdigest() != "00":
                    raise Exception(f"Bad CRC at line {line_number}")

                # Extract and return the data.
                yield matched["time"], tm.parse_tm(tm.Response(bytedata), log_hex=False)
            else:
                raise Exception(f"Unmatched line at line {line_number}")

        # Seek back to the start of the file so the iterator can be re-run if needed.
        self.in_file.seek(0)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Decode data from egse log")
    parser.add_argument("-gnuplot", action="store_true", help="Output tab separated data and precede the header line with #")
    parser.add_argument("-fields", type=str, metavar="FIELD[,FIELD[,...]]", help="List of fields you want from the log")
    parser.add_argument("logfile", type=str, metavar="something.LOG", help="Data log from egse")
    parser.add_argument("outfile", type=str, nargs="?", metavar="output.csv", help="File to write to")
    args = parser.parse_args()

    try:
        log_file = EGSEDumpDecoder(args.logfile)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        exit(1)

    # Out file is optional - if not specified, write to standard output.
    if args.outfile is None:
        out_file = sys.stdout
    else:
        try:
            out_file = open(args.outfile, "x")
            print(f"Output will be written to '{args.outfile}'", file=sys.stderr)
        except Exception as e:
            print(f"Error opening CSV file for writing: {str(e)}", file=sys.stderr)
            exit(1)

    # Set field separator.
    if args.gnuplot:
        separator = "\t"
    else:
        separator = ","

    # If fields is specified and is "" then we use all fields.
    # If it's specified and is a comma separated list, we use that list.
    # If it's not specified then we look in default_fields_per_type. This
    # latter option can only be done once we've started reading the file,
    # since we don't know what type it is until that point.
    if args.fields == "":
        args.fields = []
    elif args.fields is not None:
        args.fields = args.fields.split(",")

    try:
        printed_header = False
        for timestamp, entry in log_file:
            if args.fields is None:
                if type(entry) in log_file.default_fields_per_type:
                    args.fields = log_file.default_fields_per_type[type(entry)]
                else:
                    args.fields = []

            # Print header line if not already printed.
            if not printed_header:
                if args.gnuplot:
                    print("# ", end="", file=out_file)
                print(f"Date{separator}Time", end=separator, file=out_file)
                print(entry.csv_header(*args.fields, separator=separator))
                printed_header = True

            # Print data line.
            # To match pre-existing decodes, we need to split date/time
            # into separate columns.
            (date, timeofday) = timestamp.split(" ")
            print(date, end=separator, file=out_file)
            print(timeofday, end=separator, file=out_file)
            print(entry.csv(*args.fields, separator=separator), file=out_file)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        exit(1)
