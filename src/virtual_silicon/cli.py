"""Command-line interface for the Virtual Silicon Validation Platform."""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from virtual_silicon.configuration.settings import get_settings
from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import get_session
from virtual_silicon.device.virtual_chip import VirtualChip
from virtual_silicon.faults.fault_injector import FaultInjector
from virtual_silicon.faults.fault_models import load_fault_configs

app = typer.Typer(
    name="virtual-silicon", help="Virtual Silicon Validation Platform CLI.", rich_markup_mode="rich"
)
console = Console()
settings = get_settings()

_chip: VirtualChip | None = None
_repo: TestRepository | None = None


def _setup_logging() -> None:
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path),
        ],
    )


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


@app.command()
def initialize() -> None:
    """Initialize the virtual chip and database tables."""
    _setup_logging()
    console.print("[bold blue]Initializing Virtual Silicon Platform...[/bold blue]")
    chip = _get_chip()
    chip.power_on()
    get_session(settings.database_url)
    console.print(f"[green]✓[/green] Database initialized at [cyan]{settings.database_url}[/cyan]")
    console.print(
        f"[green]✓[/green] Chip powered on. Device ID: [cyan]0x{chip.get_device_id():02X}[/cyan]"
    )
    console.print(f"[green]✓[/green] Firmware version: [cyan]{chip.get_firmware_version()}[/cyan]")
    console.print(f"[green]✓[/green] SRAM size: [cyan]{chip.sram.size} bytes[/cyan]")
    console.print("[bold green]Platform ready.[/bold green]")


@app.command(name="run-tests")
def run_tests(
    execution_id: str | None = typer.Option(None, help="Custom execution ID."),
) -> None:
    """Run all chip tests including register validation and SRAM tests."""
    _setup_logging()
    eid = execution_id or str(uuid.uuid4())[:8]
    console.print(f"[bold blue]Running validation tests (execution: {eid})...[/bold blue]")

    chip = _get_chip()
    if not chip.powered:
        chip.power_on()

    repo = _get_repo()
    repo.create_test_run(eid, firmware_version=chip.get_firmware_version())

    # Register validation
    passed = failed = 0
    reg_tests = [
        (
            "device_id_check",
            "register",
            chip.get_device_id() == 0xA5,
            "0xA5",
            f"0x{chip.get_device_id():02X}",
        ),
        (
            "firmware_version_check",
            "register",
            chip.get_firmware_version() == "1.0",
            "1.0",
            chip.get_firmware_version(),
        ),
    ]
    for name, cat, ok, exp, act in reg_tests:
        status = "PASS" if ok else "FAIL"
        repo.save_test_result(eid, name, cat, status, expected=exp, actual=act)
        if ok:
            passed += 1
        else:
            failed += 1
        mark = "[green]PASS[/green]" if ok else "[red]FAIL[/red]"
        console.print(f"  {mark} {name}")

    # Memory tests
    mem_results = chip.run_memory_tests()
    for result in mem_results:
        status = "PASS" if result.passed else "FAIL"
        repo.save_test_result(
            eid,
            result.test_name,
            "memory",
            status,
            duration_ms=result.duration * 1000,
            error_message=result.error_message,
        )
        if result.passed:
            passed += 1
        else:
            failed += 1
        mark = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        console.print(f"  {mark} memory/{result.test_name}")

    repo.finish_test_run(eid, passed, failed)
    total = passed + failed
    console.print(f"\n[bold]Results:[/bold] {passed}/{total} passed", end="")
    if failed:
        console.print(f", [red]{failed} failed[/red]")
    else:
        console.print(" [green](all passed)[/green]")


@app.command(name="run-memory-tests")
def run_memory_tests() -> None:
    """Run only the SRAM memory test suite."""
    _setup_logging()
    chip = _get_chip()
    if not chip.powered:
        chip.power_on()

    console.print("[bold blue]Running SRAM memory tests...[/bold blue]")
    results = chip.run_memory_tests()

    table = Table(title="Memory Test Results", show_lines=True)
    table.add_column("Test", style="cyan")
    table.add_column("Status")
    table.add_column("Duration (ms)", justify="right")
    table.add_column("Error")

    for r in results:
        status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
        table.add_row(r.test_name, status, f"{r.duration * 1000:.2f}", r.error_message or "—")

    console.print(table)
    passed = sum(1 for r in results if r.passed)
    console.print(f"\n[bold]{passed}/{len(results)} tests passed.[/bold]")


@app.command(name="inject-fault")
def inject_fault(
    config: str = typer.Option(
        "configs/faults.yaml", "--config", "-c", help="Path to faults YAML."
    ),
) -> None:
    """Inject faults from a YAML configuration file."""
    _setup_logging()
    chip = _get_chip()
    if not chip.powered:
        chip.power_on()

    try:
        fault_configs = load_fault_configs(config)
    except Exception as exc:
        console.print(f"[red]Error loading fault config: {exc}[/red]")
        raise typer.Exit(1) from exc

    injector = FaultInjector(fault_configs, seed=settings.random_seed)
    applied = injector.apply_to_chip(chip, cycle=chip.cycle_count)

    if applied:
        console.print(f"[yellow]Injected {len(applied)} fault(s):[/yellow]")
        for fid in applied:
            console.print(f"  • {fid}")
    else:
        console.print("[blue]No faults triggered at current cycle.[/blue]")


@app.command(name="generate-report")
def generate_report(
    execution_id: str | None = typer.Option(None, help="Execution ID to report on."),
    output: str = typer.Option("reports", "--output", "-o", help="Output directory."),
) -> None:
    """Generate HTML, CSV, and JSON reports for a test run."""
    _setup_logging()
    from virtual_silicon.analytics.analyzer import TestAnalyzer
    from virtual_silicon.analytics.report_generator import ReportGenerator

    repo = _get_repo()

    if execution_id is None:
        runs = repo.list_test_runs()
        if not runs:
            console.print("[red]No test runs found in database.[/red]")
            raise typer.Exit(1)
        execution_id = runs[-1].execution_id
        console.print(f"[blue]Using latest execution: {execution_id}[/blue]")

    results = repo.get_all_results(execution_id)
    measurements = repo.get_measurements(execution_id)
    fault_events: list = []

    analyzer = TestAnalyzer(results, measurements, fault_events)
    summary = analyzer.summarize(execution_id)

    generator = ReportGenerator(output_dir=output)
    paths = generator.generate_all(summary, results, measurements)

    console.print(f"[green]✓[/green] HTML report: [cyan]{paths['html']}[/cyan]")
    console.print(f"[green]✓[/green] CSV summary: [cyan]{paths['csv']}[/cyan]")
    console.print(f"[green]✓[/green] JSON report: [cyan]{paths['json']}[/cyan]")


@app.command(name="reset-chip")
def reset_chip() -> None:
    """Reset the virtual chip to its power-on state."""
    _setup_logging()
    chip = _get_chip()
    chip.reset()
    console.print("[green]✓ Chip reset. All registers restored to defaults.[/green]")


@app.command(name="show-registers")
def show_registers() -> None:
    """Display all register values in a formatted table."""
    _setup_logging()
    chip = _get_chip()
    if not chip.powered:
        chip.power_on()

    snapshot = chip.get_register_snapshot()
    table = Table(title="Register Map Snapshot", show_lines=True)
    table.add_column("Register Name", style="cyan")
    table.add_column("Value (hex)", justify="right")
    table.add_column("Value (dec)", justify="right")

    for name, value in sorted(snapshot.items()):
        table.add_row(name, f"0x{value:04X}", str(value))

    console.print(table)


if __name__ == "__main__":  # pragma: no cover
    app()
