def com_port_name(port_number: int) -> str:
    return f"COM{port_number}"


def validate_com_port_selection(ob_com: str, psu_com: str, *, nopsu: bool = False) -> None:
    if nopsu:
        return
    if ob_com.strip().upper() == psu_com.strip().upper():
        raise SystemExit(f"OB and PSU COM ports must be different; both were set to {ob_com}.")