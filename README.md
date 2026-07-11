# Virtual Silicon Validation Platform

A Python-based IC validation platform that simulates chip hardware — registers, SRAM, I2C/SPI buses, instruments, and fault injection — without any physical device.

Designed for learning, interview portfolios, and prototyping validation workflows that mirror real silicon bring-up.

---

## Features

- **Register simulation** — 10 named registers with configurable access control (RO/RW), bit-width (8/16-bit), and reset values
- **SRAM testing** — 256-byte virtual SRAM with 9 built-in test patterns (walking ones/zeros, checkerboard, March C−, data retention, and more)
- **Protocol buses** — I2C and SPI simulation sharing the same register map, with probabilistic fault injection and transaction logs
- **Fault injection** — YAML-driven fault configurations for stuck bits, bit flips, voltage drops, overheating, I2C timeouts, and SPI corruption
- **Instruments** — Power supply, multimeter, temperature sensor, and spectrometer simulations with configurable noise and tolerance
- **Database persistence** — SQLAlchemy ORM (SQLite) storing test runs, cases, results, measurements, fault events, and protocol transactions
- **Analytics & reports** — Pandas-based metrics, Matplotlib charts, and HTML/CSV/JSON report generation
- **REST API** — FastAPI endpoints for chip control, register access, test execution, and result retrieval
- **CLI** — Typer-based CLI with rich table output
- **C firmware simulator** — Optional portable C reference implementation in `firmware_simulator/`

---

## Architecture

```text
┌───────────────────────────────────────────────────┐
│                  CLI / REST API                    │
│           (virtual_silicon.cli / .api)             │
├───────────────────────────────────────────────────┤
│                    Scripts                         │
│        run_validation / generate_report            │
├────────────────┬─────────────────┬────────────────┤
│   Analytics    │   Fault Inject  │  Configuration │
│  (analyzer,    │  (fault_models, │  (settings.py) │
│   report_gen)  │  fault_injector)│                │
├────────────────┴─────────────────┴────────────────┤
│                  Instruments                       │
│  PowerSupply / Multimeter / TempSensor / Spectro  │
├────────────────────┬──────────────────────────────┤
│    Protocols       │         Database              │
│  I2CBus / SPIBus   │  models / repo / session      │
├────────────────────┴──────────────────────────────┤
│                  Virtual Device                    │
│    VirtualChip / RegisterMap / Register / SRAM     │
└───────────────────────────────────────────────────┘
```

Dependencies always flow inward. The `device` layer has no dependencies on protocols, instruments, or the database. See [docs/architecture.md](docs/architecture.md) for the full breakdown.

---

## Quick Start

**Requirements:** Python 3.12+

```bash
git clone https://github.com/marcelinodeoliveira91/virtual-silicon-validation-platform.git
cd virtual-silicon-validation-platform

python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Verify the installation:

```bash
python -c "from virtual_silicon.device.virtual_chip import VirtualChip; c = VirtualChip(); c.power_on(); print('OK', c.get_device_id())"
# Expected: OK 165
```

---

## CLI

```bash
virtual-silicon --help
```

| Command | Description |
| ------- | ----------- |
| `initialize` | Initialize the chip and create database tables |
| `run-tests` | Run all chip tests (registers + SRAM) |
| `run-memory-tests` | Run only the SRAM test suite |
| `inject-fault` | Inject faults from a YAML config file |
| `generate-report` | Generate HTML, CSV, and JSON reports |
| `reset-chip` | Reset the chip to its power-on state |
| `show-registers` | Display all register values in a table |

Example workflow:

```bash
virtual-silicon initialize
virtual-silicon run-tests
virtual-silicon inject-fault --config configs/faults.yaml
virtual-silicon generate-report
```

---

## REST API

Start the server:

```bash
uvicorn virtual_silicon.api.main:app --reload --host 0.0.0.0 --port 8000
# Interactive docs: http://localhost:8000/docs
```

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| `GET` | `/health` | Health check |
| `GET` | `/chip/status` | Chip power state and cycle count |
| `POST` | `/chip/power` | Power on the chip |
| `POST` | `/chip/reset` | Reset the chip |
| `GET` | `/chip/registers` | Read all registers |
| `GET` | `/chip/registers/{address}` | Read a single register |
| `POST` | `/chip/registers/{address}` | Write a register |
| `POST` | `/tests/run` | Run all chip tests |
| `POST` | `/faults/inject` | Inject a fault |
| `GET` | `/results` | Retrieve stored test results |
| `GET` | `/reports/latest` | Get the latest generated report |

---

## Register Map

| Address | Name | Access | Reset | Width |
| ------- | ---- | ------ | ----- | ----- |
| `0x00` | `DEVICE_ID` | RO | `0xA5` | 8-bit |
| `0x01` | `DEVICE_STATUS` | RO | `0x00` | 8-bit |
| `0x02` | `POWER_CONTROL` | RW | `0x00` | 8-bit |
| `0x03` | `TEMPERATURE` | RO | `0x19` | 8-bit |
| `0x04` | `VOLTAGE_LEVEL` | RO | `0x0C80` | 16-bit |
| `0x06` | `CURRENT_LEVEL` | RO | `0x0064` | 16-bit |
| `0x08` | `DISPLAY_CONFIG` | RW | `0x80` | 8-bit |
| `0x09` | `ERROR_FLAGS` | RW | `0x00` | 8-bit |
| `0x0A` | `FIRMWARE_VERSION` | RO | `0x0100` | 16-bit |
| `0x0C` | `INTERRUPT_STATUS` | RW | `0x00` | 8-bit |

---

## Running Tests

```bash
# All tests
pytest tests/

# By layer
make test-unit
make test-integration
make test-system
make test-performance

# By marker
pytest tests/ -m fault
pytest tests/ -m "protocol or memory"

# With coverage (must be explicit)
pytest tests/ --cov=virtual_silicon --cov-report=term-missing
```

Coverage threshold: **85%** (enforced via `pyproject.toml`).

All tests are deterministic — random seeds are fixed in fixtures. No physical hardware required.

See [docs/test_strategy.md](docs/test_strategy.md) for the full test strategy and traceability matrix.

---

## Fault Configuration

Faults are defined in `configs/faults.yaml`. Only entries with `enabled: true` are loaded.

```yaml
- name: SRAM_STUCK_BIT_LOW
  type: stuck_bit
  enabled: true
  target: sram
  address: 0
  bit_position: 0
  probability: 1.0
  trigger_after_cycles: 0
```

Available fault types: `stuck_bit`, `bit_flip`, `voltage_drop`, `overheat`, `i2c_timeout`, `spi_corruption`.

---

## Docker

```bash
# Build
docker compose build

# Run tests
docker compose run --rm test

# Start API server
docker compose up api

# Run full validation
docker compose run --rm validate
```

---

## Make Targets

```bash
make install        # Install in editable mode with dev extras
make test           # Run all tests
make lint           # Ruff lint check
make lint-fix       # Auto-fix lint issues
make typecheck      # Mypy type check
make coverage       # Tests with HTML coverage report
make validate       # Run full validation script
make report         # Generate reports
make api            # Start the API server
make seed           # Seed the database with sample data
make clean          # Remove caches, build artifacts, and temp DBs
make ci             # lint → typecheck → test → coverage
```

---

## Project Structure

```text
virtual-silicon-validation-platform/
├── src/virtual_silicon/
│   ├── device/          # VirtualChip, RegisterMap, Register, SRAM
│   ├── protocols/       # I2CBus, SPIBus
│   ├── instruments/     # PowerSupply, Multimeter, TempSensor, Spectrometer
│   ├── faults/          # FaultInjector, FaultConfig, fault models
│   ├── database/        # ORM models, session, repository
│   ├── analytics/       # TestAnalyzer, ReportGenerator
│   ├── configuration/   # Pydantic Settings
│   ├── api/             # FastAPI app and routes
│   └── cli.py           # Typer CLI
├── tests/
│   ├── unit/            # Isolated class tests
│   ├── integration/     # Multi-component tests
│   ├── system/          # End-to-end flow tests
│   └── performance/     # Timing assertions
├── configs/             # faults.yaml and other config files
├── scripts/             # run_validation.py, generate_report.py, seed_database.py
├── firmware_simulator/  # Optional C reference implementation
├── docs/                # Architecture, test strategy, risk analysis, troubleshooting
├── Makefile
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## Documentation

| Document | Description |
| -------- | ----------- |
| [docs/architecture.md](docs/architecture.md) | Layer diagram, data flow, component responsibilities |
| [docs/test_strategy.md](docs/test_strategy.md) | Test levels, markers, traceability matrix |
| [docs/risk_analysis.md](docs/risk_analysis.md) | Risk register and heat map |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common errors and fixes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, code standards, PR process |
| [firmware_simulator/README.md](firmware_simulator/README.md) | C reference build and run |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
