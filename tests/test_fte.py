import pytest

from calculations.fte import (
    calculate_fte_breakdown,
    current_fte,
    effective_current_fte,
    law104_deduction,
    night_eligible_fte,
)


def test_required_fte_uses_larger_of_workload_and_programmed_activity():
    activity = {
        "annual_work_hours": 1440,
        "cas_percent": 0,
        "ias_hours": 0,
        "morning_operators": 1,
        "afternoon_operators": 0,
        "night_operators": 0,
        "coverage_days_year": 100,
        "outpatient_volume": 0,
        "outpatient_minutes": 0,
        "community_hours": 0,
        "recovery_hours": 0,
        "operating_rooms": 0,
        "room_hours_day": 0,
        "room_days_year": 0,
        "operators_per_room": 0,
    }
    result = calculate_fte_breakdown(activity, annual_available_hours=1440, shift_hours=7.2)
    assert result.workload == pytest.approx(1.0)
    assert result.shifts == pytest.approx(0.5)
    assert result.required == pytest.approx(1.0)


def test_current_fte_matches_workbook_part_time_convention():
    assert current_fte({"full_time": 10, "part_time": 3}) == pytest.approx(11.5)


def test_law_104_one_and_two_dependents_with_part_time_weight():
    staffing = {
        "full_time": 10,
        "part_time": 4,
        "full_time_law104_one": 2,
        "full_time_law104_two": 1,
        "part_time_law104_one": 2,
        "part_time_law104_two": 1,
    }
    deduction = law104_deduction(staffing, 1443.6, 7.2, 36)
    # FT: (2 + 2*1)*36 = 144 giorni.
    assert deduction.full_time_days == pytest.approx(144)
    # PT: stesso diritto in giorni: (2 + 2*1)*36 = 144 giorni.
    assert deduction.part_time_days == pytest.approx(144)
    # Conversione nel modello: 144 + 0,5*144 = 216 giorni equivalenti FT.
    assert deduction.equivalent_days == pytest.approx(216)
    assert deduction.lost_hours == pytest.approx(216 * 7.2)
    assert deduction.lost_fte == pytest.approx(216 * 7.2 / 1443.6)
    assert effective_current_fte(staffing, 1443.6, 7.2, 36) == pytest.approx(
        12 - deduction.lost_fte
    )


def test_night_eligible_fte_is_total_less_night_limitations():
    staffing = {
        "full_time": 10,
        "part_time": 4,
        "full_time_night_limited": 3,
        "part_time_night_limited": 2,
    }
    assert night_eligible_fte(staffing) == pytest.approx(7 + 0.5 * 2)
