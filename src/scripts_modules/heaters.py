import logging
import time
import constants as const
import send_cmd
import tc

# ----Logging Setup---------------------------------------------------------------------------------
event_log = logging.getLogger("event_log")
event_log = logging.getLogger("event_log")


def mech_auto_heater_test(port):
    # Firmware bang-bang algorithm (see ICD):
    #   Heater turns ON  only when BOTH current AND previous readings < ON_SP
    #   Heater turns OFF only when BOTH current AND previous readings > OFF_SP
    #   Otherwise: maintain previous state (hysteresis)
    #   On first auto-enable: default state is OFF until two readings < ON_SP
    #
    # THRM_STATUS_BYTE bit map (MSB first): HDS | HMS | UNUSED | S | DM | DA | MM | MA
    #   0x01 = MA=1, HMS=0  — auto enabled, heater OFF
    #   0x41 = MA=1, HMS=1  — auto enabled, heater ON (heating)

    ON_SP  = 0x738  # 1848 DN — 823 Ohm — -45°C
    OFF_SP = 0x79A  # 1946 DN — 882 Ohm — -30°C

    tc.set_mech_sp(port, OFF_SP, ON_SP)
    resp = tc.hk_request(port)
    event_log.info(
        f"Mech Heater ON  threshold : {ON_SP} DN (823 Ohm, -45°C) | HK confirms: {resp.THRM_MECH_ON_SP}"
    )
    event_log.info(
        f"Mech Heater OFF threshold : {OFF_SP} DN (882 Ohm, -30°C) | HK confirms: {resp.THRM_MECH_OFF_SP}"
    )

    # Enable auto mechanism heater — firmware default state is OFF on first enable
    tc.heater_control(port, False, False, False, False, True)
    event_log.info("Mech Auto Heater enabled. Firmware default: OFF until two readings < ON_SP.")

    # ---- Phase 1: Verify initial state is OFF ----
    resp = tc.hk_request(port)
    if resp.THRM_STATUS_BYTE == 0x01:
        event_log.info(f"PASS Phase 1 — Initial state OFF as expected. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}")
    else:
        event_log.error(f"FAIL Phase 1 — Initial state not OFF. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}")

    # ---- Phase 2: Turn ON — need TWO consecutive readings < ON_SP ----
    event_log.info(
        f"Phase 2: Lower resistance below {ON_SP} DN (823 Ohm / -45°C). "
        f"Heater turns ON only after TWO consecutive readings below ON_SP."
    )
    input("Press Return when temperature is below ON threshold...")
    resp_prev = tc.hk_request(port)
    time.sleep(1)
    resp = tc.hk_request(port)
    event_log.info(
        f"  Prev MECH_TRP={resp_prev.MECH_TRP}  Cur MECH_TRP={resp.MECH_TRP}  ON_SP={ON_SP}"
    )
    if resp_prev.MECH_TRP < ON_SP and resp.MECH_TRP < ON_SP:
        if resp.THRM_STATUS_BYTE == 0x41:
            event_log.info(
                f"PASS Phase 2 — Heater ON after two readings < ON_SP. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}"
            )
        else:
            event_log.error(
                f"FAIL Phase 2 — Two readings < ON_SP but heater not ON. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}"
            )
    else:
        event_log.error(
            f"FAIL Phase 2 — Not two consecutive readings below ON_SP. "
            f"Prev={resp_prev.MECH_TRP} Cur={resp.MECH_TRP} ON_SP={ON_SP}"
        )

    # ---- Phase 3: Hysteresis — raise into band, heater should STAY ON ----
    event_log.info(
        f"Phase 3: Raise resistance into hysteresis band ({ON_SP}–{OFF_SP} DN). "
        f"Heater should STAY ON (previous state was ON)."
    )
    input("Press Return when temperature is in the hysteresis band...")
    resp = tc.hk_request(port)
    event_log.info(f"  MECH_TRP={resp.MECH_TRP}")
    if ON_SP <= resp.MECH_TRP <= OFF_SP:
        if resp.THRM_STATUS_BYTE == 0x41:
            event_log.info(
                f"PASS Phase 3 — Heater stayed ON in hysteresis band. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}"
            )
        else:
            event_log.error(
                f"FAIL Phase 3 — Heater did not stay ON in hysteresis band. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}"
            )
    else:
        event_log.error(
            f"FAIL Phase 3 — MECH_TRP={resp.MECH_TRP} not in hysteresis band [{ON_SP}–{OFF_SP}]"
        )

    # ---- Phase 4: Turn OFF — need TWO consecutive readings > OFF_SP ----
    event_log.info(
        f"Phase 4: Raise resistance above {OFF_SP} DN (882 Ohm / -30°C). "
        f"Heater turns OFF only after TWO consecutive readings above OFF_SP."
    )
    input("Press Return when temperature is above OFF threshold...")
    resp_prev = tc.hk_request(port)
    time.sleep(1)
    resp = tc.hk_request(port)
    event_log.info(
        f"  Prev MECH_TRP={resp_prev.MECH_TRP}  Cur MECH_TRP={resp.MECH_TRP}  OFF_SP={OFF_SP}"
    )
    if resp_prev.MECH_TRP > OFF_SP and resp.MECH_TRP > OFF_SP:
        if resp.THRM_STATUS_BYTE == 0x01:
            event_log.info(
                f"PASS Phase 4 — Heater OFF after two readings > OFF_SP. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}"
            )
        else:
            event_log.error(
                f"FAIL Phase 4 — Two readings > OFF_SP but heater not OFF. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}"
            )
    else:
        event_log.error(
            f"FAIL Phase 4 — Not two consecutive readings above OFF_SP. "
            f"Prev={resp_prev.MECH_TRP} Cur={resp.MECH_TRP} OFF_SP={OFF_SP}"
        )

    # ---- Phase 5: Hysteresis — lower into band, heater should STAY OFF ----
    event_log.info(
        f"Phase 5: Lower resistance back into hysteresis band ({ON_SP}–{OFF_SP} DN). "
        f"Heater should STAY OFF (previous state was OFF)."
    )
    input("Press Return when temperature is in the hysteresis band...")
    resp = tc.hk_request(port)
    event_log.info(f"  MECH_TRP={resp.MECH_TRP}")
    if ON_SP <= resp.MECH_TRP <= OFF_SP:
        if resp.THRM_STATUS_BYTE == 0x01:
            event_log.info(
                f"PASS Phase 5 — Heater stayed OFF in hysteresis band. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}"
            )
        else:
            event_log.error(
                f"FAIL Phase 5 — Heater did not stay OFF in hysteresis band. THRM_STATUS_BYTE=0x{resp.THRM_STATUS_BYTE:02X}"
            )
    else:
        event_log.error(
            f"FAIL Phase 5 — MECH_TRP={resp.MECH_TRP} not in hysteresis band [{ON_SP}–{OFF_SP}]"
        )
