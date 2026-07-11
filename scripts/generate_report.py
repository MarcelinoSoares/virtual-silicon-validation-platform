#!/usr/bin/env python3
"""Generate HTML, CSV, and JSON reports from the latest test run."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virtual_silicon.analytics.analyzer import TestAnalyzer
from virtual_silicon.analytics.report_generator import ReportGenerator
from virtual_silicon.configuration.settings import get_settings
from virtual_silicon.database.repository import TestRepository
from virtual_silicon.database.session import get_session


def main() -> int:
    settings = get_settings()

    db = get_session(settings.database_url)
    repo = TestRepository(db)

    runs = repo.list_test_runs()
    if not runs:
        print("No test runs found in database.", file=sys.stderr)
        return 1

    latest = runs[-1]
    eid = latest.execution_id
    print(f"Generating report for execution: {eid}")

    results = repo.get_all_results(eid)
    measurements = repo.get_measurements(eid)

    analyzer = TestAnalyzer(results, measurements, [])
    summary = analyzer.summarize(eid)

    generator = ReportGenerator(
        output_dir=settings.reports_dir,
        firmware_version=latest.firmware_version,
        chip_version=latest.chip_version,
    )
    paths = generator.generate_all(summary, results, measurements)

    print(f"HTML: {paths['html']}")
    print(f"CSV:  {paths['csv']}")
    print(f"JSON: {paths['json']}")
    print(f"Pass rate: {summary.pass_rate}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
