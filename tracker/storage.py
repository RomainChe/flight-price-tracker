"""Historique en CSV (ajout seul) : lisible, et chaque commit quotidien ne versionne que les nouvelles lignes."""
import csv
from dataclasses import asdict, fields
from pathlib import Path

from .models import Quote

QUOTE_FIELDS = [f.name for f in fields(Quote) if f.name != "history"]
BASELINE_FIELDS = ["search", "source", "origin", "dest", "depart_date", "return_date", "found_at", "price"]
INT_FIELDS = {"stops", "duration_min"}
FLOAT_FIELDS = {"price", "typical_low", "typical_high"}


def _convert(name, value):
    if value == "":
        return None if name in INT_FIELDS | FLOAT_FIELDS else value
    if name in INT_FIELDS:
        return int(float(value))
    if name in FLOAT_FIELDS:
        return float(value)
    return value


def _append(path: Path, columns: list[str], rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        if new:
            writer.writeheader()
        writer.writerows(rows)


def load_quotes(path: Path) -> list[Quote]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [Quote(**{k: _convert(k, v) for k, v in row.items()}) for row in csv.DictReader(f)]


def append_quotes(path: Path, quotes: list[Quote]):
    _append(path, QUOTE_FIELDS, [asdict(q) for q in quotes])


def load_baseline(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{**row, "price": float(row["price"])} for row in csv.DictReader(f)]


def append_baseline(path: Path, rows: list[dict]):
    _append(path, BASELINE_FIELDS, rows)
