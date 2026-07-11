# Architecture

## Overview

The Virtual Silicon Validation Platform follows a layered, modular architecture
with clear separation of concerns and unidirectional dependency flow.

```
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

## Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `device.Register` | Single register with access control, bit masking, field extraction |
| `device.RegisterMap` | Address-indexed collection of all chip registers |
| `device.SRAM` | 256-byte virtual SRAM with 9 test patterns |
| `device.VirtualChip` | Integrates RegisterMap + SRAM; power, cycle tracking, fault callbacks |
| `protocols.I2CBus` | I2C register read/write with fault injection and transaction log |
| `protocols.SPIBus` | SPI full-duplex transfer with fault injection and transaction log |
| `instruments.*` | Power supply, multimeter, temperature, and spectrometer simulations |
| `faults.*` | YAML-driven fault model configuration and injection dispatcher |
| `database.*` | SQLAlchemy ORM models, session management, repository pattern |
| `analytics.*` | Pandas-based metrics and Matplotlib chart generation |
| `configuration.Settings` | Pydantic-Settings environment-based configuration |
| `cli` | Typer CLI with rich output |
| `api.main` | FastAPI REST endpoints |

## Dependency Direction

```
CLI/API → Analytics → Database
CLI/API → Faults → Device
CLI/API → Instruments
CLI/API → Protocols → Device
Tests → All layers (via conftest fixtures)
```

Dependencies always point inward toward the domain (`device`).
The `device` layer has no dependencies on protocols, instruments, or database.

## Data Flow

1. **Test Execution**: `VirtualChip.power_on()` → register reset + SRAM clear
2. **Protocol Access**: `I2CBus.write_register()` → `RegisterMap.write()` → `Register.write()`
3. **Fault Injection**: `FaultInjector.apply_to_chip()` → `SRAM.inject_stuck_bit()` or callback
4. **Persistence**: `TestRepository.save_test_result()` → `Session` → SQLite
5. **Reporting**: `TestAnalyzer.summarize()` → `ReportGenerator.generate_all()` → HTML/CSV/JSON

## Protocol Abstraction

Both `I2CBus` and `SPIBus` operate on a shared `RegisterMap` instance,
allowing the same register state to be accessed through either protocol —
mirroring real silicon where I2C and SPI share the same register space.

## Database Flow

```
TestRun (1) ──< TestCase (N) ──< TestResult (N)
TestRun (1) ──< Measurement (N)
TestRun (1) ──< FaultEvent (N)
TestRun (1) ──< ProtocolTransaction (N)
```

## Report Generation Flow

```
TestRepository → TestAnalyzer → AnalyticsSummary
AnalyticsSummary → ReportGenerator → HTML + CSV + JSON + charts/
```
