"""Valutazione centralizzata dello stato di compilazione."""

from core.constants import PROFESSIONS, SECTION_KEYS


def _parameters_are_complete(db, scenario_id: int, units: list[dict], parameters: list[dict]) -> bool:
    if len(parameters) != len(PROFESSIONS):
        return False
    for row in parameters:
        days = int(row["workdays_week"])
        weekly_hours = float(row["weekly_hours"])
        if days < 1 or days > 7 or weekly_hours <= 0:
            return False
        if float(row["shift_hours"]) <= 0:
            return False
    return True


def section_completion(db, scenario_id: int) -> dict[str, bool]:
    scenario = db.get_scenario(scenario_id)
    units = db.list_operating_units(scenario_id, active_only=True)
    parameters = db.get_work_parameters(scenario_id)
    manual = db.get_manual_section_status(scenario_id)

    configuration_complete = bool(
        scenario["facility_name"].strip()
        and units
        and all(unit["professions"] for unit in units)
    )
    parameters_complete = _parameters_are_complete(db, scenario_id, units, parameters)
    staffing_done, staffing_total = db.staffing_completion(scenario_id)
    staffing_complete = staffing_total > 0 and staffing_done == staffing_total
    activity_done, activity_total = db.activity_completion(scenario_id)
    activity_complete = activity_total > 0 and activity_done == activity_total
    radiology_units = [
        unit for unit in units
        if any(token in unit["name"].casefold() for token in ("radiolog", "nuclear", "tac", "rm"))
    ]
    radiology_complete = not radiology_units or all(
        db.list_radiology_rooms(scenario_id, unit["id"]) for unit in radiology_units
    )
    has_shift_requirements = any(
        item["morning_operators"] + item["afternoon_operators"] + item["night_operators"] > 0
        for item in db.list_activity_inputs(scenario_id)
    )

    completion = {
        "configurazione": configuration_complete,
        "parametri": parameters_complete,
        "organico": staffing_complete,
        "attivita": activity_complete,
        "radiologia": radiology_complete,
        "turnazione": staffing_complete and has_shift_requirements,
        "risultati": staffing_complete and activity_complete,
    }
    for key, _ in SECTION_KEYS:
        completion.setdefault(key, manual.get(key, False))
    return completion


def progress_counts(db, scenario_id: int) -> tuple[int, int, dict[str, bool]]:
    status = section_completion(db, scenario_id)
    completed = sum(1 for key, _ in SECTION_KEYS if status.get(key, False))
    return completed, len(SECTION_KEYS), status
