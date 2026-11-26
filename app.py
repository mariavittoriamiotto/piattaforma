"""Entry point Streamlit: navigazione, scenario attivo e composizione delle schermate."""

from pathlib import Path

import streamlit as st

from core.progress import progress_counts
from screens import attivita, configurazione, organico, parametri, radiologia, risultati, turnazione
from storage.database import Database

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "fte_app.db"

st.set_page_config(
    page_title="FTE Ospedale",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --fte-navy: #15324b;
        --fte-blue: #236b9e;
        --fte-sky: #eaf5fb;
        --fte-border: #cad8e3;
        --fte-surface: #f5f7fa;
        --fte-text: #263746;
    }
    .stApp {background: #f5f7fa; color: var(--fte-text);}
    .block-container {padding-top: 1.8rem; padding-bottom: 3rem;}
    h1, h2, h3 {color: var(--fte-navy);}
    [data-testid="stMetric"] {
        background: var(--fte-sky);
        border: 1px solid var(--fte-border);
        padding: 0.8rem;
        border-radius: 0.65rem;
    }
    [data-testid="stSidebar"] {
        background: #e8eef3;
        border-right: 1px solid var(--fte-border);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {color: var(--fte-navy);}
    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: var(--fte-blue);
        border-color: var(--fte-blue);
    }
    .stButton > button[kind="secondary"],
    .stFormSubmitButton > button[kind="secondary"] {
        background: #ffffff;
        color: var(--fte-navy);
        border-color: var(--fte-border);
    }
    div[data-baseweb="tab-list"] {gap: 0.35rem;}
    button[data-baseweb="tab"] {background: #e8eef3; border-radius: 0.45rem 0.45rem 0 0;}
    button[data-baseweb="tab"][aria-selected="true"] {background: #d6edf9; color: var(--fte-navy);}
    </style>
    """,
    unsafe_allow_html=True,
)

db = Database(DB_PATH)
db.initialize()
default_id = db.seed_if_empty()
scenarios = db.list_scenarios()
scenario_ids = [int(row["id"]) for row in scenarios]
scenario_names = {int(row["id"]): row["name"] for row in scenarios}

if st.session_state.get("scenario_id") not in scenario_ids:
    st.session_state.scenario_id = default_id

st.sidebar.title("FTE Ospedale")
selected_id = int(st.session_state.scenario_id)
st.sidebar.caption(f"Scenario attivo: **{scenario_names[selected_id]}**")

completed, total, _ = progress_counts(db, selected_id)
st.sidebar.progress(completed / total, text=f"{completed} sezioni completate su {total}")

PAGES = {
    "Configurazione struttura": configurazione.render,
    "Parametri struttura": parametri.render,
    "Organico attuale": organico.render,
    "Attività e fabbisogno": attivita.render,
    "Radiologia": radiologia.render,
    "Fattibilità turnazione": turnazione.render,
    "Risultati": risultati.render,
}
if st.session_state.get("active_page") not in PAGES:
    st.session_state.active_page = "Configurazione struttura"
st.sidebar.markdown("### Navigazione")
for label in PAGES:
    if st.sidebar.button(
        label,
        key=f"nav_{label}",
        use_container_width=True,
        type="primary" if st.session_state.active_page == label else "secondary",
    ):
        st.session_state.active_page = label
        st.rerun()

PAGES[st.session_state.active_page](db, selected_id)
