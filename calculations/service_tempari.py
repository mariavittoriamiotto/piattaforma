"""Calcoli condivisi per il database tempari di Radiologia e Laboratorio.

Il modulo riusa la tabella ``radiology_rooms`` già presente: le righe con modalità
``__LABORATORIO__`` rappresentano servizi di laboratorio; le righe precedenti e
quelle con una modalità SIRM rappresentano sale radiologiche. In questo modo i
progetti esistenti restano leggibili e non è necessaria una migrazione distruttiva.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from core.scenario_metrics import scenario_rows


SIRM_MINUTES = {
    "D11 RX": 22,
    "D12 TC": 26,
    "D21 ECO": 24,
    "D22 ECOCOLOR": 26,
    "D25 RM": 31,
    "D13 VASC": 36,
    "D30 BIOPSIE": 30,
    "Altro": 30,
}

LABORATORY_MODALITY = "__LABORATORIO__"

PROFESSION_FIELDS = {
    "Medici": "doctors",
    "Infermieri": "nurses",
    "OSS": "oss",
    "Tecnici sanitari": "health_technicians",
    "Tecnici di radiologia": "radiology_technicians",
}


def is_laboratory(room: dict) -> bool:
    return room.get("modality") == LABORATORY_MODALITY


def annual_open_hours(room: dict) -> float:
    """Applica una base univoca coerente con la spunta H24 della UO.

    Le righe preparate da ``adjusted_scenario_rows`` includono ``_unit_h24``.
    Per compatibilità con chiamate dirette resta disponibile il campo storico
    ``h24`` della singola sala/servizio.
    """
    is_h24 = bool(room.get("_unit_h24", room.get("h24", False)))
    if is_h24:
        return 24.0 * 365.0
    return max(float(room.get("hours_day", 0)), 0.0) * 260.0


def theoretical_capacity(room: dict) -> float | None:
    """Prestazioni teoriche annue con il personale indicato nella scheda.

    Il numero di operatori non moltiplica la produttività della sala: descrive la
    squadra contemporaneamente necessaria. Se tutti i campi professionali sono
    presenti ma valgono zero, la capacità erogabile è zero.
    """
    minutes = float(room.get("average_minutes", 0) or 0)
    if minutes <= 0:
        return None
    operator_fields = [field for field in PROFESSION_FIELDS.values() if field in room]
    if operator_fields and sum(float(room.get(field, 0) or 0) for field in operator_fields) <= 0:
        return 0.0
    return annual_open_hours(room) * 60.0 / minutes


def _rooms_by_unit(db, scenario_id: int, unit_ids: Iterable[int]) -> dict[int, list[dict]]:
    unit_h24 = {
        int(unit["id"]): bool(unit["h24"])
        for unit in db.list_operating_units(scenario_id, active_only=True)
    }
    rooms_by_unit: dict[int, list[dict]] = {}
    for unit_id in unit_ids:
        normalized = []
        for room in db.list_radiology_rooms(scenario_id, int(unit_id)):
            item = dict(room)
            item["_unit_h24"] = unit_h24.get(int(unit_id), False)
            normalized.append(item)
        rooms_by_unit[int(unit_id)] = normalized
    return rooms_by_unit


def adjusted_scenario_rows(db, scenario_id: int) -> list[dict]:
    """Integra i tempari nel fabbisogno senza modificare i calcoli storici.

    Se una UO contiene almeno una voce nel database tempari, la componente
    programmata derivata dai tempari sostituisce Ambulatorio + Sale. Il totale
    richiesto resta il massimo tra metodo workload e metodo organizzativo:
    ``max(workload, turni + attività programmate)``.
    """
    raw_rows = [dict(row) for row in scenario_rows(db, scenario_id)]
    unit_ids = {int(row["unit_id"]) for row in raw_rows}
    rooms_by_unit = _rooms_by_unit(db, scenario_id, unit_ids)

    adjusted: list[dict] = []
    for row in raw_rows:
        rooms = rooms_by_unit.get(int(row["unit_id"]), [])
        field = PROFESSION_FIELDS.get(row["profession"])
        radiology_fte = 0.0
        laboratory_fte = 0.0
        if field and float(row.get("annual_hours", 0) or 0) > 0:
            for room in rooms:
                operators = max(float(room.get(field, 0) or 0), 0.0)
                fte = annual_open_hours(room) * operators / float(row["annual_hours"])
                if is_laboratory(room):
                    laboratory_fte += fte
                else:
                    radiology_fte += fte

        tempari_override = bool(rooms)
        if tempari_override:
            programmed_fte = radiology_fte + laboratory_fte
        else:
            programmed_fte = float(row.get("outpatient_fte", 0) or 0) + float(
                row.get("room_fte", 0) or 0
            )

        operational_fte = float(row.get("shift_fte", 0) or 0) + programmed_fte
        required_fte = max(float(row.get("workload_fte", 0) or 0), operational_fte)
        current_fte = float(row.get("current_fte", 0) or 0)

        row.update({
            "radiology_fte": radiology_fte,
            "laboratory_fte": laboratory_fte,
            "programmed_fte": programmed_fte,
            "operational_fte": operational_fte,
            "required_fte": required_fte,
            "gap": current_fte - required_fte,
            "tempari_override": tempari_override,
        })
        adjusted.append(row)
    return adjusted


def adjusted_scenario_totals(db, scenario_id: int) -> dict[str, float]:
    rows = adjusted_scenario_rows(db, scenario_id)
    totals: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        totals["current_fte_nominal"] += float(row.get("current_fte_nominal", 0) or 0)
        totals["required_fte"] += float(row.get("required_fte", 0) or 0)
    # Nei risultati l'FTE attuale è quello nominale: i permessi 104 restano
    # registrati nell'organico ma non producono più una deduzione esposta.
    totals["current_fte"] = totals["current_fte_nominal"]
    totals["gap"] = totals["current_fte_nominal"] - totals["required_fte"]
    return dict(totals)
