import pytest

from storage.database import Database
from core.scenario_metrics import scenario_rows


def test_duplicate_scenario_copies_units_and_parameters(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    source_id = db.create_scenario("Base", 2026, facility_name="Ospedale Test")
    unit_id = db.upsert_operating_unit(
        source_id, None, "Radiologia", "Servizi diagnostici",
        True, True, True, False, True, True,
    )
    db.set_unit_professions(unit_id, ["Medici", "Tecnici di radiologia"])
    db.save_staffing_dotation(source_id, unit_id, "Medici", {
        "full_time": 10, "part_time": 2, "trainees": 1,
    })
    db.save_staffing_limitations(source_id, unit_id, "Medici", {
        "full_time_night_limited": 2,
        "full_time_law104_one": 1, "full_time_law104_two": 1,
        "full_time_retiring_3y": 1,
        "part_time_night_limited": 1,
        "part_time_law104_one": 0, "part_time_law104_two": 0,
        "part_time_retiring_3y": 0,
    })
    db.save_activity_input(source_id, unit_id, "Medici", {
        "annual_work_hours": 1531.4, "overtime_hours": 0, "cas_percent": 0,
        "ias_hours": 0, "morning_operators": 1, "afternoon_operators": 1,
        "night_operators": 0, "coverage_days_year": 260, "outpatient_volume": 0,
        "outpatient_minutes": 0, "community_hours": 0, "recovery_hours": 0,
        "operating_rooms": 0, "room_hours_day": 0, "room_days_year": 0,
        "operators_per_room": 0,
    })
    db.save_radiology_room(source_id, unit_id, None, {
        "name": "Sala RX 1", "modality": "D11 RX", "h24": False,
        "hours_day": 8, "days_year": 260, "annual_volume": 1000,
        "average_minutes": 22, "doctors": 1, "nurses": 0, "oss": 0,
        "health_technicians": 0, "radiology_technicians": 1,
    })
    copied_id = db.duplicate_scenario(source_id, "Scenario 2027", "Ipotesi alternativa")

    copied = db.get_scenario(copied_id)
    assert copied["facility_name"] == "Ospedale Test"
    assert copied["description"] == "Ipotesi alternativa"
    assert len(db.list_operating_units(copied_id)) == 1
    assert len(db.get_work_parameters(copied_id)) == 5
    copied_unit = db.list_operating_units(copied_id)[0]
    assert copied_unit["radioprotection"] == 1
    copied_staffing = db.get_staffing(copied_id, copied_unit["id"], "Medici")
    assert copied_staffing["dotation_saved"] == 1
    assert copied_staffing["full_time_night_limited"] == 2
    assert copied_staffing["part_time_night_limited"] == 1
    assert copied_staffing["full_time_law104_two"] == 1
    assert copied_staffing["is_complete"] == 1
    assert db.get_activity_input(copied_id, copied_unit["id"], "Medici")["is_complete"] == 1
    assert len(db.list_radiology_rooms(copied_id, copied_unit["id"])) == 1


def test_operating_unit_can_be_toggled_without_editing_its_form(tmp_path):
    db = Database(tmp_path / "toggle.db")
    db.initialize()
    scenario_id = db.create_scenario("Toggle", 2026)
    unit_id = db.upsert_operating_unit(
        scenario_id, None, "Cardiologia", "Medica", True, True, True, False, False, True
    )
    db.set_operating_unit_active(scenario_id, unit_id, False)
    assert db.list_operating_units(scenario_id)[0]["active"] == 0


def test_staffing_limitations_appear_after_dotation_and_start_from_total(tmp_path):
    db = Database(tmp_path / "staffing.db")
    db.initialize()
    scenario_id = db.create_scenario("Organico", 2026)
    unit_id = db.upsert_operating_unit(
        scenario_id, None, "Cardiologia", "Medica", True, True, True, False, False, True
    )
    db.set_unit_professions(unit_id, ["Infermieri"])

    db.save_staffing_dotation(scenario_id, unit_id, "Infermieri", {
        "full_time": 10, "part_time": 2, "trainees": 0,
    })
    staffing = db.get_staffing(scenario_id, unit_id, "Infermieri")
    assert staffing["dotation_saved"] == 1
    assert staffing["full_time_night_limited"] == 0
    assert staffing["part_time_night_limited"] == 0
    assert staffing["full_time_law104_one"] == 0
    assert staffing["part_time_law104_one"] == 0
    assert staffing["is_complete"] == 0

    db.save_staffing_limitations(scenario_id, unit_id, "Infermieri", {
        "full_time_night_limited": 2,
        "full_time_law104_one": 1, "full_time_law104_two": 1,
        "full_time_retiring_3y": 1,
        "part_time_night_limited": 1,
        "part_time_law104_one": 1, "part_time_law104_two": 0,
        "part_time_retiring_3y": 0,
    })
    staffing = db.get_staffing(scenario_id, unit_id, "Infermieri")
    assert staffing["full_time_night_limited"] == 2
    assert staffing["part_time_night_limited"] == 1
    assert staffing["part_time_law104_one"] == 1
    assert staffing["full_time_retiring_3y"] == 1
    assert staffing["is_complete"] == 1


def test_shift_duration_and_coverage_are_derived_from_parameters_and_uo(tmp_path):
    db = Database(tmp_path / "derived.db")
    db.initialize()
    scenario_id = db.create_scenario("Derivato", 2028)
    unit_id = db.upsert_operating_unit(
        scenario_id, None, "Terapia intensiva", "Emergenza-urgenza",
        True, True, False, False, False, True,
    )
    db.set_unit_professions(unit_id, ["Infermieri"])
    db.save_activity_input(scenario_id, unit_id, "Infermieri", {
        "annual_work_hours": 0, "overtime_hours": 0, "cas_percent": 0,
        "ias_hours": 0, "morning_operators": 1, "afternoon_operators": 1,
        "night_operators": 1, "coverage_days_year": 1, "outpatient_volume": 0,
        "outpatient_minutes": 0, "community_hours": 0, "recovery_hours": 0,
        "operating_rooms": 0, "room_hours_day": 0, "room_days_year": 0,
        "operators_per_room": 0,
    })

    row = scenario_rows(db, scenario_id)[0]
    assert row["shift_hours"] == 36 / 5
    assert row["activity"]["coverage_days_year"] == 366


def test_results_include_manual_radioprotection_and_indicators(tmp_path):
    db = Database(tmp_path / "indicators.db")
    db.initialize()
    scenario_id = db.create_scenario("Indicatori", 2026)
    unit_id = db.upsert_operating_unit(
        scenario_id, None, "Cardiologia", "Medica",
        False, False, False, False, True, True,
    )
    db.set_unit_professions(unit_id, ["Medici"])
    db.save_staffing_dotation(scenario_id, unit_id, "Medici", {
        "full_time": 10, "part_time": 2, "trainees": 2,
    })
    db.save_staffing_limitations(scenario_id, unit_id, "Medici", {
        "full_time_night_limited": 2,
        "full_time_law104_one": 1, "full_time_law104_two": 0,
        "full_time_retiring_3y": 2,
        "part_time_night_limited": 1,
        "part_time_law104_one": 0, "part_time_law104_two": 0,
        "part_time_retiring_3y": 0,
    })
    db.save_activity_input(scenario_id, unit_id, "Medici", {
        "annual_work_hours": 0, "overtime_hours": 395, "cas_percent": 0,
        "ias_hours": 0, "morning_operators": 0, "afternoon_operators": 0,
        "night_operators": 0, "coverage_days_year": 0, "outpatient_volume": 0,
        "outpatient_minutes": 0, "community_hours": 0, "recovery_hours": 0,
        "operating_rooms": 0, "room_hours_day": 0, "room_days_year": 0,
        "operators_per_room": 0,
    })

    row = scenario_rows(db, scenario_id)[0]
    assert row["radioprotection"] is True
    assert row["annual_hours"] == pytest.approx(1417.4)
    assert row["skill_mix"] == 0.2
    assert row["retirement_rate"] == 2 / 12
    assert row["overtime_rate"] == 395 / (38 * 52)
    assert row["current_fte"] < row["current_fte_nominal"]


def test_oss_and_technicians_never_store_trainees(tmp_path):
    db = Database(tmp_path / "trainees.db")
    db.initialize()
    scenario_id = db.create_scenario("Specializzandi", 2026)
    unit_id = db.upsert_operating_unit(
        scenario_id, None, "Servizi", "Altro", False, False, False, False, False, True
    )
    for profession in ("OSS", "Tecnici sanitari", "Tecnici di radiologia"):
        db.set_unit_professions(unit_id, [profession])
        db.save_staffing_dotation(scenario_id, unit_id, profession, {
            "full_time": 3, "part_time": 1, "trainees": 99,
        })
        assert db.get_staffing(scenario_id, unit_id, profession)["trainees"] == 0


def test_law104_categories_are_mutually_exclusive_within_each_group(tmp_path):
    db = Database(tmp_path / "validation.db")
    db.initialize()
    scenario_id = db.create_scenario("Validazione", 2026)
    unit_id = db.upsert_operating_unit(
        scenario_id, None, "Cardiologia", "Medica", True, True, True, False, False, True
    )
    db.set_unit_professions(unit_id, ["Infermieri"])
    db.save_staffing_dotation(scenario_id, unit_id, "Infermieri", {
        "full_time": 3, "part_time": 0, "trainees": 0,
    })
    with pytest.raises(ValueError, match="categorie Legge 104"):
        db.save_staffing_limitations(scenario_id, unit_id, "Infermieri", {
            "full_time_night_limited": 0,
            "full_time_law104_one": 2, "full_time_law104_two": 2,
            "full_time_retiring_3y": 0,
            "part_time_night_limited": 0,
            "part_time_law104_one": 0, "part_time_law104_two": 0,
            "part_time_retiring_3y": 0,
        })


def test_v5_database_is_migrated_and_reopened_for_verification(tmp_path):
    import sqlite3

    path = tmp_path / "legacy_v5.db"
    with sqlite3.connect(path) as con:
        con.execute(
            """CREATE TABLE staffing (
                scenario_id INTEGER NOT NULL,
                unit_id INTEGER NOT NULL,
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
                dotation_saved INTEGER NOT NULL DEFAULT 0,
                is_complete INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(scenario_id, unit_id, profession)
            )"""
        )
        con.execute(
            """INSERT INTO staffing VALUES
               (1, 1, 'Medici', 10, 2, 1, 2, 3, 12, 9, 12, 12,
                10, 8, 1, 2, 1, 1, 1, 1)"""
        )

    db = Database(path)
    db.initialize()
    with db.connect() as con:
        migrated = dict(con.execute("SELECT * FROM staffing").fetchone())
    assert migrated["full_time_night_limited"] == 2
    assert migrated["part_time_night_limited"] == 1
    assert migrated["full_time_law104_one"] == 1
    assert migrated["part_time_law104_one"] == 1
    assert migrated["full_time_law104_two"] == 0
    assert migrated["full_time_retiring_3y"] == 3
    assert migrated["part_time_retiring_3y"] == 0
    assert migrated["is_complete"] == 0
