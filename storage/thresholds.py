"""Migrazione e persistenza delle soglie configurabili per scenario."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "fte_app.db"

DEFAULT_THRESHOLDS = {
    "cas_threshold": 0.15,
    "overtime_threshold": 0.15,
    "retirement_attention": 0.15,
    "retirement_critical": 0.30,
    "staffing_ratio_min": 0.85,
    "staffing_ratio_max": 1.10,
}


def _connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def migrate_thresholds() -> None:
    """Crea la tabella aggiuntiva senza modificare le tabelle già esistenti."""
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS model_thresholds (
                scenario_id INTEGER PRIMARY KEY,
                cas_threshold REAL NOT NULL DEFAULT 0.15,
                overtime_threshold REAL NOT NULL DEFAULT 0.15,
                retirement_attention REAL NOT NULL DEFAULT 0.15,
                retirement_critical REAL NOT NULL DEFAULT 0.30,
                staffing_ratio_min REAL NOT NULL DEFAULT 0.85,
                staffing_ratio_max REAL NOT NULL DEFAULT 1.10
            )
            """
        )


def get_thresholds(scenario_id: int) -> dict[str, float]:
    migrate_thresholds()
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM model_thresholds WHERE scenario_id = ?", (int(scenario_id),)
        ).fetchone()
    if row is None:
        return dict(DEFAULT_THRESHOLDS)
    return {key: float(row[key]) for key in DEFAULT_THRESHOLDS}


def save_thresholds(scenario_id: int, values: dict[str, float]) -> None:
    migrate_thresholds()
    normalized = {key: float(values.get(key, default)) for key, default in DEFAULT_THRESHOLDS.items()}
    if normalized["retirement_attention"] > normalized["retirement_critical"]:
        raise ValueError("La soglia pensionamento di attenzione non può superare quella critica.")
    if normalized["staffing_ratio_min"] > normalized["staffing_ratio_max"]:
        raise ValueError("La soglia minima di organico non può superare quella massima.")
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO model_thresholds (
                scenario_id, cas_threshold, overtime_threshold,
                retirement_attention, retirement_critical,
                staffing_ratio_min, staffing_ratio_max
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scenario_id) DO UPDATE SET
                cas_threshold = excluded.cas_threshold,
                overtime_threshold = excluded.overtime_threshold,
                retirement_attention = excluded.retirement_attention,
                retirement_critical = excluded.retirement_critical,
                staffing_ratio_min = excluded.staffing_ratio_min,
                staffing_ratio_max = excluded.staffing_ratio_max
            """,
            (
                int(scenario_id), normalized["cas_threshold"], normalized["overtime_threshold"],
                normalized["retirement_attention"], normalized["retirement_critical"],
                normalized["staffing_ratio_min"], normalized["staffing_ratio_max"],
            ),
        )


def reset_thresholds(scenario_id: int) -> None:
    migrate_thresholds()
    with _connect() as connection:
        connection.execute("DELETE FROM model_thresholds WHERE scenario_id = ?", (int(scenario_id),))
