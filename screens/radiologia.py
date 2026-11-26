"""Tempi delle attività programmate per Radiologia e Laboratorio."""

import sqlite3

import streamlit as st

from calculations.service_tempari import (
    LABORATORY_MODALITY,
    PROFESSION_FIELDS,
    SIRM_MINUTES,
    annual_open_hours,
    adjusted_scenario_rows,
    is_laboratory,
    theoretical_capacity,
)
from screens.common import render_progress, render_simple_table


RADIOLOGY_TOKENS = (
    "radiolog", "medicina nucleare", "nuclear", "diagnostica per immagini",
    "imaging", "tac", "risonanza magnetica",
)
LABORATORY_TOKENS = (
    "laborator", "analisi", "microbiolog", "patologia clinica", "biochim",
)


def _integer_operator(column, profession: str, value: float, key: str) -> int:
    return int(column.number_input(
        profession,
        min_value=0,
        max_value=500,
        value=int(round(value)),
        step=1,
        format="%d",
        key=key,
    ))


def _save_room(db, scenario_id: int, unit_id: int, room_id: int | None, payload: dict) -> bool:
    try:
        db.save_radiology_room(scenario_id, unit_id, room_id, payload)
        st.success("Voce dei tempi attività programmate salvata.")
        return True
    except sqlite3.IntegrityError:
        st.error("Esiste già una voce con questo nome nella UO.")
        return False


def _annual_basis(unit: dict, hours_day: int) -> tuple[bool, int, int]:
    """La spunta H24 della UO è l'unica fonte per ore e giorni di copertura."""
    h24 = bool(unit["h24"])
    return h24, 24 if h24 else int(hours_day), 365 if h24 else 260


def _basis_caption(unit: dict) -> None:
    if unit["h24"]:
        st.caption("Base ereditata dalla Configurazione UO: **H24 · 24 ore/giorno · 365 giorni/anno**.")
    else:
        st.caption("Base ereditata dalla Configurazione UO: **regime ordinario · 260 giorni/anno**.")


def _radiology_form(db, scenario_id: int, unit: dict, room: dict | None, form_key: str) -> None:
    existing = room or {}
    with st.form(form_key, clear_on_submit=room is None):
        name = st.text_input("Nome sala", value=existing.get("name", ""))
        modality_options = list(SIRM_MINUTES)
        current_modality = existing.get("modality", "D11 RX")
        modality = st.selectbox(
            "Tipo di sala (codice SIRM)",
            modality_options,
            index=modality_options.index(current_modality) if current_modality in modality_options else 0,
            help="Il minutaggio proposto proviene dal tempario SIRM del modello Excel.",
        )
        default_minutes = SIRM_MINUTES[modality]
        average_minutes = int(st.number_input(
            "Tempo medio per prestazione (minuti)",
            min_value=1,
            max_value=1440,
            value=int(round(existing.get("average_minutes", default_minutes) or default_minutes)),
            step=1,
            format="%d",
            help=f"Valore SIRM proposto per {modality}: {default_minutes} minuti; è modificabile.",
        ))

        _basis_caption(unit)
        if unit["h24"]:
            hours_day = 24
            first, second = st.columns(2)
            first.metric("Ore apertura / giorno", "24")
            second.metric("Giorni / anno", "365")
        else:
            hours_day = int(st.number_input(
                "Ore apertura / giorno",
                min_value=0,
                max_value=24,
                value=min(24, int(round(existing.get("hours_day", 8) or 8))),
                step=1,
                format="%d",
            ))
            st.metric("Giorni / anno", "260")
        h24, hours_day, days_year = _annual_basis(unit, hours_day)

        st.markdown("**Operatori contemporaneamente presenti**")
        applicable = [
            (profession, field) for profession, field in PROFESSION_FIELDS.items()
            if profession in unit["professions"]
        ]
        operator_values: dict[str, int] = {}
        if applicable:
            columns = st.columns(len(applicable))
            for column, (profession, field) in zip(columns, applicable):
                operator_values[field] = _integer_operator(
                    column, profession, existing.get(field, 0), f"{form_key}_{field}"
                )
        else:
            st.warning("Aggiungi almeno una professione alla UO per calcolare gli FTE della sala.")
        for _, field in PROFESSION_FIELDS.items():
            operator_values.setdefault(field, 0)

        save_column, delete_column = st.columns(2)
        saved = save_column.form_submit_button("Salva sala", type="primary")
        deleted = delete_column.form_submit_button("Elimina sala", disabled=room is None)
        if saved:
            if not name.strip():
                st.error("Inserisci il nome della sala.")
            elif _save_room(db, scenario_id, unit["id"], existing.get("id"), {
                "name": name.strip(), "modality": modality, "h24": h24,
                "hours_day": hours_day, "days_year": days_year,
                "annual_volume": 0, "average_minutes": average_minutes,
                **operator_values,
            }):
                st.rerun()
        if deleted and room:
            db.delete_radiology_room(scenario_id, room["id"])
            st.success("Sala eliminata.")
            st.rerun()


def _laboratory_form(db, scenario_id: int, unit: dict, room: dict | None, form_key: str) -> None:
    existing = room or {}
    with st.form(form_key, clear_on_submit=room is None):
        name = st.text_input("Nome del servizio", value=existing.get("name", ""))
        _basis_caption(unit)
        first, second = st.columns(2)
        if unit["h24"]:
            hours_day = 24
            first.metric("Apertura (ore / giorno)", "24")
            second.metric("Giorni / anno", "365")
        else:
            hours_day = int(first.number_input(
                "Apertura (ore / giorno)", min_value=0, max_value=24,
                value=min(24, int(round(existing.get("hours_day", 8) or 8))), step=1, format="%d",
            ))
            second.metric("Giorni / anno", "260")
        h24, hours_day, days_year = _annual_basis(unit, hours_day)

        average_minutes = int(st.number_input(
            "Minuti per prestazione (facoltativo)", min_value=0, max_value=1440,
            value=int(round(existing.get("average_minutes", 0) or 0)), step=1, format="%d",
            help="Lascia 0 se il servizio garantisce una presenza continuativa e non una capacità per prestazioni.",
        ))

        st.markdown("**Operatori contemporaneamente richiesti**")
        doctors_column, technicians_column = st.columns(2)
        doctors = _integer_operator(
            doctors_column, "Medici", existing.get("doctors", 0), f"{form_key}_doctors"
        )
        technicians = _integer_operator(
            technicians_column, "Tecnici sanitari", existing.get("health_technicians", 0),
            f"{form_key}_health_technicians",
        )
        missing = [p for p in ("Medici", "Tecnici sanitari") if p not in unit["professions"]]
        if missing:
            st.caption(
                "Per riportare gli FTE nei risultati, aggiungi alla UO in Configurazione: "
                + ", ".join(missing) + "."
            )

        save_column, delete_column = st.columns(2)
        saved = save_column.form_submit_button("Salva servizio", type="primary")
        deleted = delete_column.form_submit_button("Elimina servizio", disabled=room is None)
        if saved:
            if not name.strip():
                st.error("Inserisci il nome del servizio.")
            elif _save_room(db, scenario_id, unit["id"], existing.get("id"), {
                "name": name.strip(), "modality": LABORATORY_MODALITY,
                "h24": h24, "hours_day": hours_day, "days_year": days_year,
                "annual_volume": 0, "average_minutes": average_minutes,
                "doctors": doctors, "nurses": 0, "oss": 0,
                "health_technicians": technicians, "radiology_technicians": 0,
            }):
                st.rerun()
        if deleted and room:
            db.delete_radiology_room(scenario_id, room["id"])
            st.success("Servizio eliminato.")
            st.rerun()


def _service_result(room: dict, unit: dict, result_rows: list[dict], service_label: str) -> None:
    normalized_room = dict(room)
    normalized_room["_unit_h24"] = bool(unit["h24"])
    capacity = theoretical_capacity(normalized_room)
    first, second = st.columns(2)
    first.metric("Ore di apertura annue", f"{annual_open_hours(normalized_room):,.0f}".replace(",", "."))
    if capacity is None:
        second.metric("Capacità teorica", "Non calcolata")
    else:
        second.metric("Prestazioni teoriche / anno", f"{capacity:,.0f}".replace(",", "."))

    rows = []
    for profession, field in PROFESSION_FIELDS.items():
        operators = int(round(float(room.get(field, 0) or 0)))
        matching = next(
            (row for row in result_rows
             if row["unit_id"] == room["unit_id"] and row["profession"] == profession),
            None,
        )
        if operators > 0:
            annual_hours = float(matching["annual_hours"]) if matching else 0.0
            fte = annual_open_hours(normalized_room) * operators / annual_hours if annual_hours else 0.0
            rows.append({
                "Servizio": service_label,
                "Professione": profession,
                "Operatori contemporanei": operators,
                "FTE attività programmate": f"{fte:.2f}" if annual_hours else "Configura professione",
            })
    if rows:
        render_simple_table(rows)


def _unit_selector(units: list[dict], key: str, empty_message: str) -> dict | None:
    if not units:
        st.warning(empty_message)
        return None
    labels = {unit["id"]: unit["name"] for unit in units}
    unit_id = st.selectbox(
        "Unità Operativa associata", list(labels), format_func=lambda item: labels[item], key=key
    )
    return next(item for item in units if item["id"] == unit_id)


def _contains_any(value: str, tokens: tuple[str, ...]) -> bool:
    normalized = (value or "").casefold()
    return any(token in normalized for token in tokens)


def _is_radiology_unit(unit: dict) -> bool:
    return _contains_any(unit.get("name", ""), RADIOLOGY_TOKENS)


def _is_laboratory_unit(unit: dict) -> bool:
    return (
        "laborator" in (unit.get("area", "") or "").casefold()
        or _contains_any(unit.get("name", ""), LABORATORY_TOKENS)
    )


def render(db, scenario_id: int) -> None:
    st.title("Tempi attività programmate")
    st.caption(
        "Configura le sale di Radiologia e i servizi di Laboratorio. La base di calcolo deriva "
        "sempre dalla spunta H24 della UO: 365 giorni × 24 ore se attiva, 260 giorni negli altri casi."
    )
    render_progress(db, scenario_id)
    units = db.list_operating_units(scenario_id, active_only=True)
    result_rows = adjusted_scenario_rows(db, scenario_id)

    radiology_units = [unit for unit in units if _is_radiology_unit(unit)]
    laboratory_units = [unit for unit in units if _is_laboratory_unit(unit)]
    medical_tab, laboratory_tab = st.tabs(["Area medica", "Area laboratoriale"])

    with medical_tab:
        st.markdown("### Sale radiologiche")
        st.caption(
            "Per il momento in quest'area sono visualizzate esclusivamente le UO di Radiologia. "
            "Le prestazioni teoriche derivano da ore di apertura e minutaggio SIRM."
        )
        unit = _unit_selector(
            radiology_units,
            "programmed_radiology_unit",
            "Non sono presenti UO di Radiologia attive. Attivane una in Configurazione struttura.",
        )
        if unit:
            rooms = [
                room for room in db.list_radiology_rooms(scenario_id, unit["id"])
                if not is_laboratory(room)
            ]
            with st.expander("Aggiungi sala", expanded=not rooms):
                _radiology_form(db, scenario_id, unit, None, f"new_radiology_room_{unit['id']}")
            for room in rooms:
                with st.expander(f"{room['name']} · {room['modality']}"):
                    _radiology_form(db, scenario_id, unit, room, f"radiology_room_{room['id']}")
                    _service_result(room, unit, result_rows, "Radiologia")

    with laboratory_tab:
        st.markdown("### Servizi di laboratorio")
        st.caption(
            "Sono selezionabili solo le UO dell'area laboratoriale. Il minutaggio è facoltativo; "
            "il fabbisogno dipende da ore di apertura, base annua e operatori contemporanei."
        )
        unit = _unit_selector(
            laboratory_units,
            "programmed_laboratory_unit",
            "Non sono presenti UO di Laboratorio attive. Configurane una nell'area Laboratori.",
        )
        if unit:
            services = [
                room for room in db.list_radiology_rooms(scenario_id, unit["id"])
                if is_laboratory(room)
            ]
            with st.expander("Aggiungi servizio", expanded=not services):
                _laboratory_form(db, scenario_id, unit, None, f"new_laboratory_{unit['id']}")
            for service in services:
                with st.expander(service["name"]):
                    _laboratory_form(db, scenario_id, unit, service, f"laboratory_{service['id']}")
                    _service_result(service, unit, result_rows, "Laboratorio")
