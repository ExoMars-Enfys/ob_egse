# Expanded pytest coverage patch v15

Copy the five `test_*.py` files into `src/tests`, replacing the existing files.
No production source files are changed by this patch.

The additions cover:

- constants-backed monitoring registry validation and plot-range errors;
- OB FDIR inclusive boundaries, disabled mode, invalid ADCs, restored state,
  mixed-fault shutdown priority, no downgrade, bitmasks, and reset callbacks;
- alarm clear/retrigger behaviour, valid/missing HK, valid/missing POST,
  conversion errors, CRC/status failures, and unknown check types;
- MMS in-progress de-duplication, no-script behaviour, SAFE/RET failures,
  SAFE-mode OB5V skip, unconfirmed SAFE fallback, PSU errors, and io-bound cleanup;
- zero/edge packet bitmaps, OB error-byte decoding, truncated packets, and
  science block-length helpers.

Optional coverage configuration is provided in `coverage_pyproject_snippet.toml`.
Merge it into `pyproject.toml` rather than copying it as a standalone project file.

Run:

    uv run pytest -vv --cov=src --cov-branch --cov-report=term-missing --cov-report=html
