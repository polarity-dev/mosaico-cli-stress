"""Upload stress test command."""

from __future__ import annotations

import uuid
from typing import Optional

import typer
from rich.console import Console

from mosaico_stress.connection import get_connect_kwargs
from mosaico_stress.utils import (
    parse_duration,
    parse_size,
)

console = Console()
error_console = Console(stderr=True)

app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def upload(
    client: int = typer.Option(..., "--client", help="Number of concurrent upload clients."),
    size: Optional[str] = typer.Option(None, "--size", help="Maximum data volume (e.g. 10GB, 500MB)."),
    time_limit: Optional[str] = typer.Option(None, "--time", help="Maximum test duration (e.g. 5m, 30s, 1h)."),
    no_cleanup: bool = typer.Option(False, "--no-cleanup", help="Skip cleanup of uploaded data after the test."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Include per-client statistics in the report."),
    output: str = typer.Option("table", "--output", "-o", help="Report format: table or json."),
):
    """
    Run an upload stress test against the Mosaico platform.

    Generates random IMU data and uploads it using multiple concurrent clients.
    The test stops when the first of --size or --time limits is reached.
    At least one of --size or --time must be provided.
    """
    if not size and not time_limit:
        error_console.print("[bold red]Error:[/bold red] At least one of --size or --time must be specified.")
        raise typer.Exit(code=1)

    max_bytes = parse_size(size) if size else None
    max_seconds = parse_duration(time_limit) if time_limit else None

    connect_kwargs = get_connect_kwargs()
    sequence_prefix = f"stress_upload_{uuid.uuid4().hex[:8]}"
