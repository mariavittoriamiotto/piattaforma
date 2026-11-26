"""Organico attuale: prima consistenza, poi limitazioni separate per regime."""

import streamlit as st

from core.constants import TRAINEE_PROFESSIONS
from screens.common import render_progress


def _integer_row(label: str, key: str, value: float) -> int:
    label_column, value_column = st.columns([0.7, 0.3], vertical_alignment="center")
    label_column.markdown(f"**{label}**")
    return int(value_column.number_input(
        label,
        min_value=0,
        value=int(round(value)),
        step=1,
        format="%d",
        key=key,
        label_visibility="collapsed",
    ))


def _limit_input(label: str, key: str, value: float, maximum: int) -> int:
    return int(st.number_input(
        label,
        min_value=0,
        max_value=int(maximum),
        value=min(int(round(value)), int(maximum)),
        step=1,
        format="%d",
        key=key,
        label_visibility="collapsed",
    ))


def _exclusive_law104_inputs(
    key_prefix: str,
    total: int,
    law104_one: float,
    law104_two: float,
    one_column,
    two_column,
) -> tuple[int, int]:
    """Renderizza due conteggi Legge 104 che condividono lo stesso totale.

    Le due categorie descrivono persone diverse: un dipendente può essere
    conteggiato nel permesso per un assistito oppure in quello per due
    assistiti, mai in entrambi. I massimi dei due input vengono quindi
    aggiornati a ogni modifica usando la capienza residua della riga.
    """
    total = max(0, int(total))
    one_key = f"{key_prefix}_law104_one"
    two_key = f"{key_prefix}_law104_two"

    # Inizializza lo stato dai dati salvati e normalizza anche eventuali dati
    # legacy non validi, privilegiando la categoria "un assistito".
    one_value = int(st.session_state.get(one_key, round(law104_one)))
    two_value = int(st.session_state.get(two_key, round(law104_two)))
    one_value = min(max(0, one_value), total)
    two_value = min(max(0, two_value), total - one_value)
    st.session_state[one_key] = one_value
    st.session_state[two_key] = two_value

    with one_column:
        one_value = int(st.number_input(
            "Con permesso Legge 104 (un assistito)",
            min_value=0,
            max_value=total - two_value,
            step=1,
            format="%d",
            key=one_key,
            label_visibility="collapsed",
        ))

    # Il primo input può essere appena cambiato. Prima di creare il secondo
    # widget, riallinea il suo stato al nuovo massimo consentito.
    two_maximum = total - one_value
    if int(st.session_state[two_key]) > two_maximum:
        st.session_state[two_key] = two_maximum

    with two_column:
        two_value = int(st.number_input(
            "Con permesso Legge 104 (due assistiti)",
            min_value=0,
            max_value=two_maximum,
            step=1,
            format="%d",
            key=two_key,
            label_visibility="collapsed",
        ))

    return one_value, two_value


def _limitation_row(
    label: str,
    key_prefix: str,
    total: int,
    night_limited: float,
    law104_one: float,
    law104_two: float,
    retiring: float,
) -> tuple[int, int, int, int]:
    columns = st.columns([1.30, 0.45, 1.0, 1.0, 1.0, 1.0], vertical_alignment="center")
    columns[0].markdown(f"**{label}**")
    columns[1].markdown(f"**{total}**")
    with columns[2]:
        night_value = _limit_input(
            "Esentati dal lavoro notturno",
            f"{key_prefix}_night_limited",
            night_limited,
            total,
        )
    law104_one_value, law104_two_value = _exclusive_law104_inputs(
        key_prefix,
        total,
        law104_one,
        law104_two,
        columns[3],
        columns[4],
    )
    with columns[5]:
        retiring_value = _limit_input(
            "Pensionamento entro 3 anni",
            f"{key_prefix}_retiring",
            retiring,
            total,
        )
    return night_value, law104_one_value, law104_two_value, retiring_value


def _render_profession_form(db, scenario_id: int, unit: dict, profession: str) -> None:
    data = db.get_staffing(scenario_id, unit["id"], profession)
    key_prefix = f"staff_{unit['id']}_{profession}"
    trainees_allowed = profession in TRAINEE_PROFESSIONS

    st.markdown("#### Dotazione attuale")
    required_fields = "tre campi" if trainees_allowed else "due campi"
    st.caption(
        f"Compila i {required_fields} e salva. Solo dopo potranno essere specificati i permessi e le limitazioni associate a ciascun dipendenti."
    )
    with st.form(f"staffing_dotation_form_{unit['id']}_{profession}"):
        # st.caption("")
        full_time = _integer_row("1. Dipendenti full-time", f"{key_prefix}_full", data["full_time"])
        part_time = _integer_row("2. Dipendenti part-time", f"{key_prefix}_part", data["part_time"])
        trainees = 0
        if trainees_allowed:
            trainees = _integer_row(
                "3. Specializzandi", f"{key_prefix}_trainees", data["trainees"]
            )
        else:
            st.caption("Non sono previsti specializzandi/tirocinanti per questa professione.")
        if st.form_submit_button("Salva dotazione", type="primary", use_container_width=True):
            db.save_staffing_dotation(scenario_id, unit["id"], profession, {
                "full_time": full_time,
                "part_time": part_time,
                "trainees": trainees,
            })
            st.success("Dotazione salvata.")
            st.rerun()

    if not data["dotation_saved"]:
        st.info("Questa sezione sarà disponibile dopo il salvataggio della dotazione.")
        return

    full_time_total = int(round(data["full_time"]))
    part_time_total = int(round(data["part_time"]))
    st.markdown("#### Limitazioni, Legge 104 e pensionamenti")
    st.caption(
        "Inserire quante persone ricadono in ciascuna condizione; lavoro notturno e "
        "pensionamento possono sovrapporsi alle categorie Legge 104."
    )
    with st.container(border=True):
        headers = st.columns([1.30, 0.45, 1.0, 1.0, 1.0, 1.0])
        headers[0].markdown("**Tipologia**")
        headers[1].markdown("**Totale**")
        headers[2].markdown("**Esentati dal lavoro notturno**")
        headers[3].markdown("**Con permesso Legge 104 (un assistito)**")
        headers[4].markdown("**Con permesso Legge 104 (due assistiti)**")
        headers[5].markdown("**Pensionamento entro 3 anni**")

        ft_values = _limitation_row(
            "Dipendenti full-time",
            f"{key_prefix}_ft",
            full_time_total,
            data["full_time_night_limited"],
            data["full_time_law104_one"],
            data["full_time_law104_two"],
            data["full_time_retiring_3y"],
        )
        pt_values = _limitation_row(
            "Dipendenti part-time",
            f"{key_prefix}_pt",
            part_time_total,
            data["part_time_night_limited"],
            data["part_time_law104_one"],
            data["part_time_law104_two"],
            data["part_time_retiring_3y"],
        )
        st.caption(
            "Le due categorie Legge 104 sono alternative nella stessa riga: la loro somma "
            "non può superare il totale. Il massimo di ciascun campo si aggiorna in base "
            "alla capienza residua. Una persona a carico comporta 36 giorni/anno; "
            "due persone comportano 72 giorni/anno."
        )
        if st.button(
            "Salva limitazioni",
            type="primary",
            use_container_width=True,
            key=f"{key_prefix}_save_limitations",
        ):
            ft_night, ft_one, ft_two, ft_retiring = ft_values
            pt_night, pt_one, pt_two, pt_retiring = pt_values
            if ft_one + ft_two > full_time_total or pt_one + pt_two > part_time_total:
                st.error(
                    "Per ciascuna riga la somma tra permesso 104 per una e per due persone "
                    "non può superare il totale dipendenti."
                )
            else:
                db.save_staffing_limitations(scenario_id, unit["id"], profession, {
                    "full_time_night_limited": ft_night,
                    "full_time_law104_one": ft_one,
                    "full_time_law104_two": ft_two,
                    "full_time_retiring_3y": ft_retiring,
                    "part_time_night_limited": pt_night,
                    "part_time_law104_one": pt_one,
                    "part_time_law104_two": pt_two,
                    "part_time_retiring_3y": pt_retiring,
                })
                st.success("Limitazioni, permessi e pensionamenti salvati.")
                st.rerun()


def render(db, scenario_id: int) -> None:
    st.title("Organico attuale")
    st.caption(
        "Inserire numero di dipendenti full-time, part-time e, solo per Medici e Infermieri, specializzandi/tirocinanti. "
        "Dopo il salvataggio apparirà una sezione dove inserire limitazioni, permessi per la Legge 104 e previsione di pensionamenti."
    )
    render_progress(db, scenario_id)
    units = db.list_operating_units(scenario_id, active_only=True)
    if not units:
        st.warning("Configura almeno una UO attiva.")
        return

    unit_tabs = st.tabs([unit["name"] for unit in units])
    for unit_tab, unit in zip(unit_tabs, units):
        with unit_tab:
            st.subheader(unit["name"])
            profession_tabs = st.tabs(unit["professions"])
            for profession_tab, profession in zip(profession_tabs, unit["professions"]):
                with profession_tab:
                    _render_profession_form(db, scenario_id, unit, profession)

    completed, total = db.staffing_completion(scenario_id)
    st.info(f"{completed} schede organico completate su {total}")
