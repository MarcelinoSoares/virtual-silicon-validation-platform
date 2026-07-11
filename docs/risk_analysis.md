# Risk Analysis

## Risk Register

| ID | Risk | Probability | Impact | Priority | Mitigation | Related Tests |
|----|------|-------------|--------|----------|-----------|---------------|
| R01 | Incorrect register configuration (wrong reset value, size, or access type) | Medium | High | High | Reset value assertions on power-on; access type negative tests | test_registers.py, test_chip_initialization.py |
| R02 | SRAM data corruption (stuck bit goes undetected) | Low | Critical | Critical | 9 independent test patterns; fault injection + detection assertion | test_memory.py, test_fault_injection.py |
| R03 | Unstable power supply causing out-of-tolerance voltage | Medium | High | High | Voltage range assertions; voltage drop fault + detection | test_power_sequence.py, test_instruments.py |
| R04 | I2C communication timeout (intermittent fault) | Medium | Medium | Medium | Timeout fault injection; probabilistic fault config; transaction log | test_i2c.py, test_fault_injection.py |
| R05 | SPI data corruption (corrupted response undetected) | Low | High | High | SPI corruption fault injection; read-back verification | test_spi.py, test_fault_injection.py |
| R06 | Overheating (temperature exceeds safe threshold) | Low | High | High | Overheat injection; InstrumentMeasurementError assertion | test_instruments.py |
| R07 | Silent data corruption (wrong value written/read without error) | Low | Critical | Critical | March C- test; walking ones/zeros; data retention | test_memory.py |
| R08 | Intermittent failures (non-deterministic test outcomes) | Medium | High | High | Fixed random seeds in all fixtures | conftest.py |
| R09 | Invalid firmware state after reset | Low | High | High | Power-off/on reset validation; register snapshot comparison | test_chip_initialization.py |
| R10 | Database persistence failure (lost test results) | Low | Medium | Medium | In-memory SQLite test isolation; repository save + query assertions | test_full_validation_flow.py |
| R11 | Report generation failure (malformed HTML/CSV/JSON) | Low | Low | Low | E2E test checks file existence; JSON schema validation | test_end_to_end_validation.py |
| R12 | Protocol address collision (I2C/SPI targeting wrong register) | Medium | High | High | Interoperability test: I2C write → SPI read | test_full_validation_flow.py |

## Risk Heat Map

```
Impact →  LOW    MEDIUM   HIGH    CRITICAL
Prob ↓
HIGH      R11     R08      R03      —
MEDIUM     —      R04      R01      R02
LOW       R10      —       R06, R09 R07
```

## Priority 1 Risks (Critical)

**R02 — SRAM Data Corruption**
- Undetected stuck bits can cause incorrect program execution in real silicon
- Mitigated by 9 independent SRAM test patterns, each targeting different failure modes
- Fault injection + detection test validates the detection pipeline end-to-end

**R07 — Silent Data Corruption**
- Data written correctly but read incorrectly, or vice versa
- March C- specifically designed for coupling faults
- Walking ones/zeros detect bit-level stuck faults

## Priority 2 Risks (High)

**R01 — Register Misconfiguration**
- A wrong reset value or access type could mask real failures
- Addressed by explicit reset value assertions and negative tests for RO/WO access

**R12 — Protocol Cross-contamination**
- I2C write to register X followed by SPI read of register Y
- Addressed by interoperability test that writes via I2C and reads via SPI
