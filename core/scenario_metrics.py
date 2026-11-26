"""Aggregazione dei risultati di scenario per turnazione e risultati."""

import calendar

from calculations.biological_rest import annual_hours_for_unit
from calculations.fte import (
    calculate_fte_breakdown,
    current_fte,
    effective_current_fte,
    law104_deduction,
    night_eligible_fte,
)
from calculations.work_availability import standard_shift_hours
from core.constants import LAW_104_DAYS_PER_YEAR, TRAINEE_PROFESSIONS
from models.domain import WorkParameters


RADIOLOGY_OPERATOR_FIELDS = {
    "Medici": "doctors",
    "Infermieri": "nurses",
    "OSS": "oss",
    "Tecnici sanitari": "health_technicians",
    "Tecnici di radiologia": "radiology_technicians",
}


def _parameter_map(db, scenario_id: int) -> dict[str, dict]:
    return {row["profession"]: row for row in db.get_work_parameters(scenario_id)}


def contractual_shift(row: dict) -> float:
    return standard_shift_hours(float(row["weekly_hours"]), int(row["workdays_week"]))


def work_model(parameter: dict, shift_hours: float) -> WorkParameters:
    return WorkParameters(
        profession=parameter["profession"],
        weekly_hours=float(parameter["weekly_hours"]),
        workdays_week=int(parameter["workdays_week"]),
        shift_hours=float(shift_hours),
        shift_is_auto=True,
        holidays=float(parameter["holidays"]),
        leave_days=float(parameter["leave_days"]),
        sickness_days=float(parameter["sickness_days"]),
        training_days=float(parameter["training_days"]),
    )


def scenario_rows(db, scenario_id: int) -> list[dict]:
    """Restituisce una riga calcolata per ogni combinazione UO-professione attiva."""
    parameters = _parameter_map(db, scenario_id)
    scenario = db.get_scenario(scenario_id)
    days_in_year = 366 if calendar.isleap(int(scenario["reference_year"])) else 365
    radiology_rooms = db.list_radiology_rooms(scenario_id)
    rows: list[dict] = []
    for unit in db.list_operating_units(scenario_id, active_only=True):
        for profession in unit["professions"]:
            parameter = parameters[profession]
            shift_hours = contractual_shift(parameter)
            annual_hours = annual_hours_for_unit(
                work_model(parameter, shift_hours), bool(unit["radioprotection"])
            )
            activity = db.get_activity_input(scenario_id, unit["id"], profession)
            activity["coverage_days_year"] = (
                days_in_year if unit["h24"] else int(parameter["workdays_week"]) * 52
            ) if unit["has_shifts"] else 0
            breakdown = calculate_fte_breakdown(activity, annual_hours, shift_hours)
            operator_field = RADIOLOGY_OPERATOR_FIELDS[profession]
            radiology_fte = sum(
                float(room[operator_field]) * float(room["hours_day"]) * int(room["days_year"])
                / annual_hours
                for room in radiology_rooms
                if room["unit_id"] == unit["id"] and annual_hours > 0
            )
            required_fte = max(breakdown.required, radiology_fte)
            staffing = db.get_staffing(scenario_id, unit["id"], profession)
            nominal_fte = current_fte(staffing)
            available = effective_current_fte(
                staffing, annual_hours, shift_hours, LAW_104_DAYS_PER_YEAR
            )
            law104 = law104_deduction(
                staffing, annual_hours, shift_hours, LAW_104_DAYS_PER_YEAR
            )
            full_time = float(staffing["full_time"])
            part_time = float(staffing["part_time"])
            people = full_time + part_time
            skill_mix = (
                float(staffing["trainees"]) / full_time
                if profession in TRAINEE_PROFESSIONS and full_time > 0
                else None
            )
            retiring_people = (
                float(staffing["full_time_retiring_3y"])
                + float(staffing["part_time_retiring_3y"])
            )
            retirement_rate = retiring_people / people if people > 0 else None
            contractual_hours_year = float(parameter["weekly_hours"]) * 52
            overtime_rate = (
                float(activity["overtime_hours"]) / contractual_hours_year
                if contractual_hours_year > 0 and bool(activity["is_complete"])
                else None
            )
            rows.append({
                "unit_id": unit["id"],
                "unit": unit["name"],
                "profession": profession,
                "shift_hours": shift_hours,
                "annual_hours": annual_hours,
                "current_fte": available,
                "current_fte_nominal": nominal_fte,
                "required_fte": required_fte,
                "gap": available - required_fte,
                "workload_fte": breakdown.workload,
                "shift_fte": breakdown.shifts,
                "outpatient_fte": breakdown.outpatient,
                "room_fte": breakdown.operating_rooms,
                "ias_fte": breakdown.ias,
                "radiology_fte": radiology_fte,
                "radioprotection": bool(unit["radioprotection"]),
                "night_eligible_fte": night_eligible_fte(staffing),
                "law104_lost_days_equivalent": law104.equivalent_days,
                "law104_lost_hours": law104.lost_hours,
                "law104_lost_fte": law104.lost_fte,
                "skill_mix": skill_mix,
                "retirement_rate": retirement_rate,
                "overtime_rate": overtime_rate,
                "staffing": staffing,
                "activity": activity,
            })
    return rows


def scenario_totals(db, scenario_id: int) -> dict:
    rows = scenario_rows(db, scenario_id)
    current = sum(row["current_fte"] for row in rows)
    nominal = sum(row["current_fte_nominal"] for row in rows)
    required = sum(row["required_fte"] for row in rows)
    return {
        "current_fte": current,
        "current_fte_nominal": nominal,
        "required_fte": required,
        "gap": current - required,
    }
