#!/usr/bin/env python3
"""Utility CLI for creating timestamped SQLite backups of the primary BarQuina database."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable

DEFAULT_DB = Path(__file__).resolve().parents[1] / "barquina.db"
DEFAULT_DEST = Path(__file__).resolve().parents[1] / "backups"
CONFIG_FILE = Path(__file__).resolve().parents[1] / ".backup_config.json"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a timestamped backup of the SQLite DB.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to the SQLite database file (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Directory where backups will be written. Overrides any saved configuration.",
    )
    parser.add_argument(
        "--retain",
        type=int,
        default=30,
        help="Number of recent backups to retain (oldest beyond this count are deleted).",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail instead of prompting if no destination is configured.",
    )
    return parser.parse_args()


def ensure_paths(db_path: Path, dest_dir: Path) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")
    dest_dir.mkdir(parents=True, exist_ok=True)


def create_backup(src: Path, dest_dir: Path) -> Path:
    timestamp = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_path = dest_dir / f"{src.stem}-{timestamp}{src.suffix}"
    with sqlite3.connect(src) as source_conn:
        with sqlite3.connect(backup_path) as backup_conn:
            source_conn.backup(backup_conn)
    return backup_path


def cleanup_old_backups(dest_dir: Path, retain: int, stem: str) -> Iterable[Path]:
    if retain <= 0:
        return []
    backups = sorted(dest_dir.glob(f"{stem}-*"))
    to_remove = backups[:-retain]
    for path in to_remove:
        path.unlink(missing_ok=True)
    return to_remove


def load_saved_destination() -> Path | None:
    if not CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    dest = data.get("dest")
    if not dest:
        return None
    return Path(dest).expanduser()


def save_destination(dest: Path) -> None:
    payload = {"dest": str(dest)}
    CONFIG_FILE.write_text(json.dumps(payload, indent=2))


def prompt_for_destination(default: Path) -> Path:
    print("On vols guardar les còpies de seguretat?")
    raw = input(f"Introdueix una carpeta (enter per defecte: {default}): \n> ").strip()
    target = Path(raw) if raw else default
    remember = input("Vols recordar aquesta ruta per a properes execucions? [s/N]: ").strip().lower()
    if remember.startswith("s"):
        save_destination(target)
        print(f"S'ha desat la destinació a {CONFIG_FILE}")
    return target


def resolve_destination(args_dest: Path | None, interactive: bool) -> Path:
    if args_dest:
        return args_dest.expanduser()
    env_dest = os.getenv("BARQUINA_BACKUP_DEST")
    if env_dest:
        return Path(env_dest).expanduser()
    saved = load_saved_destination()
    if saved:
        return saved
    if not interactive:
        raise RuntimeError("Backup destination not configured. Provide --dest or set BARQUINA_BACKUP_DEST.")
    return prompt_for_destination(DEFAULT_DEST)


def main() -> None:
    args = parse_args()
    dest_dir = resolve_destination(args.dest, interactive=not args.non_interactive)
    ensure_paths(args.db, dest_dir)
    backup_path = create_backup(args.db, dest_dir)
    removed = cleanup_old_backups(dest_dir, args.retain, args.db.stem)
    print(f"Backup created: {backup_path}")
    if removed:
        print(f"Removed {len(removed)} old backup(s):")
        for path in removed:
            print(f"  - {path}")


if __name__ == "__main__":
    main()
