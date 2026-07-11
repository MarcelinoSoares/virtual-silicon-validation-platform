# Test Strategy

## Scope

All virtual chip components — registers, SRAM, I2C/SPI protocols, instruments,
fault injection, database persistence, analytics, and reporting.

## Objectives

1. Verify correct register behavior for all access types and bit widths
2. Validate SRAM test pattern coverage and fault detection capability
3. Confirm protocol simulation correctness and fault handling
4. Ensure instrument measurements are within configured tolerances
5. Validate fault injection triggers and effects
6. Verify database persistence integrity
7. Confirm report generation produces valid HTML/CSV/JSON artifacts

## Risks

| Risk | Mitigation |
|------|-----------|
| Non-deterministic test failures | Fixed random seeds in all fixtures |
| Floating-point tolerance | Use range assertions, not equality |
| Database state pollution | In-memory SQLite per test |
| Missing fault detection | Explicit fault → test → assert pattern |
| Slow performance tests | Time budget assertions with generous limits |

## Test Levels

### Unit Tests (`tests/unit/`)
- Isolated tests of individual classes
- No database, no file I/O
- All randomness seeded
- Target: every public method

### Integration Tests (`tests/integration/`)
- Multi-component interactions
- In-memory database for persistence tests
- Real chip + protocol interaction

### System Tests (`tests/system/`)
- Full end-to-end validation flow
- Powers on chip, runs all tests, injects faults, generates reports
- Uses `tmp_path` for file artifacts

### Performance Tests (`tests/performance/`)
- Time-bounded assertions on SRAM test operations
- Verify throughput under realistic workloads

## Test Types

| Type | Marker | Description |
|------|--------|-------------|
| Unit | `@pytest.mark.unit` | Single-class isolation |
| Integration | `@pytest.mark.integration` | Multi-component |
| System | `@pytest.mark.system` | Full E2E flow |
| Performance | `@pytest.mark.performance` | Timing assertions |
| Memory | `@pytest.mark.memory` | SRAM-specific |
| Protocol | `@pytest.mark.protocol` | I2C/SPI |
| Fault | `@pytest.mark.fault` | Fault injection |

## Entry Criteria

- All source modules compile without import errors
- `pytest` is installed with all dependencies
- No physical hardware required

## Exit Criteria

- All tests pass (no FAIL/ERROR)
- Code coverage ≥ 85%
- No Ruff lint errors
- Mypy reports no type errors

## Defect Severity

| Severity | Definition |
|----------|-----------|
| Critical | Incorrect device ID, SRAM data corruption undetected |
| High | Protocol transaction fails silently |
| Medium | Fault not triggering at configured cycle |
| Low | Measurement noise outside tolerance |

## Automation Strategy

1. GitHub Actions runs on every push and PR
2. Ruff linting → Mypy type check → unit → integration → system → coverage
3. Artifacts: coverage HTML, validation HTML/CSV/JSON
4. Deterministic execution via fixed seeds (no flaky tests)

## Traceability

| Requirement | Test File | Marker |
|-------------|-----------|--------|
| Register read/write | test_registers.py | unit |
| SRAM patterns | test_memory.py | unit, memory |
| I2C simulation | test_i2c.py | unit, protocol |
| SPI simulation | test_spi.py | unit, protocol |
| Instruments | test_instruments.py | unit |
| Fault injection | test_fault_injection.py | unit, fault |
| Chip init | test_chip_initialization.py | integration |
| Power sequence | test_power_sequence.py | integration |
| Full flow | test_full_validation_flow.py | integration |
| E2E | test_end_to_end_validation.py | system |
| Performance | test_memory_performance.py | performance |
