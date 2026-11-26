import pytest

from calculations.biological_rest import annual_hours_for_unit
from calculations.work_availability import annual_available_hours, standard_shift_hours
from models.domain import WorkParameters


def nurse_parameters() -> WorkParameters:
    return WorkParameters(
        profession="Infermieri", weekly_hours=36.0, workdays_week=5,
        shift_hours=7.2, shift_is_auto=True, holidays=11.0,
        leave_days=32.5, sickness_days=9.0, training_days=7.0,
    )


def test_standard_shift_duration():
    assert standard_shift_hours(36, 5) == 7.2
    assert standard_shift_hours(36, 6) == 6.0
    assert standard_shift_hours(35, 7) == 5.0
    with pytest.raises(ValueError):
        standard_shift_hours(36, 0)


def test_workbook_equivalent_nurse_hours():
    assert annual_available_hours(nurse_parameters()) == pytest.approx(1443.6)


def test_biological_rest_is_applied_only_when_selected():
    assert annual_hours_for_unit(nurse_parameters(), False) == pytest.approx(1443.6)
    assert annual_hours_for_unit(nurse_parameters(), True) == pytest.approx(1335.6)
