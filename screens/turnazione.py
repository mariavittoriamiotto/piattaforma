"""Schermata di fattibilità della turnazione temporaneamente disattivata."""

import streamlit as st

from screens.common import render_progress


def render(db, scenario_id: int) -> None:
    st.title("Fattibilità della turnazione")
    render_progress(db, scenario_id)
    st.info(
        "La verifica di fattibilità della turnazione è temporaneamente disattivata. "
        "I dati inseriti nelle altre sezioni restano disponibili e non vengono modificati."
    )
