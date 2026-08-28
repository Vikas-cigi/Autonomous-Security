"""
Initialize all enterprise-engine schemas on PostgreSQL (CREATE_TABLES).

Prereqs:
  1. Docker Desktop running
  2. From backend/: docker compose up -d
  3. pip install -r requirements.txt (includes psycopg)

Usage:
  python scripts/init_postgres.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import settings


def main() -> None:
    url = settings.DATABASE_URL
    print(f"DATABASE_URL={url}")
    if not url.startswith("postgresql"):
        print(
            "WARNING: DATABASE_URL is not PostgreSQL. "
            "Update backend/.env then re-run."
        )

    from sqlalchemy import create_engine, text

    engine = create_engine(url, pool_pre_ping=True, future=True)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
        print(f"Connected: {version}")

    # Each package owns its Base.metadata — create all known engine tables.
    packages = [
        ("trust_scoring.persistence.orm", "Base"),
        ("risk_engine.persistence.orm", "Base"),
        ("decision_service.persistence.orm", "Base"),
        ("remediation_planner.persistence.orm", "Base"),
        ("simulation_engine.persistence.orm", "Base"),
        ("approval_engine.persistence.orm", "Base"),
        ("execution_engine.persistence.orm", "Base"),
        ("verification_engine.persistence.orm", "Base"),
        ("reporting_analytics.persistence.orm", "Base"),
        ("ai_harness.persistence.orm", "Base"),
        ("evidence_repository.persistence.orm", "Base"),
        ("asset_inventory.persistence.orm", "Base"),
        ("threat_intelligence.persistence.orm", "Base"),
    ]

    for module_path, attr in packages:
        try:
            module = __import__(module_path, fromlist=[attr])
            base = getattr(module, attr)
            base.metadata.create_all(bind=engine)
            print(f"OK  {module_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP {module_path}: {exc}")

    print("Schema init complete.")


if __name__ == "__main__":
    main()
