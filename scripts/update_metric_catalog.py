"""Render executable definitions into documentation; --check verifies freshness."""

import argparse
from pathlib import Path

from app.stats.registry import REGISTRY

START = "<!-- BEGIN EXECUTABLE METRICS -->"
END = "<!-- END EXECUTABLE METRICS -->"


def render() -> str:
    rows = [
        START,
        f"\n## Executable catalog ({len(REGISTRY)} metrics)\n",
        "Generated from `app.stats.registry`; do not edit these rows manually.\n",
        "| ID | Name | Unit | Numerator | Eligible denominator |",
        "|---|---|---|---|---|",
    ]
    for definition in REGISTRY.values():
        values = (
            definition.id,
            definition.name,
            definition.unit,
            definition.numerator,
            definition.denominator,
        )
        rows.append("| " + " | ".join(v.replace("|", "\\|") for v in values) + " |")
    rows.append(END)
    return "\n".join(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path("docs/metric-catalog.md")
    document = path.read_text()
    before = document.split(START)[0].rstrip()
    after = document.split(END, 1)[1] if END in document else "\n"
    expected = before + "\n\n" + render() + after
    if args.check:
        if document != expected:
            raise SystemExit("Metric documentation is stale; run the generator.")
    else:
        path.write_text(expected)
