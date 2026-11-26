"""Risultati FTE e indicatori di organico senza deduzione Legge 104."""

from html import escape

import streamlit as st

from calculations.service_tempari import adjusted_scenario_rows, adjusted_scenario_totals
from screens.common import render_progress, render_simple_table
from storage.thresholds import get_thresholds


PALETTE = {
    "blue": ("#E5F1F7", "#5B8FA8", "#17364A"),
    "teal": ("#E2F2F1", "#4F8F8B", "#244D4A"),
    "green": ("#E4F3E8", "#4D8A5F", "#285437"),
    "yellow": ("#FFF4CC", "#C79A21", "#6F5715"),
    "red": ("#F9DEDE", "#C76868", "#713333"),
    "gray": ("#EEF2F5", "#96A5B1", "#354957"),
}


def _scenario_heading(scenario: dict) -> None:
    name_col, info_col = st.columns([0.86, 0.14], vertical_alignment="center")
    name_col.markdown(f"#### {scenario['name']}")
    with info_col.popover("ⓘ"):
        st.write(scenario["description"] or "Nessuna descrizione inserita.")


def _rate(value: float | None) -> str:
    return "N/D" if value is None else f"{value:.1%}"


def _retirement_risk(value: float | None, thresholds: dict) -> tuple[str, str]:
    if value is None:
        return "N/D", "gray"
    if value > thresholds["retirement_critical"]:
        return "Alto", "red"
    if value >= thresholds["retirement_attention"]:
        return "Medio", "yellow"
    return "Basso", "green"


def _overtime_risk(value: float | None, thresholds: dict) -> tuple[str, str]:
    if value is None:
        return "N/D", "gray"
    if value > thresholds["overtime_threshold"]:
        return "Attenzione", "red"
    return "Regolare", "green"


def _staffing_result(current: float, required: float, thresholds: dict) -> tuple[str, str]:
    if required <= 0:
        return "Dati attività mancanti", "yellow"
    coverage = current / required
    if coverage < thresholds["staffing_ratio_min"]:
        return "Sottoorganico", "red"
    if coverage > thresholds["staffing_ratio_max"]:
        return "Sovraorganico", "yellow"
    return "In linea", "green"


def _indicator_card(label: str, value: str, tone: str, note: str = "") -> None:
    background, border, text = PALETTE[tone]
    note_html = (
        f'<div style="font-size:.78rem;color:#556875;margin-top:4px;">{escape(note)}</div>'
        if note else ""
    )
    st.markdown(
        f"""
        <div style="background:{background};border:1px solid {border};border-left:6px solid {border};
                    border-radius:10px;padding:13px 15px;min-height:104px;margin-bottom:10px;">
          <div style="font-size:.84rem;color:#4A5E6B;margin-bottom:6px;">{escape(label)}</div>
          <div style="font-size:1.42rem;font-weight:750;color:{text};">{escape(value)}</div>
          {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _comparison_rows(db, left_id: int, right_id: int) -> list[dict]:
    left = {(r["unit"], r["profession"]): r for r in adjusted_scenario_rows(db, left_id)}
    right = {(r["unit"], r["profession"]): r for r in adjusted_scenario_rows(db, right_id)}
    rows = []
    for key in sorted(set(left) | set(right)):
        first = left.get(key, {})
        second = right.get(key, {})
        rows.append({
            "UO": key[0], "Professione": key[1],
            "FTE richiesti A": f"{first.get('required_fte', 0):.2f}",
            "FTE richiesti B": f"{second.get('required_fte', 0):.2f}",
            "Differenza B−A": f"{second.get('required_fte', 0) - first.get('required_fte', 0):+.2f}",
        })
    return rows


def _render_detail(row: dict, thresholds: dict) -> None:
    current = float(row.get("current_fte_nominal", 0) or 0)
    required = float(row.get("required_fte", 0) or 0)
    gap = current - required
    result, result_tone = _staffing_result(current, required, thresholds)
    retirement_risk, retirement_tone = _retirement_risk(row.get("retirement_rate"), thresholds)
    overtime_risk, overtime_tone = _overtime_risk(row.get("overtime_rate"), thresholds)
    gap_tone = "green" if result_tone == "green" else result_tone

    st.markdown(f"### {row['unit']} · {row['profession']}")
    first = st.columns(4)
    with first[0]:
        _indicator_card("FTE attuale", f"{current:.2f}", "blue", "FT + 0,5 × PT")
    with first[1]:
        _indicator_card("FTE richiesto", f"{required:.2f}", "teal")
    with first[2]:
        _indicator_card("Gap", f"{gap:+.2f}", gap_tone)
    with first[3]:
        _indicator_card("Risultato", result, result_tone)

    second = st.columns(5)
    with second[0]:
        _indicator_card("Skill mix", _rate(row.get("skill_mix")), "blue")
    with second[1]:
        _indicator_card("Tasso pensionamento", _rate(row.get("retirement_rate")), retirement_tone)
    with second[2]:
        _indicator_card("Rischio pensionamento", retirement_risk, retirement_tone)
    with second[3]:
        _indicator_card("Tasso straordinario", _rate(row.get("overtime_rate")), overtime_tone)
    with second[4]:
        _indicator_card("Rischio straordinario", overtime_risk, overtime_tone)


def render(db, scenario_id: int) -> None:
    st.title("Risultati")
    st.caption(
        "FTE attuale, fabbisogno, gap e indicatori di rischio. I permessi Legge 104 restano "
        "registrati nell'organico ma non vengono dedotti dai risultati FTE."
    )
    render_progress(db, scenario_id)
    rows = adjusted_scenario_rows(db, scenario_id)
    totals = adjusted_scenario_totals(db, scenario_id)
    thresholds = get_thresholds(scenario_id)

    total_current = float(totals.get("current_fte_nominal", 0) or 0)
    total_required = float(totals.get("required_fte", 0) or 0)
    total_gap = total_current - total_required
    total_result, total_tone = _staffing_result(total_current, total_required, thresholds)
    summary = st.columns(4)
    with summary[0]:
        _indicator_card("FTE attuale", f"{total_current:.2f}", "blue")
    with summary[1]:
        _indicator_card("FTE richiesto", f"{total_required:.2f}", "teal")
    with summary[2]:
        _indicator_card("Gap", f"{total_gap:+.2f}", total_tone)
    with summary[3]:
        _indicator_card("Risultato complessivo", total_result, total_tone)

    st.subheader("Dettaglio per UO e professione")
    for row in sorted(
        rows,
        key=lambda item: float(item.get("current_fte_nominal", 0) or 0)
        - float(item.get("required_fte", 0) or 0),
    ):
        _render_detail(row, thresholds)

    with st.expander("Come sono calcolati gli indicatori"):
        st.markdown(
            "- **FTE attuale** = dipendenti full-time + 0,5 × dipendenti part-time. "
            "Non viene applicata alcuna deduzione per i permessi Legge 104.\n"
            "- **Gap** = FTE attuale − FTE richiesto.\n"
            f"- **Risultato**: sottoorganico sotto il {thresholds['staffing_ratio_min']:.0%}, "
            f"in linea tra {thresholds['staffing_ratio_min']:.0%} e "
            f"{thresholds['staffing_ratio_max']:.0%}, sovraorganico oltre il "
            f"{thresholds['staffing_ratio_max']:.0%}.\n"
            "- **Skill mix** = specializzandi / dipendenti full-time; è previsto solo per Medici e Infermieri.\n"
            "- **Tasso pensionamento** = pensionamenti FT e PT previsti entro 3 anni / dipendenti FT e PT. "
            f"Rischio medio da {thresholds['retirement_attention']:.0%} e alto oltre "
            f"{thresholds['retirement_critical']:.0%}.\n"
            "- **Tasso straordinario** = ore di straordinario / ore contrattuali annue della professione. "
            f"Il rischio scatta oltre il {thresholds['overtime_threshold']:.0%}."
        )

    scenarios = db.list_scenarios()
    alternatives = [row for row in scenarios if int(row["id"]) != scenario_id]
    st.divider()
    st.subheader("Confronto FTE tra scenari")
    if not alternatives:
        st.info("Duplica lo scenario o creane uno nuovo per attivare il confronto.")
        return
    labels = {int(row["id"]): row["name"] for row in alternatives}
    compare_id = st.selectbox(
        "Scenario da confrontare", list(labels), format_func=lambda item: labels[item],
        key="results_compare_scenario",
    )
    left_scenario = dict(db.get_scenario(scenario_id))
    right_scenario = dict(db.get_scenario(compare_id))
    left_col, right_col = st.columns(2)
    with left_col:
        _scenario_heading(left_scenario)
        total = adjusted_scenario_totals(db, scenario_id)
        st.metric("FTE richiesti", f"{total['required_fte']:.2f}")
        st.metric("Gap", f"{total['gap']:+.2f}")
    with right_col:
        _scenario_heading(right_scenario)
        total = adjusted_scenario_totals(db, compare_id)
        st.metric("FTE richiesti", f"{total['required_fte']:.2f}")
        st.metric("Gap", f"{total['gap']:+.2f}")
    render_simple_table(_comparison_rows(db, scenario_id, compare_id))
