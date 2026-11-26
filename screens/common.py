"""Componenti visivi condivisi tra le schermate."""

from html import escape

import streamlit as st

from core.constants import SECTION_KEYS
from core.progress import progress_counts


def render_progress(db, scenario_id: int) -> dict[str, bool]:
    completed, total, status = progress_counts(db, scenario_id)
    st.progress(
        completed / total if total else 0,
        text=f"{completed} sezioni completate su {total}",
    )
    return status


def render_simple_table(rows: list[dict]) -> None:
    """Renderizza una tabella leggera senza dipendenze da pandas/pyarrow."""
    if not rows:
        return
    headers = list(rows[0])
    head = "".join(f"<th>{escape(str(item))}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row.get(item, '')))}</td>" for item in headers) + "</tr>"
        for row in rows
    )
    st.markdown(
        f"""
        <table style="width:100%; border-collapse:collapse; margin-bottom:1rem">
          <thead><tr>{head}</tr></thead><tbody>{body}</tbody>
        </table>
        <style>
          table th, table td {{text-align:left; padding:.55rem .7rem; border-bottom:1px solid #e3e8ef;}}
          table th {{background:#f6f8fb;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_status_table(status: dict[str, bool]) -> None:
    rows = [
        {"Sezione": label, "Stato": "Completa" if status.get(key) else "Da completare"}
        for key, label in SECTION_KEYS
    ]
    render_simple_table(rows)
