"""Applicazione manuale del riposo biologico configurato per ogni UO."""

from calculations.work_availability import annual_available_hours
from core.constants import BIOLOGICAL_REST_DAYS
from models.domain import WorkParameters


def annual_hours_for_unit(parameters: WorkParameters, radioprotection: bool) -> float:
    """Calcola le ore annue applicando 15 giorni solo se la UO li ha attivati."""
    additional_days = BIOLOGICAL_REST_DAYS if radioprotection else 0.0
    return annual_available_hours(parameters, additional_days)
