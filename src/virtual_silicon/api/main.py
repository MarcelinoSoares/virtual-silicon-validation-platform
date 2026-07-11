"""FastAPI REST API for virtual silicon chip interaction and test execution."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from virtual_silicon.configuration.settings import get_settings
from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import get_session
from virtual_silicon.device.register import InvalidRegisterAddressError, RegisterAccessError
from virtual_silicon.device.virtual_chip import DeviceNotPoweredError, VirtualChip

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="Virtual Silicon Validation Platform API",
    description="REST API for virtual chip interaction, test execution, and result retrieval.",
    version="1.0.0",
)

# Module-level chip and repository (production singleton pattern)
_chip: VirtualChip | None = None
_repo: TestRepository | None = None


def _get_chip() -> VirtualChip:
    global _chip
    if _chip is None:
        _chip = VirtualChip(sram_size=settings.sram_size_bytes, seed=settings.random_seed)
    return _chip


def _get_repo() -> TestRepository:
    global _repo
    if _repo is None:
        db = get_session(settings.database_url)
        _repo = TestRepository(db)
    return _repo


# ── Request / Response Models ──────────────────────────────────────────────


class RegisterWriteRequest(BaseModel):
    """Request body for a register write."""
    value: int


class TestRunRequest(BaseModel):
    """Request body to start a test run."""
    categories: list[str] = []
    seed: int | None = None


class FaultInjectRequest(BaseModel):
    """Request body to inject a fault."""
    fault_type: str
    address: int | None = None
    bit: int | None = None
    value: int | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": settings.project_name}


@app.get("/chip/status")
def chip_status() -> dict[str, Any]:
    """Return the current chip health status."""
    chip = _get_chip()
    return chip.get_health_status()


@app.get("/chip/registers")
def list_registers() -> dict[str, Any]:
    """Return a snapshot of all register values."""
    chip = _get_chip()
    if not chip.powered:
        raise HTTPException(status_code=409, detail="Chip is not powered on.")
    return chip.get_register_snapshot()


@app.get("/chip/registers/{address}")
def read_register(address: int) -> dict[str, Any]:
    """Read a single register by address."""
    chip = _get_chip()
    try:
        value = chip.read_register(address)
        return {"address": address, "value": value, "hex": hex(value)}
    except DeviceNotPoweredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (InvalidRegisterAddressError, RegisterAccessError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/chip/registers/{address}")
def write_register(address: int, body: RegisterWriteRequest) -> dict[str, Any]:
    """Write a value to a register by address."""
    chip = _get_chip()
    try:
        chip.write_register(address, body.value)
        return {"address": address, "written": body.value, "status": "ok"}
    except DeviceNotPoweredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (InvalidRegisterAddressError, RegisterAccessError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/chip/reset")
def reset_chip() -> dict[str, str]:
    """Reset the chip to default state."""
    chip = _get_chip()
    chip.reset()
    return {"status": "reset", "message": "Chip registers and SRAM reset."}


@app.post("/chip/power")
def power_on_chip() -> dict[str, str]:
    """Power on the chip."""
    chip = _get_chip()
    chip.power_on()
    return {"status": "powered_on"}


@app.post("/tests/run")
def run_tests(body: TestRunRequest) -> dict[str, Any]:
    """Execute chip memory tests and return results."""
    chip = _get_chip()
    if not chip.powered:
        raise HTTPException(status_code=409, detail="Chip must be powered on before running tests.")
    results = chip.run_memory_tests()
    return {
        "execution_id": str(uuid.uuid4()),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "results": [
            {
                "test_name": r.test_name,
                "status": r.status.value,
                "duration_ms": round(r.duration * 1000, 3),
                "error": r.error_message,
            }
            for r in results
        ],
    }


@app.post("/faults/inject")
def inject_fault(body: FaultInjectRequest) -> dict[str, Any]:
    """Inject a fault into the virtual chip."""
    chip = _get_chip()
    from virtual_silicon.faults.fault_models import FaultType
    try:
        ft = FaultType(body.fault_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown fault type: {body.fault_type}") from exc

    if ft == FaultType.STUCK_BIT and body.address is not None and body.bit is not None:
        chip.sram.inject_stuck_bit(body.address, body.bit, body.value or 1)
        return {"status": "injected", "fault_type": ft.value, "address": body.address}

    return {"status": "no_action", "detail": "Fault type requires chip-level configuration."}


@app.get("/results")
def get_results(execution_id: str | None = None) -> list[dict]:
    """Retrieve test results from the database."""
    repo = _get_repo()
    results = repo.get_all_results(execution_id=execution_id)
    return [
        {
            "test_name": r.test_name,
            "category": r.category,
            "status": r.status,
            "duration_ms": r.duration_ms,
            "error_message": r.error_message,
        }
        for r in results
    ]


@app.get("/reports/latest")
def get_latest_report() -> dict[str, Any]:
    """Return summary of the latest test run."""
    repo = _get_repo()
    runs = repo.list_test_runs()
    if not runs:
        raise HTTPException(status_code=404, detail="No test runs found.")
    latest = runs[-1]
    return {
        "execution_id": latest.execution_id,
        "started_at": str(latest.started_at),
        "finished_at": str(latest.finished_at),
        "status": latest.status,
        "total_tests": latest.total_tests,
        "passed": latest.passed,
        "failed": latest.failed,
    }
