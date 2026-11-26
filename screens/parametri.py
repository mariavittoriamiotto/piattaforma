"""Parametri contrattuali per professione con calcolo immediato del turno."""

import streamlit as st

from calculations.work_availability import annual_available_hours, standard_shift_hours
from core.constants import BIOLOGICAL_REST_DAYS, PROFESSIONS
from models.domain import WorkParameters
from screens.common import render_progress
from storage.thresholds import get_thresholds, reset_thresholds, save_thresholds


def _format_hours(value: float) -> str:
    return f"{value:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _clear_parameter_widgets(profession: str) -> None:
    for prefix in ("weekly", "days", "hol", "leave", "sick", "train"):
        st.session_state.pop(f"{prefix}_{profession}", None)


def render(db, scenario_id: int) -> None:
    st.title("Parametri della struttura")
    st.caption(
        "Ore e giorni di lavoro a settimana sono specifici per ciascuna professione. La durata del turno coincide "
        "con la giornata contrattuale. Festività, ferie e permessi, malattia, formazione e riposo biologico "
        "sono espressi in giorni annui. Tutti i parametri possono essere modificati e adeguati alla propria struttura e alle osservazioni interne."
    )
    render_progress(db, scenario_id)
    parameters = {row["profession"]: row for row in db.get_work_parameters(scenario_id)}
    tabs = st.tabs(PROFESSIONS)

    for tab, profession in zip(tabs, PROFESSIONS):
        with tab:
            row = parameters[profession]
            st.subheader(profession)
            c1, c2 = st.columns(2)
            weekly_hours = c1.number_input(
                "Ore di lavoro a settimana",
                min_value=1,
                max_value=84,
                value=int(round(row["weekly_hours"])),
                step=1,
                format="%d",
                key=f"weekly_{profession}",
            )
            workdays_week = c2.number_input(
                "Giorni di lavoro a settimana",
                min_value=1,
                max_value=7,
                value=int(row["workdays_week"]),
                step=1,
                format="%d",
                key=f"days_{profession}",
                # help="Utilizza i pulsanti +/− oppure inserisci un intero da 1 a 7.",
            )
            contractual_day = standard_shift_hours(float(weekly_hours), int(workdays_week))
            st.metric(
                "Durata turno calcolata",
                f"{contractual_day:.2f} ore".replace(".", ","),
                help="Ore settimanali divise per giorni lavorativi settimanali.",
            )

            st.markdown("**Assenze annue (giorni)**")
            a, b, c, d = st.columns(4)
            holidays = a.number_input(
                "Festività (giorni)", min_value=0.0, max_value=40.0,
                value=float(row["holidays"]), step=0.5, key=f"hol_{profession}",
                help="Il numero di festività proviene dal CCNL. Tutti i valori di questa sezione sono espressi in giorni annui."
            )
            leave_days = b.number_input(
                "Ferie e permessi (giorni)", min_value=0.0, max_value=80.0,
                value=float(row["leave_days"]), step=0.5, key=f"leave_{profession}",
                help="Valore espresso in giorni annui; comprende l'equivalente delle 18 ore di permesso annue.",
            )
            sickness_days = c.number_input(
                "Malattia (giorni)", min_value=0.0, max_value=120.0,
                value=float(row["sickness_days"]), step=0.5, key=f"sick_{profession}",
                help="Stima espressa in giorni annui.",
            )
            training_days = d.number_input(
                "Formazione (giorni)", min_value=0.0, max_value=80.0,
                value=float(row["training_days"]), step=0.5, key=f"train_{profession}",
                help="Stima espressa in giorni annui.",
            )

            model = WorkParameters(
                profession=profession,
                weekly_hours=float(weekly_hours),
                workdays_week=int(workdays_week),
                shift_hours=float(contractual_day),
                shift_is_auto=True,
                holidays=float(holidays),
                leave_days=float(leave_days),
                sickness_days=float(sickness_days),
                training_days=float(training_days),
            )
            base_hours = annual_available_hours(model)
            protected_hours = annual_available_hours(model, BIOLOGICAL_REST_DAYS)
            st.markdown("#### Disponibilità annua per 1 FTE")
            m1, m2 = st.columns(2)
            m1.metric("Regime ordinario", f"{_format_hours(base_hours)} ore/anno")
            m2.metric(
                "Con radioprotezione attiva (+15 giorni annui)",
                f"{_format_hours(protected_hours)} ore/anno",
                help="Il valore è usato solo nelle UO in cui la radioprotezione è stata selezionata manualmente.",
            )

            save, reset = st.columns(2)
            if save.button("Salva parametri", type="primary", key=f"save_parameters_{profession}"):
                db.update_work_parameters(scenario_id, profession, {
                    "weekly_hours": float(weekly_hours),
                    "workdays_week": int(workdays_week),
                    "shift_hours": float(contractual_day),
                    "shift_is_auto": True,
                    "holidays": float(holidays),
                    "leave_days": float(leave_days),
                    "sickness_days": float(sickness_days),
                    "training_days": float(training_days),
                })
                st.success("Parametri salvati.")
                st.rerun()
            if reset.button("Ripristina standard", key=f"reset_parameters_{profession}"):
                db.reset_work_parameters(scenario_id, profession)
                _clear_parameter_widgets(profession)
                st.success("Valori standard ripristinati.")
                st.rerun()

    st.divider()
    st.header("Soglie degli indicatori")
    st.caption(
        "Le soglie sono specifiche dello scenario e alimentano gli alert della dashboard organico."
    )
    thresholds = get_thresholds(scenario_id)
    with st.form(f"thresholds_form_{scenario_id}"):
        first, second = st.columns(2)
        cas = first.number_input(
            "Soglia CAS (%)", min_value=0.0, max_value=100.0,
            value=float(thresholds["cas_threshold"] * 100), step=1.0,
            help="Valore standard: 15%. Oltre la soglia viene segnalata attenzione.",
        )
        overtime = second.number_input(
            "Soglia tasso straordinario (%)", min_value=0.0, max_value=100.0,
            value=float(thresholds["overtime_threshold"] * 100), step=1.0,
            help="Valore standard: 15%.",
        )
        third, fourth = st.columns(2)
        retirement_attention = third.number_input(
            "Pensionamento · attenzione da (%)", min_value=0.0, max_value=100.0,
            value=float(thresholds["retirement_attention"] * 100), step=1.0,
        )
        retirement_critical = fourth.number_input(
            "Pensionamento · criticità oltre (%)", min_value=0.0, max_value=100.0,
            value=float(thresholds["retirement_critical"] * 100), step=1.0,
        )
        fifth, sixth = st.columns(2)
        staffing_min = fifth.number_input(
            "Ratio organico · limite inferiore (%)", min_value=0.0, max_value=300.0,
            value=float(thresholds["staffing_ratio_min"] * 100), step=1.0,
        )
        staffing_max = sixth.number_input(
            "Ratio organico · limite superiore (%)", min_value=0.0, max_value=300.0,
            value=float(thresholds["staffing_ratio_max"] * 100), step=1.0,
        )
        save, reset = st.columns(2)
        save_clicked = save.form_submit_button("Salva soglie", type="primary", use_container_width=True)
        reset_clicked = reset.form_submit_button("Ripristina soglie standard", use_container_width=True)
        if save_clicked:
            try:
                save_thresholds(scenario_id, {
                    "cas_threshold": cas / 100,
                    "overtime_threshold": overtime / 100,
                    "retirement_attention": retirement_attention / 100,
                    "retirement_critical": retirement_critical / 100,
                    "staffing_ratio_min": staffing_min / 100,
                    "staffing_ratio_max": staffing_max / 100,
                })
                st.success("Soglie salvate.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        if reset_clicked:
            reset_thresholds(scenario_id)
            st.success("Soglie standard ripristinate.")
            st.rerun()

    st.caption(
        "Standard: CAS 15%; straordinario 15%; pensionamento 15–30%; ratio organico 85–110%."
    )
