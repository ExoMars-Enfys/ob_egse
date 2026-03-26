# Rebase Status and Next Steps

## 1) Current status of the project (as of now)

Current tree is still legacy-style under `src/`:
- `src/main.py`
- `src/gui.py`, `src/ebgui.py`
- `src/core_modules/*` (instead of `src/core/*`)
- `src/utility_modules/*` (instead of `src/utils/*`)
- `src/widget_modules/*` (instead of `src/widgets/*`)
- `src/analysis_modules/*` (instead of `src/analysis/*`)
- `src/scripts_modules/*` (instead of `src/scripts/*`)

Rebase goals from docs are not yet implemented: no `src/enfys_main.py`, no `src/core`, no `src/utils`, etc.

## 2) Cross-check vs proposed structure

Proposed structure (`Documentation/PROPOSED_FRAMEWORK_STRUCTURE.md`):
- `src/enfys_main.py`
- `src/core/config.py`, `constants.py`, `cmd_ids.py`, `tmstruct.py`
- `src/utils/crc8_function.py`, `comms.py`, `send_cmd.py`, `tm.py`, `tc.py`, `psu.py`, `egse_logger.py`, `eb_interface.py`, `eb_sniffer.py`
- `src/widgets/*` (parent_window_widget, packet_viewer_widget, menu_widget, psu_widget, plot_widget, popup_widget, traffic_light_widget, log_window_widget)
- `src/analysis/*` (sci_plot.py, analysis.py, thermal_summary.py)
- `src/scripts/test_scripts.py`

Current module paths mostly match legacy source names with `_modules` prefix; only analysis + script are similar with underscore variations.

## 3) Required actions (priority order)

1. Create package folders + `__init__.py`:
   - `src/core`, `src/utils`, `src/widgets`, `src/analysis`, `src/scripts`
2. Create target entrypoint:
   - `src/enfys_main.py` (refactor `main.py` logic)
3. Move/populate core modules:
   - `src/core/config.py` <= `src/core_modules/config.py`
   - `src/core/constants.py` <= `src/core_modules/constants.py`
   - `src/core/cmd_ids.py` <= `src/core_modules/cmd_ids.py`
   - `src/core/tmstruct.py` <= `src/core_modules/tmstruct.py`
4. Move/populate util modules:
   - `src/utils/*.py` from `src/utility_modules/*.py` (and add missing `eb_sniffer.py` if needed)
5. Move analysis modules:
   - `src/analysis/*.py` from `src/analysis_modules/*.py` (merge/rename where necessary)
6. Move script modules:
   - Create `src/scripts/test_scripts.py` consolidating `src/scripts_modules/*.py` and `src/analysis_modules/fill_chamber_temps_and_dwell.py` as per checklists
7. Create widget modules
   - Start with `parent_window_widget.py` and keep current `gui.py` adapter
   - Extract remaining legacy widget functionality into dedicated files
8. Update and/or create import shim adapters to keep behavior while migrating.

## 4) GUI-specific graphical plan

### High-level widget flow (Mermaid)

```mermaid
flowchart LR
  A[enfys_main()] --> B[parent_window_widget]
  B --> C[menu_widget]
  B --> D[packet_viewer_widget]
  B --> E[psu_widget]
  B --> F[plot_widget]
  B --> G[popup_widget]
  B --> H[traffic_light_widget]
  B --> I[log_window_widget]

  C -.->|commands| U[utils.send_cmd]
  D -.->|TM decoding| V[analysis.tm / core.tmstruct]
  E -.->|PSU flow| W[utils.psu]
  F -.->|data plot| X[analysis.sci_plot | analysis.thermal_summary]
  G -.->|alerts| Y[core.constants | core.config]
  H -.->|status| Z[core.constants]
  I -.->|logging| Q[utils.egse_logger]
```

> Note: Accept that this is a design sketch; refine after first pass at widget refactor.

## 5) Remain checks from `FRAMEWORK_REBASE_MIGRATION_CHECKLIST.md`

- [ ] `src/enfys_main.py` creation
- [ ] `src/scripts/test_scripts.py`
- [ ] `src/widgets/log_window_widget.py` exists
- [ ] safe import rewrites (`from core...`, `from utils...`, etc.)
- [ ] run scoops: `ruff`, type-check, runtime GUI smoke test, scripts functional test

## 6) Quick hits / first merge strategy

1. Create repository-wide pipeline in `pyproject.toml` for lint/test
2. Phase 1 branch: folder skeleton + copy code + pass `ruff`
3. Phase 2 branch: switch imports + preserve foo
4. Phase 3 branch: remove old path + final cleanup
5. Final: update README run instructions + docs

---

## 7) Runtime vs Pylance note

The earlier Pylance type issues in `src/utility_modules/tc.py` are a static-type _noise_ path (doesn't block runtime there if object shapes are valid). Keep this in mind when migrating to strict `core` types.
