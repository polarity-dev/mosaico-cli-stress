"""Upload stress test command."""

from __future__ import annotations

import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import typer
from mosaicolabs import (
    IMU,
    Message,
    MosaicoClient,
    SessionLevelErrorPolicy,
    Vector3d,
)

from mosaico_stress.connection import get_connect_kwargs
from mosaico_stress.utils import (
    Operation,
    console,
    error_console,
    parse_duration,
    parse_size,
    print_report,
    size_limit_reached,
)

FLUSH_EVERY = 100
BATCH_SIZE = 100

def upload_worker(
    client_id: int,
    shared_state: dict,
    metrics_bucket: List[Operation],
    connect_kwargs: dict,
    sequence_prefix: str,
) -> None:
    """Upload random IMU data until the stop event fires."""
    with MosaicoClient.connect(**connect_kwargs) as sdk_client:
        seq_name = f"{sequence_prefix}_client{client_id}"

        with sdk_client.sequence_create(
            sequence_name=seq_name,
            metadata={"stress_test": "true", "client_id": str(client_id)},
            on_error=SessionLevelErrorPolicy.Delete,
        ) as seq_writer:
            topic_writer = seq_writer.topic_create(
                topic_name="stress/data",
                metadata={"type": "random_imu"},
                ontology_type=IMU,
            )

            if not topic_writer:
                return

            ts_ns = 1_700_000_000_000_000_000
            batch_count = 0

            while not shared_state["stop_event"].is_set():
                start_time = time.time()
                bytes_sent = 0

                for _ in range(BATCH_SIZE):
                    msg = Message(
                        timestamp_ns=ts_ns,
                        data=IMU(
                            acceleration=Vector3d(
                                x=random.uniform(-10, 10),
                                y=random.uniform(-10, 10),
                                z=random.uniform(9.0, 10.0),
                            ),
                            angular_velocity=Vector3d(
                                x=random.uniform(-1, 1),
                                y=random.uniform(-1, 1),
                                z=random.uniform(-1, 1),
                            ),
                        ),
                    )
                    topic_writer.push(message=msg)
                    ts_ns += 10_000_000
                    bytes_sent += len(msg.model_dump_json())

                duration = time.time() - start_time
                batch_count += 1

                metrics_bucket.append(
                    Operation(
                        client_id=client_id,
                        duration_seconds=duration,
                        bytes_transferred=bytes_sent,
                        throughput_mbs=(bytes_sent / (1024 * 1024)) / duration if duration > 0 else 0,
                    )
                )

                with shared_state["lock"]:
                    shared_state["total_bytes"] += bytes_sent

                if size_limit_reached(shared_state):
                    shared_state["stop_event"].set()
                    break


def _cleanup_sequences(connect_kwargs: dict, sequence_prefix: str, num_clients: int) -> None:
    """Delete uploaded sequences after the test."""
    try:
        with MosaicoClient.connect(**connect_kwargs) as sdk_client:
            for i in range(num_clients):
                seq_name = f"{sequence_prefix}_client{i}"
                try:
                    sdk_client.sequence_delete(seq_name)
                except Exception:
                    pass
    except Exception as e:
        error_console.print(f"[yellow]Warning:[/yellow] Cleanup failed: {e}")


app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def upload(
    client: int = typer.Option(..., "--client", help="Number of concurrent upload clients."),
    size: Optional[str] = typer.Option(None, "--size", help="Maximum data volume (e.g. 10GB, 500MB)."),
    time_limit: Optional[str] = typer.Option(None, "--time", help="Maximum test duration (e.g. 5m, 30s, 1h)."),
    sequence_name: Optional[str] = typer.Option(None, "--name", "-n", help="Base name for uploaded sequences (default: auto-generated)."),
    no_cleanup: bool = typer.Option(False, "--no-cleanup", help="Skip cleanup of uploaded data after the test."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Include per-client statistics in the report."),
    output: str = typer.Option("table", "--output", "-o", help="Report format: table or json."),
) -> None:
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
    sequence_prefix = sequence_name if sequence_name else f"stress_upload_{uuid.uuid4().hex[:8]}"

    if output != "json":
        console.print("[bold cyan]Starting upload stress test[/bold cyan]")
        console.print(f"  Clients:  {client}")
        console.print(f"  Max size: {max_bytes / (1024*1024):.1f} MB" if max_bytes else "  Max size: unlimited")
        console.print(f"  Max time: {max_seconds:.0f}s" if max_seconds else "  Max time: unlimited")
        console.print(f"  Target:   {connect_kwargs['host']}:{connect_kwargs['port']}")
        console.print()

    # Shared state — thread-safe via lock + Event
    stop_event = threading.Event()
    shared_state = {
        "total_bytes": 0,
        "stop_event": stop_event,
        "max_bytes": max_bytes,
        "lock": threading.Lock(),
    }
    metrics_bucket: List[Operation] = []

    # Time limit watchdog
    def _timer():
        stop_event.wait(timeout=max_seconds)
        stop_event.set()

    if max_seconds:
        timer_thread = threading.Thread(target=_timer, daemon=True)
        timer_thread.start()

    start = time.time()

    with ThreadPoolExecutor(max_workers=client) as pool:
        futures = [
            pool.submit(upload_worker, i, shared_state, metrics_bucket, connect_kwargs, sequence_prefix)
            for i in range(client)
        ]
        stop_event.wait()

        for f in futures:
            f.result()

    total_duration = time.time() - start
    print_report("upload", total_duration, shared_state, metrics_bucket, client, verbose, output)

    # Cleanup
    if not no_cleanup:
        if output != "json":
            console.print("[dim]Cleaning up uploaded sequences...[/dim]")
        _cleanup_sequences(connect_kwargs, sequence_prefix, client)
        if output != "json":
            console.print("[dim]Cleanup complete.[/dim]")
