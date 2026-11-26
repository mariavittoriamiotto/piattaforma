"""Modelli di dominio semplici e indipendenti da Streamlit."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkParameters:
    profession: str
    weekly_hours: float
    workdays_week: int
    shift_hours: float
    shift_is_auto: bool
    holidays: float
    leave_days: float
    sickness_days: float
    training_days: float


@dataclass(frozen=True)
class OperatingUnit:
    id: int
    scenario_id: int
    name: str
    area: str
    h24: bool
    has_shifts: bool
    has_outpatient: bool
    has_operating_rooms: bool
    active: bool
