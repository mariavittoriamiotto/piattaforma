"""Configurazione della struttura e gestione degli scenari."""

import sqlite3

import streamlit as st

from core.constants import AREAS, PROFESSIONS
from screens.common import render_progress
from storage.thresholds import get_thresholds, save_thresholds


def _activate_scenario(scenario_id: int) -> None:
    """Imposta lo scenario di sessione prima del rerun."""
    st.session_state.scenario_id = scenario_id


def _render_scenario_management(db, scenario_id: int) -> None:
    scenarios = db.list_scenarios()
    scenario_ids = [int(row["id"]) for row in scenarios]
    labels = {int(row["id"]): row["name"] for row in scenarios}

    st.header("Scenari")
    st.caption(
        "Uno scenario raccoglie struttura, parametri, organico e attività. Selezionane uno per "
        "renderlo attivo, creane uno vuoto oppure duplica quello corrente per formulare un'alternativa."
    )
    selector, info = st.columns([0.78, 0.22], vertical_alignment="bottom")
    selected_id = selector.selectbox(
        "Scenario attivo",
        scenario_ids,
        index=scenario_ids.index(scenario_id),
        format_func=lambda item: labels[item],
        key=f"scenario_selector_{scenario_id}",
    )
    """with info.popover("ⓘ Descrizione", use_container_width=True):
        selected = db.get_scenario(int(selected_id))
        st.write(selected["description"] or "Nessuna descrizione inserita.")"""
    if int(selected_id) != scenario_id:
        _activate_scenario(int(selected_id))
        st.rerun()

    create_tab, duplicate_tab = st.tabs(["+ Nuovo scenario", "Duplica scenario attivo"])
    with create_tab, st.form("new_scenario_form", clear_on_submit=True):
        name = st.text_input("Nome del nuovo scenario")
        description = st.text_area(
            "Descrizione",
            help="Spiega brevemente l'ipotesi organizzativa o la finalità dello scenario.",
        )
        year = st.number_input(
            "Anno di riferimento", min_value=2020, max_value=2100, value=2026, step=1
        )
        if st.form_submit_button("Crea e attiva scenario", type="primary"):
            if not name.strip():
                st.error("Inserisci il nome dello scenario.")
            else:
                try:
                    new_id = db.create_scenario(name, int(year), description=description)
                    _activate_scenario(new_id)
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Esiste già uno scenario con questo nome.")

    active = db.get_scenario(scenario_id)
    with duplicate_tab, st.form("duplicate_scenario_form"):
        duplicate_name = st.text_input("Nome della copia", value=f"{active['name']} - copia")
        duplicate_description = st.text_area(
            "Descrizione della copia",
            value=active["description"],
            help="Puoi distinguere subito l'ipotesi duplicata modificandone la descrizione.",
        )
        if st.form_submit_button("Duplica e attiva scenario", type="primary"):
            if not duplicate_name.strip():
                st.error("Inserisci il nome della copia.")
            else:
                try:
                    new_id = db.duplicate_scenario(
                        scenario_id,
                        duplicate_name,
                        new_description=duplicate_description,
                    )
                    save_thresholds(new_id, get_thresholds(scenario_id))
                    _activate_scenario(new_id)
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Esiste già uno scenario con questo nome.")


def render(db, scenario_id: int) -> None:
    scenario = db.get_scenario(scenario_id)
    st.title("Configurazione della struttura")
    st.markdown(
        "La piattaforma consente di configurare la dotazione di dipendenti all'interno di una struttura ospedaliera, "
        "calcolare il fabbisogno FTE e verificare la sostenibilità della turnazione. "
        "Utilizzando gli scenari è possibile confrontare diverse ipotesi organizzative."
    )
    render_progress(db, scenario_id)
    _render_scenario_management(db, scenario_id)

    st.header("Informazioni rigurado il corrente scenario")
    with st.form("scenario_general_form"):
        name = st.text_input("Nome scenario", value=scenario["name"])
        col1, col2 = st.columns(2)
        facility_name = col1.text_input("Nome struttura", value=scenario["facility_name"])
        facility_code = col2.text_input(
            "Codice struttura (facoltativo)", value=scenario["facility_code"]
        )
        reference_year = st.number_input(
            "Anno di riferimento", min_value=2020, max_value=2100,
            value=int(scenario["reference_year"]), step=1,
        )
        description = st.text_area(
            "Descrizione dello scenario", value=scenario["description"],
            help="La descrizione identifica l'ipotesi nei confronti tra scenari.",
        )
        if st.form_submit_button("Salva informazioni generali", type="primary"):
            try:
                db.update_scenario(
                    scenario_id, name, facility_name, facility_code,
                    int(reference_year), description,
                )
                st.success("Informazioni generali salvate.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Esiste già uno scenario con questo nome.")

    st.header("Unità Operative")
    st.caption("La spunta nella colonna ""Attivo"" include o esclude immediatamente la UO dal modello.")

    with st.expander("Aggiungi Unità Operativa"):
        with st.form("add_unit_form", clear_on_submit=True):
            unit_name = st.text_input("Nome UO")
            area = st.selectbox(
                "Area", AREAS
            )
            c1, c2, c3, c4, c5 = st.columns(5)
            h24 = c1.checkbox("H24")
            shifts = c2.checkbox("Turni")
            outpatient = c3.checkbox("Ambulatorio")
            rooms = c4.checkbox("Sale")
            radioprotection = c5.checkbox(
                "Radioprotezione",
                help="Applica 15 giorni annui di riposo biologico alla disponibilità della UO.",
            )
            professions = st.multiselect("Professioni presenti", PROFESSIONS)
            if st.form_submit_button("Aggiungi UO", type="primary"):
                if not unit_name.strip():
                    st.error("Inserisci il nome della UO.")
                elif not professions:
                    st.error("Seleziona almeno una professione.")
                else:
                    try:
                        unit_id = db.upsert_operating_unit(
                            scenario_id, None, unit_name, area, h24, shifts,
                            outpatient, rooms, radioprotection, True,
                        )
                        db.set_unit_professions(unit_id, professions)
                        st.success("Unità Operativa aggiunta.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Questa UO esiste già nello scenario.")

    units = db.list_operating_units(scenario_id)
    if not units:
        st.warning("Nessuna Unità Operativa configurata.")
    else:
        header_active, header_name = st.columns([0.1, 0.9])
        header_active.markdown("**Attivo**")
        header_name.markdown("**Unità Operativa**")

    for unit in units:
        flag_column, unit_column = st.columns([0.1, 0.9], vertical_alignment="top")
        with flag_column:
            selected = st.checkbox(
                f"Attiva {unit['name']}", value=bool(unit["active"]),
                key=f"unit_enabled_{unit['id']}", label_visibility="collapsed",
            )
            if selected != bool(unit["active"]):
                db.set_operating_unit_active(scenario_id, unit["id"], selected)
                st.rerun()
        with unit_column, st.expander(unit["name"]):
            with st.form(f"unit_form_{unit['id']}"):
                edited_name = st.text_input("Nome UO", value=unit["name"], key=f"name_{unit['id']}")
                edited_area = st.selectbox(
                    "Area", AREAS,
                    index=AREAS.index(unit["area"]) if unit["area"] in AREAS else len(AREAS) - 1,
                    key=f"area_{unit['id']}"
                    # help="Il campo è mantenuto per ora e potrà essere rimosso in seguito.",
                )
                c1, c2, c3, c4, c5 = st.columns(5)
                edited_h24 = c1.checkbox("H24", value=bool(unit["h24"]), key=f"h24_{unit['id']}")
                edited_shifts = c2.checkbox(
                    "Turni", value=bool(unit["has_shifts"]), key=f"shifts_{unit['id']}"
                )
                edited_outpatient = c3.checkbox(
                    "Ambulatorio", value=bool(unit["has_outpatient"]), key=f"out_{unit['id']}"
                )
                edited_rooms = c4.checkbox(
                    "Sale", value=bool(unit["has_operating_rooms"]), key=f"rooms_{unit['id']}"
                )
                edited_radioprotection = c5.checkbox(
                    "Radioprotezione",
                    value=bool(unit["radioprotection"]),
                    key=f"radioprotection_{unit['id']}",
                    help="Seleziona questa voce solo per le UO cui spettano 15 giorni di riposo biologico.",
                )
                edited_professions = st.multiselect(
                    "Professioni presenti", PROFESSIONS, default=unit["professions"],
                    key=f"professions_{unit['id']}",
                )
                save, remove = st.columns(2)
                saved = save.form_submit_button("Salva caratteristiche", type="primary")
                deleted = remove.form_submit_button("Elimina UO")
                if saved:
                    if not edited_name.strip() or not edited_professions:
                        st.error("Nome e almeno una professione sono obbligatori.")
                    else:
                        try:
                            db.upsert_operating_unit(
                                scenario_id, unit["id"], edited_name, edited_area,
                                edited_h24, edited_shifts, edited_outpatient,
                                edited_rooms, edited_radioprotection, bool(unit["active"]),
                            )
                            db.set_unit_professions(unit["id"], edited_professions)
                            st.success("UO aggiornata.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Esiste già una UO con questo nome.")
                if deleted:
                    db.delete_operating_unit(scenario_id, unit["id"])
                    st.success("UO eliminata insieme ai dati collegati dello scenario.")
                    st.rerun()

    active_units = [unit for unit in units if unit["active"]]
    st.subheader("Riepilogo configurazione")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("UO attive", len(active_units))
    c2.metric("UO H24", sum(bool(unit["h24"]) for unit in active_units))
    c3.metric("UO con turni", sum(bool(unit["has_shifts"]) for unit in active_units))
    c4.metric(
        "UO con radioprotezione",
        sum(bool(unit["radioprotection"]) for unit in active_units),
    )
