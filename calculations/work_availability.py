"""Formule leggibili per la disponibilità annua di un FTE."""

from models.domain import WorkParameters


def standard_shift_hours(weekly_hours: float, workdays_week: int) -> float:
    """Restituisce la durata media della giornata/turno contrattuale."""
    if weekly_hours < 0:
        raise ValueError("Le ore settimanali non possono essere negative.")
    if workdays_week < 1 or workdays_week > 7:
        raise ValueError("I giorni lavorativi settimanali devono essere compresi tra 1 e 7.")
    if weekly_hours == 0:
        raise ValueError("Le ore settimanali devono essere positive.")
    return weekly_hours / workdays_week


def annual_available_hours(
    parameters: WorkParameters,
    additional_rest_days: float = 0.0,
) -> float:
    """
    Calcola le ore annue disponibili per un FTE.

    Logica:
    - giorni programmati annui = giorni lavorativi settimanali × 52;
    - si sottraggono festività, ferie/permessi, malattia, formazione e
      l'eventuale riposo biologico;
    - i giorni disponibili sono moltiplicati per la durata del turno.
    """
    absence_days = (
        parameters.holidays
        + parameters.leave_days
        + parameters.sickness_days
        + parameters.training_days
        + additional_rest_days
    )
    scheduled_days = parameters.workdays_week * 52
    available_days = max(0.0, scheduled_days - absence_days)
    return available_days * parameters.shift_hours
