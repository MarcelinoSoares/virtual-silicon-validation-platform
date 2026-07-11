# Troubleshooting Guide

## Common Issues

### Import errors on `virtual_silicon`

**Symptom:** `ModuleNotFoundError: No module named 'virtual_silicon'`

**Fix:**
```bash
pip install -e .
# or
pip install -e ".[dev]"
```
Ensure you run this from the repository root (where `pyproject.toml` is).

---

### Tests fail with `DeviceNotPoweredError`

**Symptom:** Tests raise `DeviceNotPoweredError` unexpectedly.

**Fix:** Ensure your test uses the `virtual_chip` fixture (which calls `power_on()`),
not `unpowered_chip`. Or call `chip.power_on()` before operations.

---

### `MemoryValidationError: Address N out of range`

**Symptom:** SRAM tests fail with address out of range.

**Fix:** Default SRAM is 256 bytes (addresses 0–255). Check that test addresses
stay within `[0, sram.size - 1]`. If you need larger SRAM, pass `sram_size=4096`
to `VirtualChip`.

---

### Fault injection has no effect on SRAM tests

**Symptom:** Fault applied but memory tests still pass.

**Possible causes:**
1. Fault `probability` is less than 1.0 and the RNG skipped it.
2. `trigger_after_cycles` threshold not yet reached.
3. The stuck bit is at an address not exercised by the failing test.

**Fix:** Set `probability: 1.0` and `trigger_after_cycles: 0`, and use an
address that the walking-ones test will exercise (e.g. address 0, bit 0).

---

### Ruff linting fails in CI

**Symptom:** `ruff check src/ tests/` reports errors.

**Fix:**
```bash
ruff check src/ tests/ --fix   # auto-fix safe issues
ruff format src/ tests/        # fix formatting
```

---

### Mypy type errors on `Optional` or `dict`

**Symptom:** Mypy reports incompatible types in repository or instrument code.

**Fix:** Ensure Python 3.12 is active (`python --version`). Mypy is configured
for `python_version = "3.12"` in `pyproject.toml`.

---

### Database locked error

**Symptom:** `sqlite3.OperationalError: database is locked`

**Fix:** Only one process should write to `virtual_silicon.db` at a time.
For parallel test execution, use in-memory databases:
```python
db = DatabaseSession("sqlite:///:memory:")
```

---

### `coverage fail_under` threshold not met

**Symptom:** Coverage run exits with `FAIL Required test coverage of 85% not reached`.

**Fix:** Check which modules have low coverage:
```bash
pytest tests/ --cov=virtual_silicon --cov-report=term-missing
```
Focus on untested public methods in the modules listed.

---

### Docker build fails

**Symptom:** Docker build errors on dependency installation.

**Fix:**
```bash
docker compose build --no-cache
# or pull fresh base image
docker pull python:3.12-slim
docker compose build
```

---

### API returns 409 "Chip is not powered on"

**Symptom:** Calls to `/chip/registers` return 409.

**Fix:** First call `POST /chip/power` to power on the chip, then access registers.

---

## Debug Logging

Enable verbose logging:
```bash
export VSVP_LOG_LEVEL=DEBUG
python -m virtual_silicon.cli run-tests
```

Logs are written to `logs/virtual-silicon.log`.

---

## Running a Specific Test in Isolation

```bash
pytest tests/unit/test_memory.py::TestMemoryPatterns::test_walking_ones_passes -v
```

## Verifying the Installation

```bash
python -c "from virtual_silicon.device.virtual_chip import VirtualChip; c = VirtualChip(); c.power_on(); print('OK', c.get_device_id())"
```

Expected output: `OK 165`
