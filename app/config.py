from __future__ import annotations

from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    SECRET_KEY = "change-me"  # TODO: set via env var in production
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'barquina.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
