"""Resolve shared resources independently of the caller's working directory."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
ENV_PATH = ROOT_DIR / ".env"
DOCUMENTS_DIR = ROOT_DIR / "documents"
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = DATA_DIR / "northstar.db"
