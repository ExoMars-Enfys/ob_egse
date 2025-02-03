# List of available CMD IDs and response types using
# names according to OB-EB Data ICD

cmd_ids = {
    0x00: "HK_Request",
    0x01: "Clear_Errors",
    0x02: "Set_Errors",
    0x04: "Power_Control",
    0x05: "Heater_Control",
    0x06: "Set_Mech_SP",
    0x07: "Set_Detec_SP",
    0x0A: "Set_MTR_Param",
    0x0B: "Set_MTR_Guard",
    0x0C: "Set_MTR_Mon",
    0x0D: "Set_MTR_Err_Mask",
    0x10: "MTR_Mov_Pos",
    0x11: "MTR_Mov_Neg",
    0x12: "MTR_Mov_ABS",
    0x13: "MTR_Homing",
    0x15: "MTR_Halt",
    0x18: "Set_SWIR_Offset",
    0x19: "Set_MWIR_Offset",
    0x1B: "Set_HK_Samples",
    0x1E: "NACK",
    0x1F: "SCI_Request",
}
