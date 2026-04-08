from __future__ import annotations

from typing import Any


SCI_HEADER_FIELDS = [
    "PACKET_NUMBER",
    "SOL_NO",
    "MEASUREMENT_TYPE_ID",
    "MEASUREMENT_RUN_NO",
    "START_TIME_S",
    "START_TIME_MS",
    "END_TIME_S",
    "END_TIME_MS",
    "SWIR_OFFSET",
    "MWIR_OFFSET",
    "HEATSINK_START_TEMP",
    "HEATSINK_END_TEMP",
    "SWIR_START_TEMP",
    "SWIR_END_TEMP",
    "MWIR_START_TEMP",
    "MWIR_END_TEMP",
    "START_MTR_ABS_STEPS",
    "SAMPLE_DELAY",
    "FPGA_SAMPLES",
    "ACQUISITION_MODE",
    "AVERAGING_NUMBER",
    "SCI_POINT_COUNT",
]


SCI_POINT_FIELDS = [
    "ABS_STEPS",
    "SWIR_HIGH",
    "SWIR_MED",
    "SWIR_LOW",
    "MWIR_HIGH",
    "MWIR_MED",
    "MWIR_LOW",
]


def format_measurement_config(value: Any) -> str:
    try:
        mode = int(value)
    except (TypeError, ValueError):
        return str(value)

    mode_map = {
        0b00: "Standard Scan",
        0b01: "Limited Scan",
        0b10: "Fixed Scan",
    }
    if mode in mode_map:
        return f"0b{mode:02b}: {mode_map[mode]}"
    return str(mode)


def format_acquisition_mode(value: Any) -> str:
    return format_measurement_config(value)


def format_sci_temp_value(value: Any) -> str:
    try:
        return str(int(value) >> 4)
    except (TypeError, ValueError):
        return str(value)


def format_sci_packet_number(value: Any) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def sci_packet_sort_key(packet: Any) -> int:
    try:
        return int(getattr(packet, "PACKET_NUMBER", 0))
    except (TypeError, ValueError):
        return 0


def sci_packet_identity(packet: Any) -> tuple[Any, ...]:
    packet_number = getattr(packet, "PACKET_NUMBER", None)
    criticality = getattr(packet, "SCI_PACKET_CRITICALITY", None)
    point_count = int(getattr(packet, "SCI_POINT_COUNT", 0) or 0)

    first_abs_step = None
    last_abs_step = None
    sci_points = getattr(packet, "SCI_POINTS", None)
    if sci_points:
        first_abs_step = getattr(sci_points[0], "ABS_STEPS", None)
        last_abs_step = getattr(sci_points[-1], "ABS_STEPS", None)
    elif hasattr(packet, "ABS_STEPS"):
        first_abs_step = getattr(packet, "ABS_STEPS", None)
        last_abs_step = first_abs_step

    return (packet_number, criticality, point_count, first_abs_step, last_abs_step)


def post_packet_identity(post: Any) -> tuple[Any, ...]:
    return (
        getattr(post, "POST_WARNING_FLAGS", None),
        getattr(post, "POST_ERROR_FLAGS", None),
        getattr(post, "NUM_BAD_FLASH_BLOCKS", None),
        getattr(post, "NUM_BAD_SRAM_BLOCKS", None),
        getattr(post, "ASW_IMAGE_1_CRC", None),
        getattr(post, "ASW_IMAGE_2_CRC", None),
        getattr(post, "ASW_IMAGE_3_CRC", None),
        getattr(post, "ASW_IMAGE_4_CRC", None),
        getattr(post, "ASW_IMAGE_5_CRC", None),
        getattr(post, "BSW_IMAGE_CRC", None),
        getattr(post, "MEASUREMENT_TABLE_CRC", None),
    )


def set_sci_packet(
    packet_index: int,
    sci_packets: list[Any],
    last_sci: dict[str, Any],
    sci_packet_state: dict[str, int],
    sci_view_state: dict[str, int],
    update_panel: Any,
) -> None:
    if not sci_packets:
        last_sci["value"] = None
        sci_packet_state["index"] = 0
        sci_view_state["index"] = 0
        update_panel()
        return

    sci_packet_state["index"] = packet_index % len(sci_packets)
    last_sci["value"] = sci_packets[sci_packet_state["index"]]
    sci_view_state["index"] = 0
    update_panel()


def shift_sci_packet(
    delta: int,
    sci_packets: list[Any],
    sci_packet_state: dict[str, int],
    set_packet_fn: Any,
) -> None:
    if not sci_packets:
        return
    set_packet_fn(sci_packet_state["index"] + delta)


def shift_sci_point(delta: int, last_sci: dict[str, Any], sci_view_state: dict[str, int], update_panel: Any) -> None:
    sci = last_sci["value"]
    if sci is None:
        return

    point_count = int(getattr(sci, "SCI_POINT_COUNT", 0) or 0)
    if point_count <= 0:
        return

    sci_view_state["index"] = (sci_view_state["index"] + delta) % point_count
    update_panel()


def plot_sci_buffer(ui: Any, sci_plot: Any, last_sci: dict[str, Any]) -> None:
    sci = last_sci["value"]
    if sci is None:
        ui.notify("No science packet selected to plot", type="warning")
        return

    packet_number = getattr(sci, "PACKET_NUMBER", "?")
    image_urls = sci_plot.render_sci_packets_data_urls(
        sci_packets=[sci],
        title_prefix=f"SCI Packet {packet_number}",
    )
    if not image_urls:
        ui.notify("Selected packet has no science data points to plot", type="warning")
        return

    with ui.dialog() as plot_dialog:
        with ui.card().classes("w-[95vw] max-w-6xl max-h-[90vh] overflow-auto"):
            with ui.row(align_items="center").classes("w-full justify-between"):
                ui.label("Science Plot (ABS steps vs intensity)").classes("text-lg font-bold")
                ui.button(icon="close", on_click=plot_dialog.close).props("flat dense round")
            ui.separator()
            for image_url in image_urls:
                ui.image(image_url).props("contain").classes("w-full")

    plot_dialog.open()
    ui.notify("Plotted selected packet (ABS steps vs intensity)", type="positive")


def check_hk_manually(
    ui: Any,
    last_hk: dict[str, Any],
    labels: dict[str, Any],
    format_voltage: Any,
    format_temperature: Any,
    temperature_limit_state: Any,
    set_chip_state: Any,
    eb_sniffer: Any,
) -> None:
    if last_hk["value"] is None:
        ui.notify("No HK data available yet", type="warning")
        return

    hk = last_hk["value"]
    eb_12v = hk.EB_MEAS_MAIN_12V * 0.000400543
    eb_neg12v = hk.EB_MEAS_MAIN_NEG12V * -0.00038147
    eb_5v = hk.EB_MEAS_5V * 0.000152829
    eb_3v3 = hk.EB_MEAS_3V3 * 0.0000763
    eb_tec_v = hk.EB_MEAS_TEC_RAIL * 0.0000763
    eb_0v = hk.EB_0V_ADC_READING * 0.0000763
    eb_tec_i = hk.EB_TEC_DRIVE_CURRENT * 0.0000162
    eb_mcu_temp_adu = hk.EB_MCU_INTERNAL_TEMP
    eb_mcu_temp = eb_mcu_temp_adu * 0.01637198 - 273
    eb_peltier_temp_adu = hk.EB_PELTIER_TEMP
    eb_peltier_temp = eb_peltier_temp_adu * -0.001830011 + 51.27039922
    eb_internal_trp_adu = hk.EB_INTERNAL_TRP_TEMP
    eb_internal_trp = eb_sniffer.thermistor_adu_to_temp(eb_internal_trp_adu)
    eb_psu_board_temp_adu = hk.EB_PSU_BOARD_TEMP
    eb_psu_board_temp = eb_sniffer.thermistor_adu_to_temp(eb_psu_board_temp_adu)

    labels["hk_tcs_accepted"].set_text(f"{hk.TCS_ACCEPTED}")
    labels["hk_tcs_accepted"].set_background_color("green" if hk.TCS_ACCEPTED == 2 else "red")
    labels["hk_tcs_accepted"].set_icon("check_circle" if hk.TCS_ACCEPTED == 2 else "error")

    labels["hk_tcs_rejected"].set_text(f"{hk.TCS_REJECTED}")
    labels["hk_tcs_rejected"].set_background_color("green" if hk.TCS_REJECTED == 0 else "red")
    labels["hk_tcs_rejected"].set_icon("check_circle" if hk.TCS_REJECTED == 0 else "error")

    labels["hk_instr_status_flags"].set_text(f"{hk.INSTRUMENT_STATUS_FLAGS}")
    labels["hk_instr_status_flags"].set_background_color("green" if hk.INSTRUMENT_STATUS_FLAGS == 6 else "red")
    labels["hk_instr_status_flags"].set_icon("check_circle" if hk.INSTRUMENT_STATUS_FLAGS == 6 else "error")

    labels["hk_error_flags"].set_text(f"{hk.ERROR_FLAGS}")
    labels["hk_error_flags"].set_background_color("green" if hk.ERROR_FLAGS == 0 else "red")
    labels["hk_error_flags"].set_icon("check_circle" if hk.ERROR_FLAGS == 0 else "error")

    labels["hk_warning_flags"].set_text(f"{hk.WARNING_FLAGS}")
    labels["hk_warning_flags"].set_background_color("green" if hk.WARNING_FLAGS == 0 else "red")
    labels["hk_warning_flags"].set_icon("check_circle" if hk.WARNING_FLAGS == 0 else "error")

    labels["hk_fdir_alarms"].set_text(f"{hk.FDIR_ALARM_FLAGS}")
    labels["hk_fdir_alarms"].set_background_color("green" if hk.FDIR_ALARM_FLAGS == 0 else "red")
    labels["hk_fdir_alarms"].set_icon("check_circle" if hk.FDIR_ALARM_FLAGS == 0 else "error")

    labels["hk_fdir_warnings"].set_text(f"{hk.FDIR_WARNING_FLAGS}")
    labels["hk_fdir_warnings"].set_background_color("green" if hk.FDIR_WARNING_FLAGS == 0 else "red")
    labels["hk_fdir_warnings"].set_icon("check_circle" if hk.FDIR_WARNING_FLAGS == 0 else "error")

    labels["hk_eb_12v"].set_text(format_voltage(eb_12v, hk.EB_MEAS_MAIN_12V))
    labels["hk_eb_12v"].set_background_color("green" if 11.0 <= eb_12v <= 13.0 else "red")
    labels["hk_eb_12v"].set_icon("check_circle" if 11.0 <= eb_12v <= 13.0 else "error")

    labels["hk_eb_neg12v"].set_text(format_voltage(eb_neg12v, hk.EB_MEAS_MAIN_NEG12V))
    labels["hk_eb_neg12v"].set_background_color("green" if -13.0 <= eb_neg12v <= -11.0 else "red")
    labels["hk_eb_neg12v"].set_icon("check_circle" if -13.0 <= eb_neg12v <= -11.0 else "error")

    labels["hk_eb_5v"].set_text(format_voltage(eb_5v, hk.EB_MEAS_5V))
    labels["hk_eb_5v"].set_background_color("green" if 4.5 <= eb_5v <= 5.5 else "red")
    labels["hk_eb_5v"].set_icon("check_circle" if 4.5 <= eb_5v <= 5.5 else "error")

    labels["hk_eb_3v3"].set_text(format_voltage(eb_3v3, hk.EB_MEAS_3V3))
    labels["hk_eb_3v3"].set_background_color("green" if 2.8 <= eb_3v3 <= 3.8 else "red")
    labels["hk_eb_3v3"].set_icon("check_circle" if 2.8 <= eb_3v3 <= 3.8 else "error")

    labels["hk_eb_tec_v"].set_text(format_voltage(eb_tec_v, hk.EB_MEAS_TEC_RAIL))
    labels["hk_eb_tec_v"].set_background_color("green" if -0.5 <= eb_tec_v <= 0.5 else "red")
    labels["hk_eb_tec_v"].set_icon("check_circle" if -0.5 <= eb_tec_v <= 0.5 else "error")

    labels["hk_eb_0v"].set_text(format_voltage(eb_0v, hk.EB_0V_ADC_READING))
    labels["hk_eb_0v"].set_background_color("green" if -0.5 <= eb_0v <= 0.5 else "red")
    labels["hk_eb_0v"].set_icon("check_circle" if -0.5 <= eb_0v <= 0.5 else "error")

    set_chip_state(
        labels["hk_eb_mcu_temp"],
        format_temperature(eb_mcu_temp, eb_mcu_temp_adu),
        temperature_limit_state(eb_mcu_temp, eb_mcu_temp_adu),
    )
    set_chip_state(
        labels["hk_eb_peltier_temp"],
        format_temperature(eb_peltier_temp, eb_peltier_temp_adu),
        temperature_limit_state(eb_peltier_temp, eb_peltier_temp_adu),
    )
    set_chip_state(
        labels["hk_eb_internal_trp"],
        format_temperature(eb_internal_trp, eb_internal_trp_adu),
        temperature_limit_state(eb_internal_trp, eb_internal_trp_adu),
    )
    set_chip_state(
        labels["hk_eb_psu_board_temp"],
        format_temperature(eb_psu_board_temp, eb_psu_board_temp_adu),
        temperature_limit_state(eb_psu_board_temp, eb_psu_board_temp_adu),
    )

    labels["hk_eb_tec_drive_i"].set_text(f"{eb_tec_i:.4f} A")
    labels["hk_eb_tec_drive_i"].set_background_color("green" if -0.1 <= eb_tec_i <= 0.1 else "red")
    labels["hk_eb_tec_drive_i"].set_icon("check_circle" if -0.1 <= eb_tec_i <= 0.1 else "error")

    ui.notify("HK validation complete", type="positive")


def check_post_manually(ui: Any, last_post: dict[str, Any], labels: dict[str, Any], set_chip_state: Any) -> None:
    if last_post["value"] is None:
        ui.notify("No POST data available yet", type="warning")
        return

    post = last_post["value"]

    set_chip_state(
        labels["post_warning_flags"], f"{post.POST_WARNING_FLAGS}", "ok" if post.POST_WARNING_FLAGS == 0 else "alarm"
    )
    set_chip_state(
        labels["post_error_flags"], f"{post.POST_ERROR_FLAGS}", "ok" if post.POST_ERROR_FLAGS == 0 else "alarm"
    )
    set_chip_state(
        labels["post_bad_flash"], f"{post.NUM_BAD_FLASH_BLOCKS}", "ok" if post.NUM_BAD_FLASH_BLOCKS == 0 else "alarm"
    )
    set_chip_state(
        labels["post_bad_sram"], f"{post.NUM_BAD_SRAM_BLOCKS}", "ok" if post.NUM_BAD_SRAM_BLOCKS == 0 else "alarm"
    )
    set_chip_state(
        labels["post_asw1_crc"], f"0x{post.ASW_IMAGE_1_CRC:04X}", "ok" if post.ASW_IMAGE_1_CRC == 0xBAF7 else "alarm"
    )
    set_chip_state(
        labels["post_asw2_crc"], f"0x{post.ASW_IMAGE_2_CRC:04X}", "ok" if post.ASW_IMAGE_2_CRC == 0x5C55 else "alarm"
    )
    set_chip_state(
        labels["post_asw3_crc"], f"0x{post.ASW_IMAGE_3_CRC:04X}", "ok" if post.ASW_IMAGE_3_CRC == 0x01CB else "alarm"
    )
    set_chip_state(
        labels["post_asw4_crc"], f"0x{post.ASW_IMAGE_4_CRC:04X}", "ok" if post.ASW_IMAGE_4_CRC == 0x5318 else "alarm"
    )
    set_chip_state(
        labels["post_asw5_crc"], f"0x{post.ASW_IMAGE_5_CRC:04X}", "ok" if post.ASW_IMAGE_5_CRC == 0xDCAE else "alarm"
    )
    set_chip_state(
        labels["post_bsw_crc"], f"0x{post.BSW_IMAGE_CRC:04X}", "ok" if post.BSW_IMAGE_CRC == 0xD2D7 else "alarm"
    )
    set_chip_state(
        labels["post_meas_table_crc"],
        f"0x{post.MEASUREMENT_TABLE_CRC:04X}",
        "ok" if post.MEASUREMENT_TABLE_CRC == 0x9D9B else "alarm",
    )

    all_post_passed = (
        post.POST_WARNING_FLAGS == 0
        and post.POST_ERROR_FLAGS == 0
        and post.NUM_BAD_FLASH_BLOCKS == 0
        and post.NUM_BAD_SRAM_BLOCKS == 0
        and post.ASW_IMAGE_1_CRC == 0xBAF7
        and post.ASW_IMAGE_2_CRC == 0x5C55
        and post.ASW_IMAGE_3_CRC == 0x01CB
        and post.ASW_IMAGE_4_CRC == 0x5318
        and post.ASW_IMAGE_5_CRC == 0xDCAE
        and post.BSW_IMAGE_CRC == 0xD2D7
        and post.MEASUREMENT_TABLE_CRC == 0x9D9B
    )
    if all_post_passed:
        labels["post_status"].set_text("POST TEST PASSED")
        labels["post_status"].style("color: green; font-weight: bold;")
    else:
        labels["post_status"].set_text("POST TEST FAILED")
        labels["post_status"].style("color: red; font-weight: bold;")

    ui.notify("POST validation complete", type="positive")
