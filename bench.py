"""Quick benchmarks for PowerPoint Inverter using real fixture PPTX files.

Usage:
  uv run python bench.py --repeat 3
  uv run python bench.py --files tests/fixtures/*.pptx --repeat 5

Outputs wall-clock timings so you can compare optimizations.
"""

from __future__ import annotations

import argparse
import glob
import statistics
import time
from pathlib import Path
from typing import List

from pp.core.inverter import process_files
from pp.models.config import InversionConfig


class BenchFile:
    """Minimal UploadedFile-like adapter for benchmarks."""

    def __init__(self, path: Path):
        self._data = path.read_bytes()
        self.name = path.name

    def read(self) -> bytes:
        return self._data

    def seek(self, _: int) -> None:
        # No-op to satisfy the interface expected by process_files
        pass


def run_once(files: list[BenchFile], config: InversionConfig) -> float:
    start = time.perf_counter()
    process_files(files, config)
    return (time.perf_counter() - start) * 1000  # ms


def main() -> None:
    parser = argparse.ArgumentParser(description="Run inverter benchmarks on PPTX fixtures")
    parser.add_argument(
        "--files",
        nargs="+",
        help="Paths or glob patterns to PPTX files (defaults to tests/fixtures/*.pptx)",
    )
    parser.add_argument("--repeat", type=int, default=3, help="Number of timing runs")
    args = parser.parse_args()

    if args.files:
        paths: List[str] = []
        for pattern in args.files:
            matches = glob.glob(pattern)
            if not matches:
                raise SystemExit(f"No files matched pattern: {pattern}")
            paths.extend(matches)
    else:
        paths = glob.glob("tests/fixtures/*.pptx")

    if not paths:
        raise SystemExit("No PPTX files found to benchmark.")

    bench_files = [BenchFile(Path(p)) for p in paths]

    config = InversionConfig.from_hex(
        fg_hex="#FFFFFF",
        bg_hex="#000000",
        file_suffix="(bench)",
        folder_name="Bench Output",
        invert_images=True,
    )

    timings = []
    for _ in range(args.repeat):
        timings.append(run_once(bench_files, config))

    total_files = len(bench_files)
    mean_ms = statistics.mean(timings)
    p95_ms = statistics.quantiles(timings, n=20)[18] if len(timings) > 1 else mean_ms
    per_file_ms = mean_ms / total_files

    print(f"Runs: {args.repeat}")
    print(f"Files per run: {total_files}")
    print(f"Mean: {mean_ms:.1f} ms (p95: {p95_ms:.1f} ms)")
    print(f"Per-file mean: {per_file_ms:.1f} ms")


if __name__ == "__main__":
    main()
