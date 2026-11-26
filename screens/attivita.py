"""Driver di attività e fabbisogno FTE."""

import streamlit as st

from calculations.service_tempari import adjusted_scenario_rows
from screens.common import render_progress


def _integer_input(label: str, value: float, key: str, help: str | None = None, maximum: int = 10_000_000) -> int:
    return int(st.number_input(
        label,
        min_value=0,
        max_value=maximum,
        value=int(round(value)),
        step=1,
        format="%d",
        key=key,
        help=help,
    ))


ACTIVITY_FIELDS = (
    "annual_work_hours", "overtime_hours", "cas_percent", "ias_hours",
    "morning_operators", "afternoon_operators", "night_operators",
    "coverage_days_year", "outpatient_volume", "outpatient_minutes",
    "community_hours", "recovery_hours", "operating_rooms",
    "room_hours_day", "room_days_year", "operators_per_room",
)


def _copy_outpatient_data(db, scenario_id: int, unit: dict, profession: str, payload: dict) -> None:
    """Copia solo i dati ambulatoriali, preservando gli altri driver dell'altra professione."""
    counterpart = "Infermieri" if profession == "Medici" else "Medici"
    if counterpart not in unit["professions"]:
        return
    current = db.get_activity_input(scenario_id, unit["id"], counterpart)
    copied = {field: current[field] for field in ACTIVITY_FIELDS}
    for field in (
        "outpatient_volume", "outpatient_minutes", "community_hours", "recovery_hours"
    ):
        copied[field] = payload[field]
    db.save_activity_input(scenario_id, unit["id"], counterpart, copied)


def _metric_card(label: str, value: float, background: str, border: str) -> None:
    st.markdown(
        f"""
        <div style="background:{background}; border-left:5px solid {border};
                    border-radius:9px; padding:14px 16px; min-height:92px;">
          <div style="font-size:.88rem; color:#405365; margin-bottom:6px;">{label}</div>
          <div style="font-size:1.75rem; font-weight:700; color:#17364a;">{value:.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _coverage_days(unit: dict) -> int:
    """Usa la base standard: 365 giorni per H24, 260 negli altri casi."""
    if not unit["has_shifts"]:
        return 0
    return 365 if unit["h24"] else 260


def _standard_cas_percent(data: dict) -> float:
    """Propone il CAS standard del 15% anche per le schede storiche inizializzate a zero."""
    stored = float(data.get("cas_percent", 0.0) or 0.0)
    return stored * 100 if stored > 0 else 15.0


def _render_form(db, scenario_id: int, unit: dict, profession: str) -> None:
    data = db.get_activity_input(scenario_id, unit["id"], profession)
    prefix = f"activity_{unit['id']}_{profession}"
    with st.form(f"activity_form_{unit['id']}_{profession}"):
        st.markdown("#### FTE dettato dal CARICO DI LAVORO")
        c1, c2 = st.columns(2)
        with c1:
            annual_work_hours = _integer_input(
                "Ore lavorate / anno", data["annual_work_hours"], f"{prefix}_work"
            )
        with c2:
            overtime_hours = _integer_input(
                "Ore di straordinario", data["overtime_hours"], f"{prefix}_overtime"
            )
        c3, c4 = st.columns(2)
        cas_percentage = c3.number_input(
            "CAS (%)", min_value=0.0, max_value=99.0,
            value=_standard_cas_percent(data), step=1.0, key=f"{prefix}_cas",
            help="Si tratta di un correttivo che identifica la $%$ di ore di lavoro dedicate ad attività non prettamente cliniche, come la refertazione, partecipazione alle riunioni di reparto, attività preparatorie. Sono attività comuni a tutto il gruppo professionale. "
        )
        with c4:
            ias_hours = _integer_input("IAS (ore annue)", data["ias_hours"], f"{prefix}_ias", help="Quantità di ore di lavoro dedicate ad attività aggiuntive o incarichi specifici assegnati solo ad alcuni membri del gruppo professionale. Esempi sono supervisione di tirocinanti, coordinamento del turno o partecipazione a riunioni esterne per conto del reparto, audit.")

        coverage_days = _coverage_days(unit)
        if unit["has_shifts"]:
            st.markdown("#### Copertura turni / degenza")
            coverage_basis = (
                "UO H24: 365 giorni e 24 ore"
                if unit["h24"]
                else "regime ordinario: 260 giorni"
            )
            st.caption(
                f"Copertura calcolata automaticamente: {coverage_days} giorni/anno "
                f"({coverage_basis})."
            )
            morning, afternoon, night = st.columns(3)
            morning_ops = int(morning.number_input(
                "Operatori mattina", 0, 500, int(data["morning_operators"]), 1,
                format="%d", key=f"{prefix}_morning",
            ))
            afternoon_ops = int(afternoon.number_input(
                "Operatori pomeriggio", 0, 500, int(data["afternoon_operators"]), 1,
                format="%d", key=f"{prefix}_afternoon",
            ))
            night_ops = int(night.number_input(
                "Operatori notte", 0, 500, int(data["night_operators"]), 1,
                format="%d", key=f"{prefix}_night",
            ))
        else:
            morning_ops = afternoon_ops = night_ops = 0

        if unit["has_outpatient"]:
            st.markdown("#### Attività ambulatoriale")
            volume_col, minutes_col = st.columns(2)
            with volume_col:
                outpatient_volume = _integer_input(
                    "Prestazioni / anno", data["outpatient_volume"], f"{prefix}_volume"
                )
            with minutes_col:
                outpatient_minutes = _integer_input(
                    "Tempo medio per prestazione (minuti)",
                    data["outpatient_minutes"],
                    f"{prefix}_minutes",
                    maximum=1440,
                )
            community_col, recovery_col = st.columns(2)
            with community_col:
                community_hours = _integer_input(
                    "Case di Comunità (ore / anno)",
                    data["community_hours"],
                    f"{prefix}_community",
                    help="Inserire il numero di ore di servizio erogato presso le case di comunità da questa professione di questa UO."
                )
            with recovery_col:
                recovery_hours = _integer_input(
                    "Abbattimento liste d'attesa (ore / anno)",
                    data["recovery_hours"],
                    f"{prefix}_recovery",
                )
            counterpart = "Infermieri" if profession == "Medici" else "Medici"
            copy_outpatient = False
            if profession in ("Medici", "Infermieri") and counterpart in unit["professions"]:
                copy_outpatient = st.checkbox(
                    f"Applica gli stessi dati ambulatoriali anche a {counterpart}",
                    key=f"{prefix}_copy_outpatient",
                    help=(
                        "Copia prestazioni, minutaggio, Case di Comunità e abbattimento liste; "
                        "gli altri dati della professione destinataria restano invariati."
                    ),
                )
        else:
            outpatient_volume = outpatient_minutes = community_hours = recovery_hours = 0
            copy_outpatient = False

        if unit["has_operating_rooms"]:
            st.markdown("#### Sale operatorie")
            room_count, hours_day, days_year, operators = st.columns(4)
            operating_rooms = int(room_count.number_input(
                "Numero sale", 0, 100, int(data["operating_rooms"]), 1,
                format="%d", key=f"{prefix}_rooms",
            ))
            room_hours_day = int(hours_day.number_input(
                "Ore apertura / giorno", min_value=0, max_value=24,
                value=int(round(data["room_hours_day"])), step=1,
                format="%d", key=f"{prefix}_room_hours",
            ))
            room_days_year = int(days_year.number_input(
                "Giorni apertura / anno", 0, 366, int(data["room_days_year"]), 1,
                format="%d", key=f"{prefix}_room_days",
            ))
            operators_per_room = int(operators.number_input(
                "Operatori per sala", min_value=0, max_value=500,
                value=int(round(data["operators_per_room"])), step=1, format="%d",
                key=f"{prefix}_room_ops",
            ))
        else:
            operating_rooms = room_hours_day = room_days_year = 0
            operators_per_room = 0.0

        if st.form_submit_button("Salva attività", type="primary", use_container_width=True):
            payload = {
                "annual_work_hours": annual_work_hours,
                "overtime_hours": overtime_hours,
                "cas_percent": cas_percentage / 100.0,
                "ias_hours": ias_hours,
                "morning_operators": morning_ops,
                "afternoon_operators": afternoon_ops,
                "night_operators": night_ops,
                "coverage_days_year": coverage_days,
                "outpatient_volume": outpatient_volume,
                "outpatient_minutes": outpatient_minutes,
                "community_hours": community_hours,
                "recovery_hours": recovery_hours,
                "operating_rooms": operating_rooms,
                "room_hours_day": room_hours_day,
                "room_days_year": room_days_year,
                "operators_per_room": operators_per_room,
            }
            db.save_activity_input(scenario_id, unit["id"], profession, payload)
            if copy_outpatient:
                _copy_outpatient_data(db, scenario_id, unit, profession, payload)
            st.success("Attività salvate.")
            st.rerun()

    result = next(
        row for row in adjusted_scenario_rows(db, scenario_id)
        if row["unit_id"] == unit["id"] and row["profession"] == profession
    )
    st.markdown("#### FTE calcolati")
    workload_column, operational_column = st.columns([1, 3])
    with workload_column:
        _metric_card("0 · Workload", result["workload_fte"], "#D6EAF5", "#5B8FA8")
    with operational_column:
        components = st.columns(3)
        if result["tempari_override"]:
            labels_values = (
                ("1 · Turni", result["shift_fte"]),
                ("2 · Attività programmate", result["programmed_fte"]),
                ("3 · Altre attività", 0.0),
            )
        else:
            labels_values = (
                ("1 · Turni", result["shift_fte"]),
                ("2 · Ambulatorio", result["outpatient_fte"]),
                ("3 · Sale", result["room_fte"]),
            )
        for column, (label, value) in zip(components, labels_values):
            with column:
                _metric_card(label, value, "#E8EEF2", "#AAB7C0")

    st.caption(
        "Il fabbisogno richiesto usa due metodi alternativi: **metrica 0 (workload)** "
        "oppure **somma delle metriche 1–2–3**. Non vengono sommati tra loro."
    )
    required_column, explanation_column = st.columns([0.36, 0.64], vertical_alignment="center")
    with required_column:
        _metric_card("4 · FTE richiesti", result["required_fte"], "#7BA7BF", "#416E85")
    explanation_column.info(
        f"FTE richiesti = max({result['workload_fte']:.2f}; "
        f"{result['operational_fte']:.2f}) = {result['required_fte']:.2f}."
    )

def render(db, scenario_id: int) -> None:
    st.title("Attività e fabbisogno")
    st.caption(
        "Compila i parametri per UO e professione. Il CAS standard è il 15%. "
        "La copertura è calcolata su 365 giorni e 24 ore per le UO H24, "
        "oppure su 260 giorni per le altre UO."
    )
    render_progress(db, scenario_id)
    units = db.list_operating_units(scenario_id, active_only=True)
    if not units:
        st.warning("Configura almeno una UO attiva.")
        return
    unit_tabs = st.tabs([unit["name"] for unit in units])
    for unit_tab, unit in zip(unit_tabs, units):
        with unit_tab:
            profession_tabs = st.tabs(unit["professions"])
            for profession_tab, profession in zip(profession_tabs, unit["professions"]):
                with profession_tab:
                    _render_form(db, scenario_id, unit, profession)
    completed, total = db.activity_completion(scenario_id)
    st.info(f"{completed} schede attività completate su {total}")
