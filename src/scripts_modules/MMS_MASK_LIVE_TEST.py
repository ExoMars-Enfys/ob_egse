"""Live MMS check: EB faults must still trigger the MMS while the INST_VOLTAGE_TEST masks are active.

Run from the GUI menu in EB mode with MMS enabled and EB-only / no-OB test mode
selected before power-up. Wait for any previous shutdown to finish, select test
mode, reset the latch and power the EB at nominal conditions. The operator picks one case;
the script applies the INST_VOLTAGE_TEST masks and induces that fault:

* EB out-of-bounds cases tighten the live MMS alarm limit for one EB parameter
  just below its current reading, so the real HK reading trips the MMS.
* EB error-flag and POST cases inject a copy of the latest HK packet with the
  flag set into the HK queue (software injection: this proves the EGSE MMS
  path, not EB firmware fault detection).
* The masked-flags control case injects only the masked flags and expects no trip.

A real trip is a real MMS action: the script is aborted, SAFE/RET are sent and
the PSU outputs are switched off. Only one trip is possible per run; use Reset
Latch in the menu before the next run. Limits and masks are always restored.
MMS remains enabled throughout preparation, selection and cleanup. The session
test mode stays selected between runs; disable it before normal OB operation.
"""

import copy
import logging
import time
from dataclasses import dataclass
from queue import Full
from types import SimpleNamespace
from typing import Any

from core_modules import constants as const
from core_modules import tmstruct
from scripts_modules.INST_VOLTAGE_TEST import inst_voltage_mms_masks
from widget_modules import ui_runtime_controller as urc

info_log = logging.getLogger("info_log")

INST_VOLTAGE_MASKED_FLAGS = frozenset({"OB_UNRESPONSIVE", "RS485_RECEIVE_ERROR", "RS485_TRANSMIT_ERROR"})
LIMIT_MARGIN = 0.5  # Engineering units placed between the live reading and the tightened alarm limit.
TRIP_TIMEOUT_S = 30.0  # MMS waits up to 10 s for SAFE confirmation before the PSU shutdown.
CONTROL_WINDOW_S = 10.0
INJECT_PERIOD_S = 0.5


@dataclass(frozen=True)
class Case:
    title: str
    kind: str  # "limit", "flag", "post" or "control"
    expected_reason: str = ""
    label: str = ""
    field: str = ""
    limit_key: str = ""
    flag: str = ""


def _cases() -> list[Case]:
    cases = [
        Case(
            title=f"EB out of bounds: {label} ({field})",
            kind="limit",
            expected_reason=f"{label} out of limits",
            label=label,
            field=field,
            limit_key=limit_key,
        )
        for label, field, limit_key, _tec in urc._MMS_FIELDS
        if not label.startswith("OB ")
    ]
    cases += [
        Case(
            title=f"EB error flag (injected): {flag}",
            kind="flag",
            expected_reason=f"HK Error Flags asserted: {flag}",
            flag=flag,
        )
        for flag, _ in tmstruct.eb_warning_flags
        if flag != "RESERVED" and flag not in INST_VOLTAGE_MASKED_FLAGS
    ]
    cases.append(Case(title="POST error flags (injected)", kind="post", expected_reason="POST Error Flags asserted"))
    cases.append(Case(title="Control: masked flags only (injected) - expect NO trip", kind="control"))
    return cases


def _error_flags_value(flags: set[str]) -> int:
    names = [name for name, _ in tmstruct.eb_warning_flags]
    value = 0
    for index, name in enumerate(names):
        if name in flags:
            value |= 1 << (len(names) - 1 - index)  # bitstruct packs MSB-first
    return value


def _injected_hk(base_hk: Any, case: Case) -> Any:
    hk = copy.copy(base_hk)
    flags = set(INST_VOLTAGE_MASKED_FLAGS)
    if case.kind == "flag":
        flags.add(case.flag)
    if case.kind == "post":
        hk.POST_ERROR_FLAGS = 0x0001
        flags = set()
    hk.ERROR_FLAGS = _error_flags_value(flags)
    hk.ERROR_FLAGS_BITS = SimpleNamespace(**{name: int(name in flags) for name, _ in tmstruct.eb_warning_flags})
    return hk


def _report(message: str, passed: bool) -> None:
    (info_log.info if passed else info_log.error)("MMS_MASK_LIVE_TEST: %s", message)
    urc.notify(message, color="positive" if passed else "negative")


def _mms_settled(mms_cfg: dict[str, Any]) -> bool:
    return bool(mms_cfg.get("latched")) and not mms_cfg.get("in_progress") and not mms_cfg.get("pending")


def _preflight(gui_state: dict[str, Any]) -> str | None:
    mms_cfg = gui_state.get("mms") or {}
    if gui_state.get("mode") != "EB":
        return "EGSE must be in EB mode."
    if mms_cfg.get("in_progress") or mms_cfg.get("pending"):
        return "MMS shutdown is still active; wait for it to finish before changing controls."
    if not mms_cfg.get("enabled", True):
        return "Enable MMS; EB protection must remain active throughout this test."
    if not const.MMS_EB_ONLY_TEST_MODE:
        return "Select EB-only / no-OB test mode before powering the EB."
    if mms_cfg.get("latched"):
        return "MMS is already latched; with EB-only test mode selected, press Reset Latch first."
    if gui_state.get("latest_hk_packet") is None:
        return "No EB HK received yet."
    return None


def _wait_for_trip(gui_state: dict[str, Any], case: Case, timeout_s: float) -> bool:
    mms_cfg = gui_state["mms"]
    deadline = time.monotonic() + timeout_s
    base_hk = gui_state["latest_hk_packet"]
    while time.monotonic() < deadline:
        if _mms_settled(mms_cfg):
            return True
        # Keep injecting: the HK poll loop drops stale queued packets when real HK arrives.
        if case.kind != "limit" and not (mms_cfg.get("in_progress") or mms_cfg.get("pending")):
            try:
                const.hk_queue.put_nowait(_injected_hk(base_hk, case))
            except Full:
                info_log.warning("MMS_MASK_LIVE_TEST: HK queue full; retrying fault injection.")
        if urc.is_aborted() and not (mms_cfg.get("in_progress") or mms_cfg.get("pending")):
            raise urc.ScriptAbortRequested
        time.sleep(INJECT_PERIOD_S)
    return _mms_settled(mms_cfg)


def run_mms_mask_live_test(gui_state: dict[str, Any]) -> None:
    problem = _preflight(gui_state)
    if problem:
        _report(f"Cannot run: {problem}", passed=False)
        return

    cases = {case.title: case for case in _cases()}
    choice = urc.request_choice(
        "Select the fault to induce while the INST_VOLTAGE_TEST MMS masks are active.\n"
        "Limit cases use the real HK reading; flag/POST cases inject a software HK packet.\n"
        "MMS stays ON and EB protection remains active between tests.\n"
        "Disable EB-only test mode before normal OB operation.",
        list(cases),
        title="MMS mask live test",
    )
    if choice is None:
        _report("Cancelled; nothing changed.", passed=True)
        return
    case = cases[choice]

    if case.kind != "control" and not urc.request_confirmation(
        f"{case.title}\n\nThis will trigger a REAL MMS: the script will be aborted, SAFE/RET sent "
        "and ALL PSU outputs switched OFF.\nPress Reset Latch before re-powering.",
        title="Confirm real MMS trip",
        confirm_label="Trigger MMS",
        severity="negative",
    ):
        _report("Cancelled; nothing changed.", passed=True)
        return

    mms_cfg = gui_state["mms"]
    problem = _preflight(gui_state)
    if problem:
        _report(f"Cannot arm: {problem}", passed=False)
        return
    original_limits = mms_cfg.get("limits") or {}
    info_log.info("MMS_MASK_LIVE_TEST: running case '%s'", case.title)

    with inst_voltage_mms_masks():
        try:
            hk = gui_state["latest_hk_packet"]
            baseline, _tec, _ob5v = urc.mms_reasons(hk, original_limits)
            if baseline:
                _report(f"Aborted before fault: MMS reasons already present: {'; '.join(baseline)}", passed=False)
                return

            if case.kind == "limit":
                reading = urc.decoded(hk, case.field)
                if reading is None:
                    _report(f"Aborted: no live reading for {case.field}.", passed=False)
                    return
                tightened = dict(original_limits)
                tightened[case.limit_key] = (None, reading - LIMIT_MARGIN)
                info_log.info(
                    "MMS_MASK_LIVE_TEST: %s live=%.3f, temporary MMS limit %s -> %s",
                    case.field,
                    reading,
                    original_limits.get(case.limit_key),
                    tightened[case.limit_key],
                )
                # Replace (not mutate) so the HK poll loop always sees a consistent mapping.
                mms_cfg["limits"] = tightened

            if case.kind == "control":
                tripped = _wait_for_trip(gui_state, case, CONTROL_WINDOW_S)
                if tripped:
                    _report(f"FAIL: masked flags tripped the MMS: {mms_cfg.get('reasons')}", passed=False)
                else:
                    _report("PASS: masked flags alone did not trip the MMS.", passed=True)
                return

            tripped = _wait_for_trip(gui_state, case, TRIP_TIMEOUT_S)
            reasons = list(mms_cfg.get("reasons") or [])
            if not tripped:
                _report(f"FAIL: '{case.title}' did not trigger the MMS within {TRIP_TIMEOUT_S:.0f} s.", passed=False)
            elif any(reason.startswith(case.expected_reason) for reason in reasons):
                _report(
                    f"PASS: '{case.title}' triggered the MMS. Reasons: {'; '.join(reasons)}. "
                    "Confirm the PSU outputs are OFF, then press Reset Latch.",
                    passed=True,
                )
            else:
                _report(
                    f"FAIL: MMS tripped without the expected reason '{case.expected_reason}'. "
                    f"Reasons: {'; '.join(reasons)}",
                    passed=False,
                )
        finally:
            mms_cfg["limits"] = original_limits
            info_log.info("MMS_MASK_LIVE_TEST: limits restored; MMS and EB-only test mode unchanged.")
