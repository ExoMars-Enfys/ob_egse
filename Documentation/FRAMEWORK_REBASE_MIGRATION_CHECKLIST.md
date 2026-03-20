# Framework Rebase Migration Checklist

This checklist translates the proposed structure in `PROPOSED_FRAMEWORK_STRUCTURE.md` into an execution plan.

Scope:
- Rebase `src/` into `core/`, `utils/`, `widgets/`, `analysis/`, `scripts/`.
- Preserve behavior first, then refine module internals.
- Consolidate legacy scripts into `scripts/test_scripts.py`.

## 1) Migration Strategy

Order of work:
1. Create target package folders and placeholders.
2. Move low-risk foundational modules (`core`, `utils`, `analysis`) with import rewrites.
3. Introduce widget split while keeping old UI entrypoints as temporary adapters.
4. Consolidate scripting modules.
5. Switch main entrypoint to `enfys_main.py`.
6. Remove compatibility shims.

Branching recommendation:
- Use one feature branch for the whole rebase.
- Commit by phase to keep rollback simple.

## 2) Target Tree Checklist

- [X] Create `src/core/`
- [X] Create `src/utils/`
- [X] Create `src/widgets/`
- [X] Create `src/analysis/`
- [X] Create `src/scripts/` (retain existing folder)
- [X] Add `__init__.py` in each new package folder
- [ ] Create `src/enfys_main.py`
- [ ] Create widget module files:
  - [ ] `src/widgets/parent_window_widget.py`
  - [ ] `src/widgets/packet_viewer_widget.py`
  - [ ] `src/widgets/menu_widget.py`
  - [ ] `src/widgets/psu_widget.py`
  - [ ] `src/widgets/plot_widget.py`
  - [ ] `src/widgets/popup_widget.py`
  - [ ] `src/widgets/traffic_light_widget.py`
  - [ ] `src/widgets/log_window_widget.py`
- [ ] Create `src/scripts/test_scripts.py`

## 3) Source -> Target Mapping

## Core
- [ ] `src/config.py` -> `src/core/config.py`
- [ ] `src/constants.py` -> `src/core/constants.py`
- [ ] `src/cmd_ids.py` -> `src/core/cmd_ids.py`
- [ ] `src/tmstruct.py` -> `src/core/tmstruct.py`
- [ ] `src/main.py` -> `src/enfys_main.py` (do not directly move; refactor entrypoint)

## Utils
- [ ] `src/crc8_function.py` -> `src/utils/crc8_function.py`
- [ ] `src/comms.py` -> `src/utils/comms.py`
- [ ] `src/send_cmd.py` -> `src/utils/send_cmd.py`
- [ ] `src/tm.py` -> `src/utils/tm.py`
- [ ] `src/tc.py` -> `src/utils/tc.py`
- [ ] `src/psu.py` -> `src/utils/psu.py`
- [ ] `src/egse_logger.py` -> `src/utils/egse_logger.py`
- [ ] `src/eb_interface.py` -> `src/utils/eb_interface.py`
- [ ] `src/eb_sniffer.py` -> `src/utils/eb_sniffer.py`

## Analysis
- [ ] `src/sci_plot.py` -> `src/analysis/sci_plot.py`
- [ ] `src/scripts/analysis.py` -> `src/analysis/analysis.py`
- [ ] `src/scripts/thermal_summary.py` -> `src/analysis/thermal_summary.py`

## Widgets (split from legacy UI)
- [ ] `src/gui.py` and `src/ebgui.py` -> `src/widgets/parent_window_widget.py` (initial shell)
- [ ] Extract packet-specific views -> `src/widgets/packet_viewer_widget.py`
- [ ] Extract menu/actions -> `src/widgets/menu_widget.py`
- [ ] Fold mechanism controls/status into `src/widgets/menu_widget.py`
- [ ] Extract PSU panel/actions -> `src/widgets/psu_widget.py`
- [ ] Extract plot panel/actions -> `src/widgets/plot_widget.py`
- [ ] Centralize dialogs -> `src/widgets/popup_widget.py`
- [ ] Move health indicators -> `src/widgets/traffic_light_widget.py`
- [ ] Move log panel handler/view -> `src/widgets/log_window_widget.py`

## Scripts consolidation
- [ ] Consolidate the following into `src/scripts/test_scripts.py`:
  - [ ] `src/scripts/sequences.py`
  - [ ] `src/scripts/abu_sequences.py`
  - [ ] `src/scripts/error_checks.py`
  - [ ] `src/scripts/heaters.py`
  - [ ] `src/scripts/LTM.py`
  - [ ] `src/scripts/OB_FFT.py`
  - [ ] `src/scripts/fill_chamber_temps_and_dwell.py`

## 4) Import Rewrite Checklist

Global rewrite rules:
- [ ] Replace `import config` with `from core import config` (or `from core.config import ...`)
- [ ] Replace `import constants as const` with `from core import constants as const`
- [ ] Replace `from cmd_ids import ...` with `from core.cmd_ids import ...`
- [ ] Replace `import tmstruct` with `from core import tmstruct`

- [ ] Replace `import comms` with `from utils import comms`
- [ ] Replace `import psu` with `from utils import psu`
- [ ] Replace `import tc` with `from utils import tc`
- [ ] Replace `import tm` with `from utils import tm`
- [ ] Replace `import send_cmd` with `from utils import send_cmd`
- [ ] Replace `import eb_sniffer` with `from utils import eb_sniffer`
- [ ] Replace `import eb_interface` with `from utils import eb_interface`
- [ ] Replace `import egse_logger` with `from utils import egse_logger`

- [ ] Replace `import sci_plot` with `from analysis import sci_plot`
- [ ] Replace `import scripts.analysis` with `from analysis import analysis`
- [ ] Replace `import scripts.thermal_summary` with `from analysis import thermal_summary`

Temporary compatibility (until full cutover):
- [ ] Keep temporary shim modules at old paths that re-export from new locations
- [ ] Remove shims only after final validation

## 5) Entry Point Cutover Checklist

- [ ] Create `src/enfys_main.py` from `main.py` logic
- [ ] Update UI imports to widget package (`parent_window_widget` first)
- [ ] Update script mode imports to consolidated `scripts/test_scripts.py`
- [ ] Ensure CLI arguments remain backward-compatible
- [ ] Update `pyproject.toml` entrypoint (if defined)
- [ ] Update README run commands

## 6) Widget Split Checklist (Safe Sequence)

Phase A (no behavior change):
- [ ] Create `parent_window_widget.py` and move top-level UI orchestration there
- [ ] Keep all detailed controls in one place initially

Phase B (extract by responsibility):
- [ ] Extract log handling -> `log_window_widget.py`
- [ ] Extract plotting -> `plot_widget.py`
- [ ] Extract PSU controls -> `psu_widget.py`
- [ ] Extract packet display -> `packet_viewer_widget.py`
- [ ] Extract menu actions -> `menu_widget.py`
- [ ] Fold mechanism dashboard controls into `menu_widget.py`
- [ ] Extract dialogs/popups -> `popup_widget.py`
- [ ] Extract traffic-light indicator -> `traffic_light_widget.py`

Phase C (cleanup):
- [ ] Remove duplicated code left in parent window
- [ ] Standardize widget interfaces (init, update, bind callbacks)

## 7) Script Consolidation Checklist

- [ ] Define sections in `test_scripts.py`:
  - [ ] Power-up / power-down flows
  - [ ] Error injection/check flows
  - [ ] Mechanism test flows
  - [ ] Thermal helper flows
- [ ] Preserve existing function names via wrappers where practical
- [ ] Add module-level index comment for script discoverability
- [ ] Mark non-production sequences clearly

## 8) Validation Gates (Run After Each Phase)

Static checks:
- [ ] Run Ruff/lint checks
- [ ] Run type checks (if configured)
- [ ] Verify imports resolve in VS Code/Pylance

Runtime checks:
- [ ] Start app in GUI mode and verify parent window loads
- [ ] Verify packet polling path still works
- [ ] Verify PSU connect/read/switch path
- [ ] Verify analysis plotting path (`sci_plot`, `analysis`, `thermal_summary`)
- [ ] Verify consolidated test scripts can be invoked

Regression checks:
- [ ] Command send/ACK parse still valid
- [ ] HK decode outputs unchanged
- [ ] Logging files still created with expected names/locations

## 9) Decommission Checklist (Final)

- [ ] Remove legacy files after successful cutover:
  - [ ] `src/main.py`
  - [ ] `src/gui.py`
  - [ ] `src/ebgui.py`
  - [ ] old moved root modules now under `core/` and `utils/`
  - [ ] old individual script files consolidated into `test_scripts.py`
- [ ] Remove temporary compatibility shims
- [ ] Update architecture docs and flowcharts
- [ ] Tag release point for post-rebase baseline

## 10) Suggested Commit Plan

1. `chore(rebase): create package skeleton and init files`
2. `refactor(rebase): move core and utility modules with import rewrites`
3. `refactor(ui): create parent window widget and wire enfys_main`
4. `refactor(ui): extract widget modules by responsibility`
5. `refactor(analysis): move analysis modules to dedicated package`
6. `refactor(scripts): consolidate scripts into test_scripts`
7. `chore(cleanup): remove legacy modules and compatibility shims`
8. `docs: update framework and migration documentation`
