import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_MOCK_PATH = BASE_DIR / "data" / "mock" / "portfolio_mock.csv"

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

DATA_REFERENCIA = "2026-03-30"
