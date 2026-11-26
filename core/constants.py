"""Costanti condivise dell'applicazione."""

PROFESSIONS = (
    "Medici",
    "Infermieri",
    "OSS",
    "Tecnici sanitari",
    "Tecnici di radiologia",
)

AREAS = (
    "Medica",
    "Laboratoriale"
)

SECTION_KEYS = (
    ("configurazione", "Configurazione struttura"),
    ("parametri", "Parametri struttura"),
    ("organico", "Organico attuale"),
    ("attivita", "Attività e fabbisogno"),
    ("radiologia", "Radiologia"),
    ("turnazione", "Fattibilità turnazione"),
    ("risultati", "Risultati"),
)

BIOLOGICAL_REST_DAYS = 15.0
LAW_104_DAYS_PER_MONTH = 3.0
LAW_104_MONTHS_PER_YEAR = 12
LAW_104_DAYS_PER_YEAR = LAW_104_DAYS_PER_MONTH * LAW_104_MONTHS_PER_YEAR
LAW_104_DAYS_ONE_DEPENDENT = LAW_104_DAYS_PER_YEAR
LAW_104_DAYS_TWO_DEPENDENTS = 2 * LAW_104_DAYS_PER_YEAR

# Gli specializzandi sono previsti soltanto per le professioni cliniche indicate.
# Per OSS e tecnici il dato non viene mostrato e viene sempre salvato a zero.
TRAINEE_PROFESSIONS = ("Medici", "Infermieri")

DEFAULT_WORK_PARAMETERS = {
    "Medici": {
        "weekly_hours": 38.0,
        "workdays_week": 5,
        "shift_hours": 7.6,
        "shift_is_auto": True,
        "holidays": 11.0,
        "leave_days": 32.5,
        "sickness_days": 8.0,
        "training_days": 7.0,
    },
    "Infermieri": {
        "weekly_hours": 36.0,
        "workdays_week": 5,
        "shift_hours": 7.2,
        "shift_is_auto": True,
        "holidays": 11.0,
        "leave_days": 32.5,
        "sickness_days": 9.0,
        "training_days": 7.0,
    },
    "OSS": {
        "weekly_hours": 36.0,
        "workdays_week": 5,
        "shift_hours": 7.2,
        "shift_is_auto": True,
        "holidays": 11.0,
        "leave_days": 32.5,
        "sickness_days": 13.0,
        "training_days": 7.0,
    },
    "Tecnici sanitari": {
        "weekly_hours": 36.0,
        "workdays_week": 5,
        "shift_hours": 7.2,
        "shift_is_auto": True,
        "holidays": 11.0,
        "leave_days": 32.5,
        "sickness_days": 7.0,
        "training_days": 7.0,
    },
    "Tecnici di radiologia": {
        "weekly_hours": 36.0,
        "workdays_week": 5,
        "shift_hours": 7.2,
        "shift_is_auto": True,
        "holidays": 11.0,
        "leave_days": 32.5,
        "sickness_days": 7.0,
        "training_days": 7.0,
    },
}
