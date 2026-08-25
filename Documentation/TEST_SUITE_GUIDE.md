# Unit Tests Guide - ENFYS OB EGSE

Complete reference guide explaining all four unit test files in the project.

---

## Quick Start

Run all tests:
```bash
uv run pytest -v
```

Run specific test file:
```bash
uv run pytest src/tests/test_[filename].py -v
```

Run specific test:
```bash
uv run pytest src/tests/test_[filename].py::test_[testname] -v
```

---

## File Overview

| File | Purpose | Key Concept |
|------|---------|-------------|
| `test_ui_mms_controller.py` | Emergency response system | Masking, latching, action sequencing |
| `test_ui_alarm_and_checks.py` | Alarm filtering & detection | OB vs EB flag filtering, deduplication |
| `test_monitoring_limit_conversions.py` | ADU ↔ Real value conversion | Voltage/temperature calibration accuracy |
| `test_eb_packet_flag_decoding.py` | Bit-level packet parsing | Bitstruct binary packing/unpacking |

---

# 1. test_ui_mms_controller.py

**Module:** `widget_modules.ui_runtime_controller` (urc)  
**System:** MMS (Maintenance Management System) - Emergency response to faults

## Helper: `_DummyLogger`

Mock logger that captures messages instead of printing:
```python
class _DummyLogger:
    def __init__(self) -> None:
        self.records = []
    
    def warning(self, msg, *args):
        self.records.append(("warning", msg % args if args else msg))
    # ... similar for info() and error()
```

Used to verify correct log messages without cluttering output.

---

## Test 1: `test_mms_reasons_masks_ob_general_error`

**Purpose:** Verify that OB (Optical Box) general errors are ignored when masking is enabled.

**Test Flow:**
1. Create fake housekeeping packet with `OB_GENERAL_ERROR=1`
2. Enable masking by setting `MMS_MASK_OB_GENERAL_ERROR = True`
3. Call `_mms_reasons()` to analyze the fault
4. Verify error is masked (not reported)

**Key Setup:**
```python
hk = SimpleNamespace(
    ERROR_FLAGS=1,
    ERROR_FLAGS_BITS=SimpleNamespace(OB_GENERAL_ERROR=1, RESERVED=0),
    # ... other fields
)
monkeypatch.setattr(urc.const, "MMS_MASK_OB_GENERAL_ERROR", True)
```

**Assertions:**
```python
assert reasons == []  # No alarm raised
assert tec_pre_action is False
assert ob5v_pre_action is False
```

---

## Test 2: `test_mms_reasons_adds_ob_error_details_even_without_active_bits`

**Purpose:** Even when individual error bits can't be decoded, include raw error codes in diagnostic output.

**Test Flow:**
1. Create hk packet with `OB_LAST_ERROR=0x10` and `OB_MOTOR_ERROR=0x04`
2. Set `ERROR_FLAGS_BITS=None` (no bits decoded)
3. Call `_mms_reasons()`
4. Verify raw error codes appear in reasons list

**Key Insight:**
Ensures you don't lose diagnostic information even if the specific fault bits aren't recognized.

**Assertions:**
```python
assert "OB_LAST_ERROR=0x10 (no active bits decoded)" in reasons
assert "OB_MOTOR_ERROR=0x04 (no active bits decoded)" in reasons
```

---

## Test 3: `test_mms_runs_actions_and_latches` (Main Emergency Test)

**Purpose:** Verify the complete MMS emergency response sequence runs in correct order.

**Context:** When a critical fault is detected (e.g., voltage out of limits), MMS must:
1. Stop the current script
2. Clear pause states
3. Disable power rails (if needed)
4. Put hardware in safe state
5. Lock the system (latch) to prevent re-triggering

**Test Setup - Mock 8 Functions:**
```python
calls = {
    "abort": 0,
    "clear_pause": 0,
    "clear_force_pause": 0,
    "disable_ob5v": 0,
    "safe": 0,
    "ret": 0,
    "shutdown": 0,
}
```

Each mocked function increments its counter when called.

**Test Execution:**
```python
asyncio.run(
    urc.mms(
        app=app,
        state=state,
        logger=logger,
        hk=hk,
        reasons=["EB +12V out of limits"],  # The fault detected
        tec_pre_action=True,   # Thermal control needs special handling
        ob5v_pre_action=True,  # OB 5V needs special handling
    )
)
```

**Action Sequence Verification:**
```python
# Each action called exactly once, in this order:
assert calls["abort"] == 1
assert calls["clear_pause"] == 1
assert calls["clear_force_pause"] == 1
assert calls["disable_ob5v"] == 1
assert calls["safe"] == 1
assert calls["ret"] == 1
assert calls["shutdown"] == 1
```

**Latching (Prevents Re-triggering):**
```python
mms_cfg = state["mms"]
assert mms_cfg["latched"] is True  # Can't trigger again
assert mms_cfg["in_progress"] is False  # No longer running
assert mms_cfg["tec_shutdown_requested"] is True  # Pre-action applied
assert mms_cfg["ob5v_disable_requested"] is True
assert mms_cfg["mode_at_trigger"] == "OB"  # Saved operation mode
```

**Why Latching Matters:**
Once triggered, MMS shouldn't trigger again on the same fault. The system is now locked waiting for manual intervention.

---

## Test 4: `test_mms_returns_early_when_latched`

**Purpose:** Confirm MMS won't execute twice on the same fault.

**Test Flow:**
1. Pre-set `state["mms"]["latched"] = True`
2. Call `mms()` function
3. Verify state unchanged

**Assertion:**
```python
assert state["mms"] == {"latched": True}
```

**Why This Matters:**
Safety - prevents cascading failure attempts.

---

# 2. test_ui_alarm_and_checks.py

**Module:** `widget_modules.ui_runtime_controller` (urc)  
**System:** Alarm detection and filtering - separates OB vs EB faults

## Helper: `_DummyLogger`

Same as above but stores in lists:
```python
self.warns = []  # warning messages
self.errors = []  # error messages
```

---

## Test 1: `test_ob_alarm_details_filter_only_ob_related_flags`

**Purpose:** Verify OB (Optical Box) alarm filtering extracts ONLY OB-related flags from the housekeeping packet.

**Test Data:**
```python
hk = SimpleNamespace(
    WARNING_FLAGS_BITS=SimpleNamespace(OB_UNRESPONSIVE=1, GENERAL_ERROR=1),
    FDIR_ALARM_FLAGS_BITS=SimpleNamespace(DIGITAL_BOARD_TRP=1, EB_PLUS_5V_SUPPLY=1),
    FDIR_WARNING_FLAGS_BITS=SimpleNamespace(MECH_BOARD_TRP=1, EB_TEC_SUPPLY=1),
    ERRORS=SimpleNamespace(IPI=1),
    MTR_ERRORS=SimpleNamespace(DSE=1),
)
```

**Call:**
```python
details = urc._ob_alarm_details(hk)
```

**Expected Filters:**

| Flag | Included? | Reason |
|------|-----------|--------|
| OB_UNRESPONSIVE | ✓ Yes | OB-specific warning |
| GENERAL_ERROR | ✗ No | Generic, not OB-specific |
| DIGITAL_BOARD_TRP (OB board) | ✓ Yes | OB hardware |
| EB_PLUS_5V_SUPPLY | ✗ No | EB power rail |
| MECH_BOARD_TRP (OB board) | ✓ Yes | OB hardware |
| EB_TEC_SUPPLY | ✗ No | EB thermal control |

**Assertions:**
```python
assert "OB Warning: OB_UNRESPONSIVE" in details
assert "OB Warning: GENERAL_ERROR" not in details  # Filtered out
assert "OB FDIR Alarm: DIGITAL_BOARD_TRP" in details
assert "OB FDIR Alarm: EB_PLUS_5V_SUPPLY" not in details  # EB flag, not OB
assert "OB FDIR Warning: MECH_BOARD_TRP" in details
assert "OB FDIR Warning: EB_TEC_SUPPLY" not in details  # EB flag
assert "OB Error flags active" in details  # Detects ERRORS field is set
assert "OB Motor error flags active" in details  # Detects MTR_ERRORS field is set
```

**Key Insight:** Filtering is critical - OB alarms shouldn't report EB problems and vice versa.

---

## Test 2: `test_eb_alarm_details_filter_only_eb_related_flags_and_tcs_rejected`

**Purpose:** Verify EB (Electronics Box) alarm filtering extracts ONLY EB-related flags AND includes TCS_REJECTED counter.

**Test Data:**
```python
hk = SimpleNamespace(
    TCS_REJECTED=2,  # TCS rejected this command 2 times
    WARNING_FLAGS_BITS=SimpleNamespace(GENERAL_ERROR=1, OB_UNRESPONSIVE=1),
    FDIR_ALARM_FLAGS_BITS=SimpleNamespace(EB_PLUS_5V_SUPPLY=1, MECH_BOARD_TRP=1),
    FDIR_WARNING_FLAGS_BITS=SimpleNamespace(PSU_BOARD_TEMPERATURE=1, MOTOR_TRP=1),
)
```

**Expected Filters (Inverse of OB):**

| Flag | Included? | Reason |
|------|-----------|--------|
| TCS_REJECTED | ✓ Yes | EB-specific counter |
| GENERAL_ERROR | ✓ Yes | Generic, but keep for EB |
| OB_UNRESPONSIVE | ✗ No | OB-specific warning |
| EB_PLUS_5V_SUPPLY | ✓ Yes | EB power rail |
| MECH_BOARD_TRP | ✗ No | OB board |
| PSU_BOARD_TEMPERATURE | ✓ Yes | EB power supply board |
| MOTOR_TRP | ✗ No | This is a motor trap (unclear context but filtered out) |

**Assertions:**
```python
assert "TCS Rejected: 2" in details
assert "EB Warning: GENERAL_ERROR" in details
assert "EB Warning: OB_UNRESPONSIVE" not in details
assert "EB FDIR Alarm: EB_PLUS_5V_SUPPLY" in details
assert "EB FDIR Alarm: MECH_BOARD_TRP" not in details
assert "EB FDIR Warning: PSU_BOARD_TEMPERATURE" in details
assert "EB FDIR Warning: MOTOR_TRP" not in details
```

---

## Test 3: `test_log_new_hk_alarm_details_logs_raise_once`

**Purpose:** Verify alarm log messages are raised only once, even if same details appear multiple times.

**Why:** Prevents log spam - if a problem persists, you don't want hundreds of duplicate "alarm raised" messages.

**Test Flow:**
```python
state = {}
logger = _DummyLogger()

# First call with alarm details
urc._log_new_hk_alarm_details(
    state,
    logger,
    channel="ob",
    details=["OB Warning: OB_UNRESPONSIVE", "OB FDIR Alarm: DIGITAL_BOARD_TRP"],
)
```

**First Call Assertions:**
```python
assert any("warning raised" in msg for msg in logger.warns)
assert any("alarm raised" in msg for msg in logger.errors)
```

**Second Call with Same Details:**
```python
warn_count = len(logger.warns)
error_count = len(logger.errors)

# Re-log same details
urc._log_new_hk_alarm_details(
    state,
    logger,
    channel="ob",
    details=["OB Warning: OB_UNRESPONSIVE", "OB FDIR Alarm: DIGITAL_BOARD_TRP"],
)

assert len(logger.warns) == warn_count  # No new messages
assert len(logger.errors) == error_count  # No new messages
```

**Key:** The state dict tracks which details were already logged. Identical details aren't logged twice.

---

## Test 4: `test_perform_hk_check_detects_non_zero_error_and_fdir_fields`

**Purpose:** Verify housekeeping check correctly detects when ERROR_FLAGS, FDIR_ALARM_FLAGS, and FDIR_WARNING_FLAGS are non-zero.

**Test Data:**
```python
hk = SimpleNamespace(
    ERROR_FLAGS=1,  # Should fail - not 0
    FDIR_ALARM_FLAGS=2,  # Should fail - not 0
    FDIR_WARNING_FLAGS=4,  # Should fail - not 0
    # ... other fields set to nominal values
)
```

**Call:**
```python
result = urc.perform_hk_check(hk=hk, hk_type="hk")
```

**Result Structure:**
```python
result = {
    "passed": False,  # Any flag non-zero = fail
    "details": [
        "ERROR_FLAGS not 0",
        "FDIR_ALARM_FLAGS not 0",
        "FDIR_WARNING_FLAGS not 0",
    ]
}
```

**Assertions:**
```python
assert result["passed"] is False
assert any("ERROR_FLAGS not 0" in detail for detail in result["details"])
assert any("FDIR_ALARM_FLAGS not 0" in detail for detail in result["details"])
assert any("FDIR_WARNING_FLAGS not 0" in detail for detail in result["details"])
```

**Key Insight:** These flags should always be 0 in nominal operation. Any non-zero value indicates a problem.

---

# 3. test_monitoring_limit_conversions.py

**Module:** `utility_modules`, `widget_modules.metrics_card_widget`, `core_modules.constants`  
**System:** Conversion between raw ADU (Analog-to-Digital Unit) values and physical units (Volts, Celsius)

## Key Concept: Why This Matters

Sensors output raw 16-bit ADU values (0-65535). These must be converted to meaningful units:
- **Voltage sensors:** ADU → Volts (e.g., 30000 ADU → 12.0V)
- **Temperature sensors:** ADU → Celsius (e.g., 40000 ADU → 25°C)

Conversions must be **accurate** - even small errors compound over time and can trigger false alarms.

---

## Helper: `_assert_decoded_pair_matches_limits`

Generic assertion helper that validates conversion accuracy:

```python
def _assert_decoded_pair_matches_limits(
    decoder: Callable[[int], float],  # Function that converts ADU to real value
    adu_bounds: tuple[int, int],      # ADU range (low, high)
    real_bounds: tuple[float, float],  # Expected real value range
    tol: float,                        # Maximum tolerance in real units
) -> None:
```

**Logic:**
1. Decode both ADU bounds
2. Find min/max of decoded values (handles non-monotonic functions)
3. Assert they match the expected real bounds within tolerance

```python
decoded_lo = decoder(lo_adu)
decoded_hi = decoder(hi_adu)
decoded_min = min(decoded_lo, decoded_hi)
decoded_max = max(decoded_lo, decoded_hi)

assert abs(decoded_min - real_lo) <= tol
assert abs(decoded_max - real_hi) <= tol
```

---

## Test 1: `test_linear_conversion_based_adu_limits_match_real_limits`

**Purpose:** Verify linear ADU-to-voltage conversions are accurate for all supplies.

**Parametrized Test** - Runs same test logic with different parameters:

```python
@pytest.mark.parametrize(
    ("field", "adu_bounds", "real_bounds", "tol"),
    [
        ("EB_MEAS_MAIN_12V", WLIM_EB_12V_ADU, WLIM_EB_12V, 0.002),
        ("EB_MEAS_MAIN_12V", ALIM_EB_12V_ADU, ALIM_EB_12V, 0.002),
        ("EB_MEAS_MAIN_NEG12V", WLIM_EB_NEG12V_ADU, WLIM_EB_NEG12V, 0.002),
        ("EB_MEAS_MAIN_NEG12V", ALIM_EB_NEG12V_ADU, ALIM_EB_NEG12V, 0.002),
        ("EB_MEAS_5V", WLIM_EB_5V_ADU, WLIM_EB_5V, 0.002),
        # ... 8 more parameter sets
    ],
)
```

| Field | Type | Warning Limits | Alarm Limits |
|-------|------|---|---|
| EB_MEAS_MAIN_12V | Voltage | 11.0-13.0V (WLIM) | 10.5-13.5V (ALIM) |
| EB_MEAS_MAIN_NEG12V | Voltage | -13.0 to -11.0V | -13.5 to -10.5V |
| EB_MEAS_5V | Voltage | 4.75-5.25V | 4.5-5.5V |
| EB_MEAS_3V3 | Voltage | 3.1-3.5V | 2.9-3.7V |
| OB_3V3_VOLTAGE | Voltage | 3.1-3.5V | 2.9-3.7V |
| OB_1V5_VOLTAGE | Voltage | 1.4-1.6V | 1.3-1.7V |
| EB_MCU_INTERNAL_TEMP | Temperature | ±0.02°C tolerance | |

**Test Logic:**
```python
conversion = hk_conversions.CONVERSIONS[field]
_assert_decoded_pair_matches_limits(
    conversion.convert,  # Decoder function
    adu_bounds,
    real_bounds,
    tol=0.002  # 2mV tolerance for voltages
)
```

**Why 0.002V (2mV) tolerance?**
- Accounts for quantization error in 16-bit ADC
- Accounts for rounding in conversion formula
- Ensures limits are tight enough to catch real problems

---

## Test 2: `test_ob_thermistor_adu_limits_match_real_limits`

**Purpose:** Verify OB thermistor ADU→temperature conversions are accurate.

**Parametrized Test:**
```python
@pytest.mark.parametrize(
    ("adu_bounds", "real_bounds", "tol"),
    [
        (WLIM_TPR_ADU, WLIM_TPR, 0.2),  # Warning limits
        (ALIM_TPR_ADU, ALIM_TPR, 0.2),  # Alarm limits
    ],
)
def test_ob_thermistor_adu_limits_match_real_limits(...):
    _assert_decoded_pair_matches_limits(adu_to_temp, adu_bounds, real_bounds, tol)
```

**Key Difference:** Temperature tolerance is **0.2°C** (not 0.002). Why?
- Thermistors are non-linear sensors
- Temperature measurement has inherent accuracy limits
- 0.2°C is acceptable for thermal monitoring

---

## Test 3: `test_eb_thermistor_adu_limits_match_real_limits`

**Purpose:** Verify EB internal thermistor conversions are accurate.

**Parametrized Test:**
```python
@pytest.mark.parametrize(
    ("adu_bounds", "real_bounds", "tol"),
    [
        (WLIM_EB_INTERNAL_TRP_TEMP_ADU, WLIM_EB_INTERNAL_TRP_TEMP, 0.2),
        (ALIM_EB_INTERNAL_TRP_TEMP_ADU, ALIM_EB_INTERNAL_TRP_TEMP, 0.2),
        (WLIM_EB_PSU_BOARD_TEMP_ADU, WLIM_EB_PSU_BOARD_TEMP, 0.2),
        (ALIM_EB_PSU_BOARD_TEMP_ADU, ALIM_EB_PSU_BOARD_TEMP, 0.2),
    ],
)
def test_eb_thermistor_adu_limits_match_real_limits(...):
    _assert_decoded_pair_matches_limits(decode_eb_trps, adu_bounds, real_bounds, tol)
```

---

## Test 4: `test_metrics_specs_are_wired_to_reference_limit_constants`

**Purpose:** Verify the UI metric display specs match the constant definitions.

**Why This Matters:** If code has two copies of limit values and they drift out of sync, the UI might show wrong limits or alarms won't trigger correctly.

**Test Structure:**
1. Get all EB and OB metric specs from the UI
2. For each field, verify specs match the constant definitions

**Example for EB 12V:**
```python
eb_specs = {spec.key: spec for spec in mcw._eb_hk_specs()}

# Check warning limits
assert eb_specs["eb_12v"].bounds == const.WLIM_EB_12V
assert eb_specs["eb_12v"].bounds_adu == const.WLIM_EB_12V_ADU

# Check alarm limits
assert eb_specs["eb_12v"].alarm_bounds == const.ALIM_EB_12V
assert eb_specs["eb_12v"].alarm_bounds_adu == const.ALIM_EB_12V_ADU
```

**All Checked Fields (EB):**
- eb_12v (±12V supply)
- eb_neg12v (-12V supply)
- eb_5v (+5V supply)
- eb_3v3 (+3.3V supply)
- eb_mcu_temp (MCU internal temperature)
- eb_internal_temp (Internal thermistor)
- eb_psu_temp (PSU board temperature)

**All Checked Fields (OB):**
- 3v3 (+3.3V supply)
- 1v5 (+1.5V supply)
- dig (Digital board thermistor)
- det (Detector board thermistor)
- mech (Mechanical board thermistor)
- mtr (Motor thermistor)

**Key Assertions:**
```python
# Each has 4 values: bounds, alarm_bounds, bounds_adu, alarm_bounds_adu
for key in ("dig", "det", "mech", "mtr"):
    assert ob_specs[key].bounds == const.WLIM_TPR
    assert ob_specs[key].alarm_bounds == const.ALIM_TPR
    assert ob_specs[key].bounds_adu == const.WLIM_TPR_ADU
    assert ob_specs[key].alarm_bounds_adu == const.ALIM_TPR_ADU
```

---

# 4. test_eb_packet_flag_decoding.py

**Module:** `utility_modules.eb_packet_utility`, `core_modules.tmstruct`  
**System:** Binary packet parsing - converts raw bytes into structured data with individual bit flags

## Key Concept: Bit-Level Decoding

EB housekeeping packets are binary structures. Flags are packed into single bytes using individual bits:
```
ERROR_FLAGS byte:  [bit0, bit1, bit2, bit3, bit4, bit5, bit6, bit7]
                    GEN   FDIR   OB_   RES   RES   RES   RES   RES
                    ERR   ALM    UNR
                    M     M      SP
```

Decoding must unpack these bits correctly into named fields.

---

## Helpers: Bit Packing Functions

### `_pack_flags(flag_struct, active_names)`

Packs named flags into a raw byte:

```python
def _pack_flags(flag_struct: list[tuple[str, str]], active_names: set[str]) -> int:
    # flag_struct: list of (name, bitstruct_format) tuples
    # active_names: which flags should be set to 1
    
    names = [name for name, _ in flag_struct]
    fmt = "".join(spec for _, spec in flag_struct)
    raw = bitstruct.pack_dict(fmt, names, {
        name: 1 if name in active_names else 0 
        for name in names
    })
    return int.from_bytes(raw, "big")
```

**Example:**
```python
flag_struct = [
    ("GENERAL_ERROR", "u1"),
    ("OB_GENERAL_ERROR", "u1"),
]
active_names = {"GENERAL_ERROR", "OB_GENERAL_ERROR"}
byte_value = _pack_flags(flag_struct, active_names)  # 0b11000000 = 0xC0
```

### `_make_hk_packet(**overrides)`

Creates a complete housekeeping packet with specified field values:

```python
def _make_hk_packet(**overrides) -> bytes:
    # Start with all fields zeroed
    # Override specific fields
    # Pack into binary format
```

---

## Test 1: `test_parse_eb_hk_decodes_warning_error_and_fdir_bitmaps`

**Purpose:** Verify packet parsing correctly decodes all four flag bytes into individual named bits.

**Test Setup - Create packet with specific flags active:**
```python
warning_bits = {"GENERAL_ERROR", "OB_GENERAL_ERROR", "RS422_TRANSMIT_ERROR"}
error_bits = {"GENERAL_ERROR", "EB_FDIR_ALARM"}
fdir_alarm_bits = {"EB_PLUS_12V_SUPPLY", "DIGITAL_BOARD_TRP"}
fdir_warning_bits = {"EB_TEC_SUPPLY", "FPGA_CORE_POWER_SUPPLY"}

packet = _make_hk_packet(
    WARNING_FLAGS=_pack_flags(tmstruct.eb_warning_flags, warning_bits),
    ERROR_FLAGS=_pack_flags(tmstruct.eb_warning_flags, error_bits),
    FDIR_ALARM_FLAGS=_pack_flags(tmstruct.eb_fdir_flags, fdir_alarm_bits),
    FDIR_WARNING_FLAGS=_pack_flags(tmstruct.eb_fdir_flags, fdir_warning_bits),
)
```

**Parse the packet:**
```python
hk = eb_packet_utility.parse_eb_hk(packet)
```

**Verify WARNING_FLAGS decoded correctly:**
```python
assert hk.WARNING_FLAGS_BITS.GENERAL_ERROR == 1
assert hk.WARNING_FLAGS_BITS.OB_GENERAL_ERROR == 1
assert hk.WARNING_FLAGS_BITS.RS422_TRANSMIT_ERROR == 1
assert hk.WARNING_FLAGS_BITS.RESERVED == 0
```

**Verify ERROR_FLAGS decoded correctly:**
```python
assert hk.ERROR_FLAGS_BITS.GENERAL_ERROR == 1
assert hk.ERROR_FLAGS_BITS.EB_FDIR_ALARM == 1
assert hk.ERROR_FLAGS_BITS.OB_UNRESPONSIVE == 0  # Not set
```

**Verify FDIR_ALARM_FLAGS decoded correctly:**
```python
assert hk.FDIR_ALARM_FLAGS_BITS.EB_PLUS_12V_SUPPLY == 1
assert hk.FDIR_ALARM_FLAGS_BITS.DIGITAL_BOARD_TRP == 1
assert hk.FDIR_ALARM_FLAGS_BITS.EB_PLUS_5V_SUPPLY == 0  # Not set
```

**Verify FDIR_WARNING_FLAGS decoded correctly:**
```python
assert hk.FDIR_WARNING_FLAGS_BITS.EB_TEC_SUPPLY == 1
assert hk.FDIR_WARNING_FLAGS_BITS.FPGA_CORE_POWER_SUPPLY == 1
assert hk.FDIR_WARNING_FLAGS_BITS.MECH_BOARD_TRP == 0  # Not set
```

---

## Test 2: `test_parse_eb_hk_decodes_ongoing_process_flags_with_any_bit`

**Purpose:** Verify special "ANY" flag is set when ANY bit in the field is set.

**Test Setup:**
```python
packet = _make_hk_packet(ONGOING_PROCESS_FLAGS=0b1001)
# Bits 0 and 3 are set
```

**Parse:**
```python
hk = eb_packet_utility.parse_eb_hk(packet)
```

**Assertions:**
```python
assert hk.ONGOING_PROCESS_FLAGS_BITS.BIT_0 == 1  # Explicitly set
assert hk.ONGOING_PROCESS_FLAGS_BITS.BIT_3 == 1  # Explicitly set
assert hk.ONGOING_PROCESS_FLAGS_BITS.BIT_1 == 0  # Not set
assert hk.ONGOING_PROCESS_FLAGS_BITS.ANY == 1    # At least one bit is set
```

**Why "ANY" Flag?**
Convenience - code can check if ANY process is ongoing without checking individual bits.

---

## Test 3: `test_parse_eb_hk_ongoing_process_any_clears_when_zero`

**Purpose:** Verify "ANY" flag correctly clears when all bits are zero.

**Test Setup:**
```python
packet = _make_hk_packet(ONGOING_PROCESS_FLAGS=0)  # All bits zero
```

**Parse:**
```python
hk = eb_packet_utility.parse_eb_hk(packet)
```

**Assertion:**
```python
assert hk.ONGOING_PROCESS_FLAGS_BITS.ANY == 0
```

**Key:** "ANY" is computed dynamically from the individual bits, not stored separately.

---

## Summary

| Test File | What It Tests | Key Technique |
|-----------|---------------|---|
| `test_ui_mms_controller.py` | Emergency response system | Mocking with monkeypatch, async testing |
| `test_ui_alarm_and_checks.py` | Alarm filtering logic | Multiple test cases validating filters |
| `test_monitoring_limit_conversions.py` | ADU↔real conversions | Parametrized tests, accuracy validation |
| `test_eb_packet_flag_decoding.py` | Binary packet parsing | Bit packing/unpacking, flag verification |

---

## Running Examples

**All tests:**
```bash
uv run pytest -v
```

**Just monitoring limits:**
```bash
uv run pytest src/tests/test_monitoring_limit_conversions.py -v
```

**Just one parametrized case:**
```bash
uv run pytest src/tests/test_monitoring_limit_conversions.py::test_linear_conversion_based_adu_limits_match_real_limits -v -k "EB_MEAS_MAIN_12V"
```

**With print statements visible:**
```bash
uv run pytest src/tests/test_ui_mms_controller.py -v -s
```

**Stop on first failure:**
```bash
uv run pytest src/tests/ -v -x
```

