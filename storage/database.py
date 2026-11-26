"""Persistenza SQLite e duplicazione transazionale degli scenari."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from core.constants import DEFAULT_WORK_PARAMETERS, PROFESSIONS, TRAINEE_PROFESSIONS


class Database:
    """Repository unico per separare il salvataggio dalla UI Streamlit."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS scenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    facility_name TEXT NOT NULL DEFAULT '',
                    facility_code TEXT NOT NULL DEFAULT '',
                    reference_year INTEGER NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_scenario_id INTEGER REFERENCES scenarios(id)
                );

                CREATE TABLE IF NOT EXISTS operating_units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    area TEXT NOT NULL,
                    h24 INTEGER NOT NULL DEFAULT 0,
                    has_shifts INTEGER NOT NULL DEFAULT 0,
                    has_outpatient INTEGER NOT NULL DEFAULT 0,
                    has_operating_rooms INTEGER NOT NULL DEFAULT 0,
                    radioprotection INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(scenario_id, name)
                );

                CREATE TABLE IF NOT EXISTS unit_professions (
                    unit_id INTEGER NOT NULL REFERENCES operating_units(id) ON DELETE CASCADE,
                    profession TEXT NOT NULL,
                    PRIMARY KEY(unit_id, profession)
                );

                CREATE TABLE IF NOT EXISTS work_parameters (
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    profession TEXT NOT NULL,
                    weekly_hours REAL NOT NULL,
                    workdays_week INTEGER NOT NULL,
                    shift_hours REAL NOT NULL,
                    shift_is_auto INTEGER NOT NULL DEFAULT 1,
                    holidays REAL NOT NULL,
                    leave_days REAL NOT NULL,
                    sickness_days REAL NOT NULL,
                    training_days REAL NOT NULL,
                    PRIMARY KEY(scenario_id, profession)
                );

                CREATE TABLE IF NOT EXISTS activity_inputs (
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    unit_id INTEGER NOT NULL REFERENCES operating_units(id) ON DELETE CASCADE,
                    profession TEXT NOT NULL,
                    annual_work_hours REAL NOT NULL DEFAULT 0,
                    overtime_hours REAL NOT NULL DEFAULT 0,
                    cas_percent REAL NOT NULL DEFAULT 0,
                    ias_hours REAL NOT NULL DEFAULT 0,
                    morning_operators INTEGER NOT NULL DEFAULT 0,
                    afternoon_operators INTEGER NOT NULL DEFAULT 0,
                    night_operators INTEGER NOT NULL DEFAULT 0,
                    coverage_days_year INTEGER NOT NULL DEFAULT 0,
                    outpatient_volume INTEGER NOT NULL DEFAULT 0,
                    outpatient_minutes REAL NOT NULL DEFAULT 0,
                    community_hours REAL NOT NULL DEFAULT 0,
                    recovery_hours REAL NOT NULL DEFAULT 0,
                    operating_rooms INTEGER NOT NULL DEFAULT 0,
                    room_hours_day REAL NOT NULL DEFAULT 0,
                    room_days_year INTEGER NOT NULL DEFAULT 0,
                    operators_per_room REAL NOT NULL DEFAULT 0,
                    is_complete INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(scenario_id, unit_id, profession)
                );

                CREATE TABLE IF NOT EXISTS radiology_rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    unit_id INTEGER NOT NULL REFERENCES operating_units(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    modality TEXT NOT NULL,
                    h24 INTEGER NOT NULL DEFAULT 0,
                    hours_day REAL NOT NULL DEFAULT 0,
                    days_year INTEGER NOT NULL DEFAULT 0,
                    annual_volume INTEGER NOT NULL DEFAULT 0,
                    average_minutes REAL NOT NULL DEFAULT 0,
                    doctors REAL NOT NULL DEFAULT 0,
                    nurses REAL NOT NULL DEFAULT 0,
                    oss REAL NOT NULL DEFAULT 0,
                    health_technicians REAL NOT NULL DEFAULT 0,
                    radiology_technicians REAL NOT NULL DEFAULT 0,
                    UNIQUE(scenario_id, unit_id, name)
                );

                CREATE TABLE IF NOT EXISTS staffing (
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    unit_id INTEGER NOT NULL REFERENCES operating_units(id) ON DELETE CASCADE,
                    profession TEXT NOT NULL,
                    full_time REAL NOT NULL DEFAULT 0,
                    part_time REAL NOT NULL DEFAULT 0,
                    trainees REAL NOT NULL DEFAULT 0,
                    over_60 REAL NOT NULL DEFAULT 0,
                    retiring_3y REAL NOT NULL DEFAULT 0,
                    shift_workers REAL NOT NULL DEFAULT 0,
                    night_eligible REAL NOT NULL DEFAULT 0,
                    effort_eligible REAL NOT NULL DEFAULT 0,
                    exposure_eligible REAL NOT NULL DEFAULT 0,
                    full_time_effort REAL NOT NULL DEFAULT 0,
                    full_time_night REAL NOT NULL DEFAULT 0,
                    full_time_law104 REAL NOT NULL DEFAULT 0,
                    part_time_effort REAL NOT NULL DEFAULT 0,
                    part_time_night REAL NOT NULL DEFAULT 0,
                    part_time_law104 REAL NOT NULL DEFAULT 0,
                    full_time_night_limited REAL NOT NULL DEFAULT 0,
                    part_time_night_limited REAL NOT NULL DEFAULT 0,
                    full_time_law104_one REAL NOT NULL DEFAULT 0,
                    full_time_law104_two REAL NOT NULL DEFAULT 0,
                    part_time_law104_one REAL NOT NULL DEFAULT 0,
                    part_time_law104_two REAL NOT NULL DEFAULT 0,
                    full_time_retiring_3y REAL NOT NULL DEFAULT 0,
                    part_time_retiring_3y REAL NOT NULL DEFAULT 0,
                    dotation_saved INTEGER NOT NULL DEFAULT 0,
                    is_complete INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(scenario_id, unit_id, profession)
                );

                CREATE TABLE IF NOT EXISTS section_status (
                    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
                    section_key TEXT NOT NULL,
                    is_complete INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(scenario_id, section_key)
                );
                """
            )
            staffing_columns = {row["name"] for row in con.execute("PRAGMA table_info(staffing)")}
            if "dotation_saved" not in staffing_columns:
                con.execute(
                    "ALTER TABLE staffing ADD COLUMN dotation_saved INTEGER NOT NULL DEFAULT 0"
                )
                con.execute(
                    "UPDATE staffing SET dotation_saved=1 WHERE is_complete=1"
                )
            unit_columns = {row["name"] for row in con.execute("PRAGMA table_info(operating_units)")}
            if "radioprotection" not in unit_columns:
                con.execute(
                    "ALTER TABLE operating_units ADD COLUMN radioprotection INTEGER NOT NULL DEFAULT 0"
                )
            new_staffing_columns = {
                "full_time_effort": "REAL NOT NULL DEFAULT 0",
                "full_time_night": "REAL NOT NULL DEFAULT 0",
                "full_time_law104": "REAL NOT NULL DEFAULT 0",
                "part_time_effort": "REAL NOT NULL DEFAULT 0",
                "part_time_night": "REAL NOT NULL DEFAULT 0",
                "part_time_law104": "REAL NOT NULL DEFAULT 0",
            }
            added_staffing_columns = []
            for column, definition in new_staffing_columns.items():
                if column not in staffing_columns:
                    con.execute(f"ALTER TABLE staffing ADD COLUMN {column} {definition}")
                    added_staffing_columns.append(column)
            if added_staffing_columns:
                con.execute(
                    """UPDATE staffing SET
                       full_time_effort=full_time, full_time_night=full_time,
                       part_time_effort=part_time, part_time_night=part_time,
                       full_time_law104=0, part_time_law104=0,
                       is_complete=0
                       WHERE dotation_saved=1"""
                )
            staffing_columns = {row["name"] for row in con.execute("PRAGMA table_info(staffing)")}
            revised_staffing_columns = {
                "full_time_night_limited": "REAL NOT NULL DEFAULT 0",
                "part_time_night_limited": "REAL NOT NULL DEFAULT 0",
                "full_time_law104_one": "REAL NOT NULL DEFAULT 0",
                "full_time_law104_two": "REAL NOT NULL DEFAULT 0",
                "part_time_law104_one": "REAL NOT NULL DEFAULT 0",
                "part_time_law104_two": "REAL NOT NULL DEFAULT 0",
                "full_time_retiring_3y": "REAL NOT NULL DEFAULT 0",
                "part_time_retiring_3y": "REAL NOT NULL DEFAULT 0",
            }
            revised_columns_added = False
            for column, definition in revised_staffing_columns.items():
                if column not in staffing_columns:
                    con.execute(f"ALTER TABLE staffing ADD COLUMN {column} {definition}")
                    revised_columns_added = True
            if revised_columns_added:
                # Migrazione v5 -> v6:
                # - gli idonei alla notte diventano il complemento dei limitati;
                # - i beneficiari 104 esistenti confluiscono nella categoria "una persona";
                # - il totale pensionamenti viene conservato, attribuendolo prima ai FT e
                #   poi ai PT solo per l'eventuale eccedenza. Le schede vengono riaperte
                #   affinché l'utente verifichi la ripartizione.
                con.execute(
                    """UPDATE staffing SET
                       full_time_night_limited=MAX(0, full_time-full_time_night),
                       part_time_night_limited=MAX(0, part_time-part_time_night),
                       full_time_law104_one=MIN(full_time_law104, full_time),
                       full_time_law104_two=0,
                       part_time_law104_one=MIN(part_time_law104, part_time),
                       part_time_law104_two=0,
                       full_time_retiring_3y=MIN(retiring_3y, full_time),
                       part_time_retiring_3y=MIN(MAX(retiring_3y-full_time, 0), part_time),
                       trainees=CASE
                           WHEN profession IN ('Medici', 'Infermieri') THEN trainees ELSE 0 END,
                       over_60=0,
                       is_complete=CASE WHEN dotation_saved=1 THEN 0 ELSE is_complete END
                       WHERE dotation_saved=1"""
                )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def seed_if_empty(self) -> int:
        scenarios = self.list_scenarios()
        if scenarios:
            return int(scenarios[0]["id"])
        scenario_id = self.create_scenario(
            name="Scenario iniziale",
            reference_year=2026,
            facility_name="",
            description="Scenario iniziale modificabile, predisposto per avviare la configurazione della struttura.",
        )
        seed_units = [
            ("Cardiologia", "Medica", True, True, True, True, ("Medici", "Infermieri", "OSS")),
            ("Terapia intensiva", "Emergenza-urgenza", True, True, False, False, ("Medici", "Infermieri", "OSS")),
            ("Chirurgia generale", "Chirurgica", True, True, True, True, ("Medici", "Infermieri", "OSS")),
            ("Lab. Analisi Cliniche", "Laboratori", False, False, False, False, ("Tecnici sanitari",)),
            ("Radiologia Diagnostica", "Servizi diagnostici", True, True, True, False, ("Medici", "Infermieri", "Tecnici di radiologia", "OSS")),
        ]
        for name, area, h24, shifts, outpatient, rooms, professions in seed_units:
            unit_id = self.upsert_operating_unit(
                scenario_id, None, name, area, h24, shifts, outpatient, rooms, False, True
            )
            self.set_unit_professions(unit_id, professions)
        return scenario_id

    def create_scenario(
        self,
        name: str,
        reference_year: int,
        facility_name: str = "",
        facility_code: str = "",
        description: str = "",
    ) -> int:
        now = self._now()
        with self.connect() as con:
            cursor = con.execute(
                """INSERT INTO scenarios
                   (name, facility_name, facility_code, reference_year, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name.strip(), facility_name.strip(), facility_code.strip(), reference_year, description.strip(), now, now),
            )
            scenario_id = int(cursor.lastrowid)
            self._insert_default_parameters(con, scenario_id)
            return scenario_id

    def _insert_default_parameters(self, con: sqlite3.Connection, scenario_id: int) -> None:
        rows = []
        for profession, values in DEFAULT_WORK_PARAMETERS.items():
            rows.append((scenario_id, profession, *values.values()))
        con.executemany(
            """INSERT INTO work_parameters
               (scenario_id, profession, weekly_hours, workdays_week, shift_hours,
                shift_is_auto, holidays, leave_days, sickness_days, training_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )

    def list_scenarios(self) -> list[sqlite3.Row]:
        with self.connect() as con:
            return list(con.execute("SELECT * FROM scenarios ORDER BY updated_at DESC, id DESC"))

    def get_scenario(self, scenario_id: int) -> sqlite3.Row:
        with self.connect() as con:
            row = con.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
            if row is None:
                raise KeyError(f"Scenario {scenario_id} non trovato")
            return row

    def update_scenario(
        self,
        scenario_id: int,
        name: str,
        facility_name: str,
        facility_code: str,
        reference_year: int,
        description: str,
    ) -> None:
        with self.connect() as con:
            con.execute(
                """UPDATE scenarios SET name=?, facility_name=?, facility_code=?,
                   reference_year=?, description=?, updated_at=? WHERE id=?""",
                (name.strip(), facility_name.strip(), facility_code.strip(), reference_year,
                 description.strip(), self._now(), scenario_id),
            )

    def touch_scenario(self, con: sqlite3.Connection, scenario_id: int) -> None:
        con.execute("UPDATE scenarios SET updated_at=? WHERE id=?", (self._now(), scenario_id))

    def duplicate_scenario(
        self,
        source_id: int,
        new_name: str,
        new_description: str | None = None,
    ) -> int:
        """Copia scenario, UO, professioni, parametri, organico e stati in una transazione."""
        with self.connect() as con:
            source = con.execute("SELECT * FROM scenarios WHERE id=?", (source_id,)).fetchone()
            if source is None:
                raise KeyError("Scenario sorgente non trovato")
            now = self._now()
            cursor = con.execute(
                """INSERT INTO scenarios
                   (name, facility_name, facility_code, reference_year, description,
                    created_at, updated_at, source_scenario_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_name.strip(), source["facility_name"], source["facility_code"],
                 source["reference_year"],
                 source["description"] if new_description is None else new_description.strip(),
                 now, now, source_id),
            )
            new_id = int(cursor.lastrowid)
            con.execute(
                """INSERT INTO work_parameters
                   SELECT ?, profession, weekly_hours, workdays_week, shift_hours,
                          shift_is_auto, holidays, leave_days, sickness_days, training_days
                   FROM work_parameters WHERE scenario_id=?""",
                (new_id, source_id),
            )
            unit_map: dict[int, int] = {}
            source_units = con.execute(
                "SELECT * FROM operating_units WHERE scenario_id=?", (source_id,)
            ).fetchall()
            for unit in source_units:
                new_unit = con.execute(
                    """INSERT INTO operating_units
                       (scenario_id, name, area, h24, has_shifts, has_outpatient,
                         has_operating_rooms, radioprotection, active)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_id, unit["name"], unit["area"], unit["h24"], unit["has_shifts"],
                     unit["has_outpatient"], unit["has_operating_rooms"],
                     unit["radioprotection"], unit["active"]),
                )
                unit_map[int(unit["id"])] = int(new_unit.lastrowid)
            for old_unit_id, new_unit_id in unit_map.items():
                professions = con.execute(
                    "SELECT profession FROM unit_professions WHERE unit_id=?", (old_unit_id,)
                ).fetchall()
                con.executemany(
                    "INSERT INTO unit_professions (unit_id, profession) VALUES (?, ?)",
                    [(new_unit_id, row["profession"]) for row in professions],
                )
                staffing = con.execute(
                    "SELECT * FROM staffing WHERE scenario_id=? AND unit_id=?",
                    (source_id, old_unit_id),
                ).fetchall()
                con.executemany(
                    """INSERT INTO staffing
                       (scenario_id, unit_id, profession, full_time, part_time, trainees,
                        over_60, retiring_3y, shift_workers, night_eligible,
                        effort_eligible, exposure_eligible, full_time_effort,
                        full_time_night, full_time_law104, part_time_effort,
                        part_time_night, part_time_law104,
                        full_time_night_limited, part_time_night_limited,
                        full_time_law104_one, full_time_law104_two,
                        part_time_law104_one, part_time_law104_two,
                        full_time_retiring_3y, part_time_retiring_3y,
                        dotation_saved, is_complete)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [(new_id, new_unit_id, row["profession"], row["full_time"], row["part_time"],
                      row["trainees"], row["over_60"], row["retiring_3y"], row["shift_workers"],
                      row["night_eligible"], row["effort_eligible"], row["exposure_eligible"],
                      row["full_time_effort"], row["full_time_night"], row["full_time_law104"],
                      row["part_time_effort"], row["part_time_night"], row["part_time_law104"],
                      row["full_time_night_limited"], row["part_time_night_limited"],
                      row["full_time_law104_one"], row["full_time_law104_two"],
                      row["part_time_law104_one"], row["part_time_law104_two"],
                      row["full_time_retiring_3y"], row["part_time_retiring_3y"],
                      row["dotation_saved"], row["is_complete"]) for row in staffing],
                )
                activities = con.execute(
                    "SELECT * FROM activity_inputs WHERE scenario_id=? AND unit_id=?",
                    (source_id, old_unit_id),
                ).fetchall()
                con.executemany(
                    """INSERT INTO activity_inputs
                       (scenario_id, unit_id, profession, annual_work_hours, overtime_hours,
                        cas_percent, ias_hours, morning_operators, afternoon_operators,
                        night_operators, coverage_days_year, outpatient_volume,
                        outpatient_minutes, community_hours, recovery_hours, operating_rooms,
                        room_hours_day, room_days_year, operators_per_room, is_complete)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [(new_id, new_unit_id, row["profession"], row["annual_work_hours"],
                      row["overtime_hours"], row["cas_percent"], row["ias_hours"],
                      row["morning_operators"], row["afternoon_operators"], row["night_operators"],
                      row["coverage_days_year"], row["outpatient_volume"], row["outpatient_minutes"],
                      row["community_hours"], row["recovery_hours"], row["operating_rooms"],
                      row["room_hours_day"], row["room_days_year"], row["operators_per_room"],
                      row["is_complete"]) for row in activities],
                )
            rooms = con.execute(
                "SELECT * FROM radiology_rooms WHERE scenario_id=?", (source_id,)
            ).fetchall()
            for room in rooms:
                con.execute(
                    """INSERT INTO radiology_rooms
                       (scenario_id, unit_id, name, modality, h24, hours_day, days_year,
                        annual_volume, average_minutes, doctors, nurses, oss,
                        health_technicians, radiology_technicians)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (new_id, unit_map[int(room["unit_id"])], room["name"], room["modality"],
                     room["h24"], room["hours_day"], room["days_year"], room["annual_volume"],
                     room["average_minutes"], room["doctors"], room["nurses"], room["oss"],
                     room["health_technicians"], room["radiology_technicians"]),
                )
            statuses = con.execute(
                "SELECT section_key, is_complete FROM section_status WHERE scenario_id=?", (source_id,)
            ).fetchall()
            con.executemany(
                "INSERT INTO section_status (scenario_id, section_key, is_complete) VALUES (?, ?, ?)",
                [(new_id, row["section_key"], row["is_complete"]) for row in statuses],
            )
            return new_id

    def list_operating_units(self, scenario_id: int, active_only: bool = False) -> list[dict]:
        query = "SELECT * FROM operating_units WHERE scenario_id=?"
        params: list[object] = [scenario_id]
        if active_only:
            query += " AND active=1"
        query += " ORDER BY name"
        with self.connect() as con:
            units = [dict(row) for row in con.execute(query, params)]
            for unit in units:
                professions = con.execute(
                    "SELECT profession FROM unit_professions WHERE unit_id=? ORDER BY profession",
                    (unit["id"],),
                ).fetchall()
                unit["professions"] = [row["profession"] for row in professions]
            return units

    def upsert_operating_unit(
        self,
        scenario_id: int,
        unit_id: int | None,
        name: str,
        area: str,
        h24: bool,
        has_shifts: bool,
        has_outpatient: bool,
        has_operating_rooms: bool,
        radioprotection: bool,
        active: bool,
    ) -> int:
        with self.connect() as con:
            if unit_id is None:
                cursor = con.execute(
                    """INSERT INTO operating_units
                       (scenario_id, name, area, h24, has_shifts, has_outpatient,
                         has_operating_rooms, radioprotection, active)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (scenario_id, name.strip(), area, int(h24), int(has_shifts),
                      int(has_outpatient), int(has_operating_rooms), int(radioprotection), int(active)),
                )
                result = int(cursor.lastrowid)
            else:
                con.execute(
                    """UPDATE operating_units SET name=?, area=?, h24=?, has_shifts=?,
                       has_outpatient=?, has_operating_rooms=?, radioprotection=?, active=?
                       WHERE id=? AND scenario_id=?""",
                    (name.strip(), area, int(h24), int(has_shifts), int(has_outpatient),
                      int(has_operating_rooms), int(radioprotection), int(active), unit_id, scenario_id),
                )
                result = unit_id
            self.touch_scenario(con, scenario_id)
            return result

    def delete_operating_unit(self, scenario_id: int, unit_id: int) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM operating_units WHERE id=? AND scenario_id=?", (unit_id, scenario_id))
            self.touch_scenario(con, scenario_id)

    def set_operating_unit_active(self, scenario_id: int, unit_id: int, active: bool) -> None:
        """Attiva/disattiva una UO senza dover aprire la relativa scheda."""
        with self.connect() as con:
            con.execute(
                "UPDATE operating_units SET active=? WHERE id=? AND scenario_id=?",
                (int(active), unit_id, scenario_id),
            )
            self.touch_scenario(con, scenario_id)

    def set_unit_professions(self, unit_id: int, professions: Iterable[str]) -> None:
        selected = [item for item in professions if item in PROFESSIONS]
        with self.connect() as con:
            con.execute("DELETE FROM unit_professions WHERE unit_id=?", (unit_id,))
            con.executemany(
                "INSERT INTO unit_professions (unit_id, profession) VALUES (?, ?)",
                [(unit_id, profession) for profession in selected],
            )
            con.execute(
                "DELETE FROM staffing WHERE unit_id=? AND profession NOT IN ({})".format(
                    ",".join("?" for _ in selected) or "''"
                ),
                (unit_id, *selected),
            )

    def get_work_parameters(self, scenario_id: int) -> list[dict]:
        with self.connect() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM work_parameters WHERE scenario_id=? ORDER BY profession", (scenario_id,)
            )]

    def update_work_parameters(self, scenario_id: int, profession: str, values: dict) -> None:
        with self.connect() as con:
            con.execute(
                """UPDATE work_parameters SET weekly_hours=?, workdays_week=?, shift_hours=?,
                   shift_is_auto=?, holidays=?, leave_days=?, sickness_days=?, training_days=?
                   WHERE scenario_id=? AND profession=?""",
                (values["weekly_hours"], values["workdays_week"], values["shift_hours"],
                 int(values["shift_is_auto"]), values["holidays"], values["leave_days"],
                 values["sickness_days"], values["training_days"], scenario_id, profession),
            )
            self.touch_scenario(con, scenario_id)

    def reset_work_parameters(self, scenario_id: int, profession: str) -> None:
        self.update_work_parameters(scenario_id, profession, DEFAULT_WORK_PARAMETERS[profession])

    def get_activity_input(self, scenario_id: int, unit_id: int, profession: str) -> dict:
        with self.connect() as con:
            row = con.execute(
                """SELECT * FROM activity_inputs
                   WHERE scenario_id=? AND unit_id=? AND profession=?""",
                (scenario_id, unit_id, profession),
            ).fetchone()
            if row:
                return dict(row)
        return {
            "annual_work_hours": 0.0, "overtime_hours": 0.0, "cas_percent": 0.0,
            "ias_hours": 0.0, "morning_operators": 0, "afternoon_operators": 0,
            "night_operators": 0, "coverage_days_year": 0, "outpatient_volume": 0,
            "outpatient_minutes": 0.0, "community_hours": 0.0, "recovery_hours": 0.0,
            "operating_rooms": 0, "room_hours_day": 0.0, "room_days_year": 0,
            "operators_per_room": 0.0, "is_complete": 0,
        }

    def save_activity_input(self, scenario_id: int, unit_id: int, profession: str, values: dict) -> None:
        columns = (
            "annual_work_hours", "overtime_hours", "cas_percent", "ias_hours",
            "morning_operators", "afternoon_operators", "night_operators",
            "coverage_days_year", "outpatient_volume", "outpatient_minutes",
            "community_hours", "recovery_hours", "operating_rooms", "room_hours_day",
            "room_days_year", "operators_per_room",
        )
        payload = [values[column] for column in columns]
        with self.connect() as con:
            con.execute(
                f"""INSERT INTO activity_inputs
                    (scenario_id, unit_id, profession, {', '.join(columns)}, is_complete)
                    VALUES (?, ?, ?, {', '.join('?' for _ in columns)}, 1)
                    ON CONFLICT(scenario_id, unit_id, profession) DO UPDATE SET
                    {', '.join(f'{column}=excluded.{column}' for column in columns)}, is_complete=1""",
                (scenario_id, unit_id, profession, *payload),
            )
            self.touch_scenario(con, scenario_id)

    def list_activity_inputs(self, scenario_id: int) -> list[dict]:
        with self.connect() as con:
            return [dict(row) for row in con.execute(
                "SELECT * FROM activity_inputs WHERE scenario_id=?", (scenario_id,)
            )]

    def activity_completion(self, scenario_id: int) -> tuple[int, int]:
        with self.connect() as con:
            total = con.execute(
                """SELECT COUNT(*) n FROM unit_professions up JOIN operating_units u ON u.id=up.unit_id
                   WHERE u.scenario_id=? AND u.active=1""", (scenario_id,)
            ).fetchone()["n"]
            completed = con.execute(
                """SELECT COUNT(*) n FROM activity_inputs a JOIN operating_units u ON u.id=a.unit_id
                   WHERE a.scenario_id=? AND u.active=1 AND a.is_complete=1""", (scenario_id,)
            ).fetchone()["n"]
            return int(completed), int(total)

    def list_radiology_rooms(self, scenario_id: int, unit_id: int | None = None) -> list[dict]:
        query = "SELECT * FROM radiology_rooms WHERE scenario_id=?"
        params: list[object] = [scenario_id]
        if unit_id is not None:
            query += " AND unit_id=?"
            params.append(unit_id)
        query += " ORDER BY name"
        with self.connect() as con:
            return [dict(row) for row in con.execute(query, params)]

    def save_radiology_room(self, scenario_id: int, unit_id: int, room_id: int | None, values: dict) -> int:
        fields = ("name", "modality", "h24", "hours_day", "days_year", "annual_volume",
                  "average_minutes", "doctors", "nurses", "oss", "health_technicians",
                  "radiology_technicians")
        payload = [values[field] for field in fields]
        with self.connect() as con:
            if room_id is None:
                cursor = con.execute(
                    f"""INSERT INTO radiology_rooms
                       (scenario_id, unit_id, {', '.join(fields)})
                       VALUES (?, ?, {', '.join('?' for _ in fields)})""",
                    (scenario_id, unit_id, *payload),
                )
                result = int(cursor.lastrowid)
            else:
                con.execute(
                    f"""UPDATE radiology_rooms SET unit_id=?,
                       {', '.join(f'{field}=?' for field in fields)}
                       WHERE id=? AND scenario_id=?""",
                    (unit_id, *payload, room_id, scenario_id),
                )
                result = room_id
            self.touch_scenario(con, scenario_id)
            return result

    def delete_radiology_room(self, scenario_id: int, room_id: int) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM radiology_rooms WHERE id=? AND scenario_id=?", (room_id, scenario_id))
            self.touch_scenario(con, scenario_id)

    def get_staffing(self, scenario_id: int, unit_id: int, profession: str) -> dict:
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM staffing WHERE scenario_id=? AND unit_id=? AND profession=?",
                (scenario_id, unit_id, profession),
            ).fetchone()
            if row:
                return dict(row)
        return {
            "full_time": 0.0, "part_time": 0.0, "trainees": 0.0, "over_60": 0.0,
            "retiring_3y": 0.0, "shift_workers": 0.0, "night_eligible": 0.0,
            "effort_eligible": 0.0, "exposure_eligible": 0.0,
            "full_time_effort": 0.0, "full_time_night": 0.0, "full_time_law104": 0.0,
            "part_time_effort": 0.0, "part_time_night": 0.0, "part_time_law104": 0.0,
            "full_time_night_limited": 0.0, "part_time_night_limited": 0.0,
            "full_time_law104_one": 0.0, "full_time_law104_two": 0.0,
            "part_time_law104_one": 0.0, "part_time_law104_two": 0.0,
            "full_time_retiring_3y": 0.0, "part_time_retiring_3y": 0.0,
            "dotation_saved": 0, "is_complete": 0,
        }

    def save_staffing_dotation(
        self,
        scenario_id: int,
        unit_id: int,
        profession: str,
        values: dict,
    ) -> None:
        """Salva FT, PT e gli eventuali specializzandi, preservando valori compatibili."""
        full_time = float(values["full_time"])
        part_time = float(values["part_time"])
        trainees = (
            float(values.get("trainees", 0.0))
            if profession in TRAINEE_PROFESSIONS
            else 0.0
        )
        counts = (full_time, part_time, trainees)
        if any(value < 0 or not value.is_integer() for value in counts):
            raise ValueError("Full-time, part-time e specializzandi devono essere interi non negativi.")

        def clipped(existing_row, field: str, total: float) -> float:
            if existing_row is None or not existing_row["dotation_saved"]:
                return 0.0
            return min(max(float(existing_row[field]), 0.0), total)

        with self.connect() as con:
            existing = con.execute(
                "SELECT * FROM staffing WHERE scenario_id=? AND unit_id=? AND profession=?",
                (scenario_id, unit_id, profession),
            ).fetchone()
            ft_one = clipped(existing, "full_time_law104_one", full_time)
            ft_two = clipped(existing, "full_time_law104_two", max(0.0, full_time - ft_one))
            pt_one = clipped(existing, "part_time_law104_one", part_time)
            pt_two = clipped(existing, "part_time_law104_two", max(0.0, part_time - pt_one))
            limitations = (
                clipped(existing, "full_time_night_limited", full_time),
                ft_one,
                ft_two,
                clipped(existing, "full_time_retiring_3y", full_time),
                clipped(existing, "part_time_night_limited", part_time),
                pt_one,
                pt_two,
                clipped(existing, "part_time_retiring_3y", part_time),
            )
            con.execute(
                """INSERT INTO staffing
                   (scenario_id, unit_id, profession, full_time, part_time, trainees,
                     full_time_night_limited, full_time_law104_one, full_time_law104_two,
                     full_time_retiring_3y, part_time_night_limited,
                     part_time_law104_one, part_time_law104_two, part_time_retiring_3y,
                     dotation_saved, is_complete)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
                   ON CONFLICT(scenario_id, unit_id, profession) DO UPDATE SET
                     full_time=excluded.full_time, part_time=excluded.part_time,
                     trainees=excluded.trainees, over_60=0,
                     full_time_night_limited=excluded.full_time_night_limited,
                     full_time_law104_one=excluded.full_time_law104_one,
                     full_time_law104_two=excluded.full_time_law104_two,
                     full_time_retiring_3y=excluded.full_time_retiring_3y,
                     part_time_night_limited=excluded.part_time_night_limited,
                     part_time_law104_one=excluded.part_time_law104_one,
                     part_time_law104_two=excluded.part_time_law104_two,
                     part_time_retiring_3y=excluded.part_time_retiring_3y,
                     dotation_saved=1, is_complete=0""",
                (scenario_id, unit_id, profession, full_time, part_time, trainees, *limitations),
            )
            self.touch_scenario(con, scenario_id)

    def save_staffing_limitations(
        self,
        scenario_id: int,
        unit_id: int,
        profession: str,
        values: dict,
    ) -> None:
        """Conferma limitazioni, permessi e pensionamenti per FT e PT."""
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM staffing WHERE scenario_id=? AND unit_id=? AND profession=?",
                (scenario_id, unit_id, profession),
            ).fetchone()
            if row is None or not row["dotation_saved"]:
                raise ValueError("Salvare prima la dotazione attuale.")
            groups = {
                "full_time": (
                    "full_time_night_limited", "full_time_law104_one",
                    "full_time_law104_two", "full_time_retiring_3y",
                ),
                "part_time": (
                    "part_time_night_limited", "part_time_law104_one",
                    "part_time_law104_two", "part_time_retiring_3y",
                ),
            }
            for total_field, fields in groups.items():
                total = float(row[total_field])
                if any(
                    float(values[field]) < 0
                    or float(values[field]) > total
                    or not float(values[field]).is_integer()
                    for field in fields
                ):
                    raise ValueError(
                        "Ogni valore deve essere compreso tra 0 e il totale della relativa riga."
                    )
                if (
                    float(values[f"{total_field}_law104_one"])
                    + float(values[f"{total_field}_law104_two"])
                    > total
                ):
                    raise ValueError(
                        "Le categorie Legge 104 per una e due persone sono alternative: "
                        "la loro somma non può superare il totale della riga."
                    )
            full_time_night = float(row["full_time"]) - float(values["full_time_night_limited"])
            part_time_night = float(row["part_time"]) - float(values["part_time_night_limited"])
            full_time_law104 = (
                float(values["full_time_law104_one"])
                + float(values["full_time_law104_two"])
            )
            part_time_law104 = (
                float(values["part_time_law104_one"])
                + float(values["part_time_law104_two"])
            )
            retiring_3y = (
                float(values["full_time_retiring_3y"])
                + float(values["part_time_retiring_3y"])
            )
            con.execute(
                """UPDATE staffing SET
                   full_time_night_limited=?, full_time_law104_one=?,
                   full_time_law104_two=?, full_time_retiring_3y=?,
                   part_time_night_limited=?, part_time_law104_one=?,
                   part_time_law104_two=?, part_time_retiring_3y=?,
                   full_time_night=?, part_time_night=?,
                   full_time_law104=?, part_time_law104=?, retiring_3y=?,
                   full_time_effort=full_time, part_time_effort=part_time,
                   shift_workers=full_time+part_time,
                   night_eligible=?+?, effort_eligible=full_time+part_time,
                   exposure_eligible=full_time+part_time,
                   is_complete=1
                   WHERE scenario_id=? AND unit_id=? AND profession=?""",
                (
                    values["full_time_night_limited"], values["full_time_law104_one"],
                    values["full_time_law104_two"], values["full_time_retiring_3y"],
                    values["part_time_night_limited"], values["part_time_law104_one"],
                    values["part_time_law104_two"], values["part_time_retiring_3y"],
                    full_time_night, part_time_night,
                    full_time_law104, part_time_law104, retiring_3y,
                    full_time_night, part_time_night,
                    scenario_id, unit_id, profession,
                ),
            )
            self.touch_scenario(con, scenario_id)

    def save_staffing(self, scenario_id: int, unit_id: int, profession: str, values: dict) -> None:
        """Compatibilità: salva entrambe le fasi quando viene fornito un record completo."""
        self.save_staffing_dotation(scenario_id, unit_id, profession, values)
        self.save_staffing_limitations(scenario_id, unit_id, profession, values)

    def set_section_status(self, scenario_id: int, section_key: str, complete: bool) -> None:
        with self.connect() as con:
            con.execute(
                """INSERT INTO section_status (scenario_id, section_key, is_complete)
                   VALUES (?, ?, ?) ON CONFLICT(scenario_id, section_key)
                   DO UPDATE SET is_complete=excluded.is_complete""",
                (scenario_id, section_key, int(complete)),
            )

    def get_manual_section_status(self, scenario_id: int) -> dict[str, bool]:
        with self.connect() as con:
            return {row["section_key"]: bool(row["is_complete"]) for row in con.execute(
                "SELECT section_key, is_complete FROM section_status WHERE scenario_id=?", (scenario_id,)
            )}

    def staffing_completion(self, scenario_id: int) -> tuple[int, int]:
        with self.connect() as con:
            total = con.execute(
                """SELECT COUNT(*) AS n FROM unit_professions up
                   JOIN operating_units u ON u.id=up.unit_id
                   WHERE u.scenario_id=? AND u.active=1""", (scenario_id,)
            ).fetchone()["n"]
            completed = con.execute(
                """SELECT COUNT(*) AS n FROM staffing s
                   JOIN operating_units u ON u.id=s.unit_id
                   WHERE s.scenario_id=? AND u.active=1 AND s.is_complete=1""", (scenario_id,)
            ).fetchone()["n"]
            return int(completed), int(total)
