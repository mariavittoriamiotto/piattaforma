"""Formule del dimensionamento FTE, mantenute separate dall'interfaccia."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FteBreakdown:
    workload: float
    shifts: float
    outpatient: float
    operating_rooms: float
    ias: float
    required: float


@dataclass(frozen=True)
class Law104Deduction:
    """Dettaglio della deduzione annua dovuta ai permessi Legge 104."""

    full_time_days: float
    part_time_days: float
    equivalent_days: float
    lost_hours: float
    lost_fte: float


def cas_factor(cas_percent: float) -> float:
    """Converte la quota di attività di supporto nel fattore correttivo CAF."""
    if cas_percent < 0 or cas_percent >= 1:
        raise ValueError("CAS deve essere compreso tra 0 e 0,99.")
    return 1.0 / (1.0 - cas_percent)


def calculate_fte_breakdown(activity: dict, annual_available_hours: float, shift_hours: float) -> FteBreakdown:
    """
    Calcola le componenti FTE evitando il doppio conteggio tra workload e coperture programmate.

    Il fabbisogno finale è il maggiore tra:
    - FTE da ore lavorate (workload);
    - somma di turni, ambulatorio, sale e IAS.
    """
    if annual_available_hours <= 0:
        return FteBreakdown(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    factor = cas_factor(float(activity.get("cas_percent", 0.0)))
    workload = float(activity.get("annual_work_hours", 0.0)) * factor / annual_available_hours
    ias = float(activity.get("ias_hours", 0.0)) / annual_available_hours

    daily_operators = (
        int(activity.get("morning_operators", 0))
        + int(activity.get("afternoon_operators", 0))
        + int(activity.get("night_operators", 0))
    )
    shift_annual_hours = (
        daily_operators
        * int(activity.get("coverage_days_year", 0))
        * shift_hours
    )
    shifts = shift_annual_hours * factor / annual_available_hours

    outpatient_hours = (
        int(activity.get("outpatient_volume", 0))
        * float(activity.get("outpatient_minutes", 0.0))
        / 60.0
        + float(activity.get("community_hours", 0.0))
        + float(activity.get("recovery_hours", 0.0))
    )
    outpatient = outpatient_hours * factor / annual_available_hours

    room_hours = (
        int(activity.get("operating_rooms", 0))
        * float(activity.get("room_hours_day", 0.0))
        * int(activity.get("room_days_year", 0))
        * float(activity.get("operators_per_room", 0.0))
    )
    operating_rooms = room_hours * factor / annual_available_hours
    programmed = shifts + outpatient + operating_rooms + ias
    return FteBreakdown(
        workload=workload,
        shifts=shifts,
        outpatient=outpatient,
        operating_rooms=operating_rooms,
        ias=ias,
        required=max(workload, programmed),
    )


def current_fte(staffing: dict) -> float:
    """Replica la convenzione del workbook: full-time + 0,5 × part-time."""
    return float(staffing.get("full_time", 0.0)) + 0.5 * float(staffing.get("part_time", 0.0))


def eligible_fte(staffing: dict, eligibility: str) -> float:
    """Converte in FTE gli idonei full-time e part-time per una specifica attività."""
    full_time = float(staffing.get(f"full_time_{eligibility}", 0.0))
    part_time = float(staffing.get(f"part_time_{eligibility}", 0.0))
    return full_time + 0.5 * part_time


def night_eligible_fte(staffing: dict) -> float:
    """FTE abilitati alla notte, ottenuti sottraendo chi ha una limitazione."""
    full_time = max(
        0.0,
        float(staffing.get("full_time", 0.0))
        - float(staffing.get("full_time_night_limited", 0.0)),
    )
    part_time = max(
        0.0,
        float(staffing.get("part_time", 0.0))
        - float(staffing.get("part_time_night_limited", 0.0)),
    )
    return full_time + 0.5 * part_time


def law104_deduction(
    staffing: dict,
    annual_available_hours: float,
    shift_hours: float,
    days_per_dependent_year: float,
) -> Law104Deduction:
    """
    Calcola giorni, ore e FTE dedotti per i permessi Legge 104.

    Ogni persona a carico genera 3 giorni/mese, cioè 36 giorni/anno. Chi assiste
    due persone genera quindi 72 giorni/anno. Il numero di giorni è identico per
    full-time e part-time; nel passaggio alle ore/FTE il part-time conserva il
    peso contrattuale 0,5 adottato dall'intero modello.
    """
    ft_one = float(staffing.get("full_time_law104_one", 0.0))
    ft_two = float(staffing.get("full_time_law104_two", 0.0))
    pt_one = float(staffing.get("part_time_law104_one", 0.0))
    pt_two = float(staffing.get("part_time_law104_two", 0.0))

    full_time_days = (ft_one + 2.0 * ft_two) * days_per_dependent_year
    part_time_days = (pt_one + 2.0 * pt_two) * days_per_dependent_year
    equivalent_days = full_time_days + 0.5 * part_time_days
    lost_hours = equivalent_days * max(0.0, shift_hours)
    lost_fte = (
        lost_hours / annual_available_hours
        if annual_available_hours > 0 and shift_hours > 0
        else 0.0
    )
    return Law104Deduction(
        full_time_days=full_time_days,
        part_time_days=part_time_days,
        equivalent_days=equivalent_days,
        lost_hours=lost_hours,
        lost_fte=lost_fte,
    )


def effective_current_fte(
    staffing: dict,
    annual_available_hours: float,
    shift_hours: float,
    law_104_days_year: float,
) -> float:
    """
    Restituisce gli FTE effettivamente disponibili al netto dei permessi Legge 104.

    Per ogni persona assistita sono dedotti tre giorni al mese: 36 giorni/anno
    per una persona, 72 per due. I part-time mantengono il peso di 0,5 FTE
    nella conversione dei giorni in ore/FTE.
    """
    nominal = current_fte(staffing)
    if annual_available_hours <= 0 or shift_hours <= 0:
        return nominal
    deduction = law104_deduction(
        staffing,
        annual_available_hours,
        shift_hours,
        law_104_days_year,
    )
    return max(0.0, nominal - deduction.lost_fte)
