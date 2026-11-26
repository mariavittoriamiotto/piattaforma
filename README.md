# FTE Ospedale — prototipo Streamlit

Prototipo modulare per trasformare il modello `FTE_v3.xlsx` in un'applicazione testabile per configurazione, dimensionamento FTE e verifica preliminare della turnazione.

## Schermate disponibili

1. **Configurazione struttura** — introduzione alla piattaforma, gestione e attivazione degli scenari, anagrafica e UO.
2. **Parametri struttura** — ore settimanali, giorni lavorativi da 1 a 7, durata turno calcolata, festività, ferie, malattia e formazione.
3. **Organico attuale** — dotazione e, dopo il primo salvataggio, idoneità/Legge 104 distinte tra full-time e part-time.
4. **Attività e fabbisogno** — workload, turni, ambulatorio e sale operatorie.
5. **Radiologia** — sale/modalità, tempario, capacità e operatori per professione.
6. **Fattibilità turnazione** — verifica preliminare di FTE, turnisti e smonto notte.
7. **Risultati** — FTE nominali e netti, fabbisogno, gap, skill mix, pensionamenti, straordinari e confronto tra scenari.

La Home è stata eliminata: l'app parte direttamente da **Configurazione struttura**.

## Scenari

La gestione degli scenari si trova nella schermata **Configurazione struttura**, non nella sidebar. L'utente può:

- selezionare e attivare uno scenario;
- vedere la sua descrizione;
- creare uno scenario vuoto con nome, descrizione e anno;
- duplicare lo scenario attivo, assegnando alla copia un nuovo nome e una nuova descrizione.

La duplicazione copia UO, professioni, parametri, organico, attività, sale di Radiologia e stati di compilazione.

## Regole principali

- la sidebar serve solo per la navigazione e mostra lo scenario attivo;
- l'attivazione di una UO avviene dalla colonna **Attivo**, senza aprire la scheda;
- le professioni sono Medici, Infermieri, OSS, Tecnici sanitari e Tecnici di radiologia;
- i giorni lavorativi settimanali sono interi da 1 a 7;
- la durata del turno non è personalizzabile per UO: coincide sempre con `ore settimanali / giorni lavorativi settimanali`;
- il valore calcolato del turno si aggiorna immediatamente nella schermata Parametri, prima del salvataggio;
- la **Radioprotezione** è una caratteristica manuale di ogni UO: i 15 giorni di riposo biologico sono applicati solo quando la relativa spunta è selezionata, senza dipendere dal nome del reparto;
- i conteggi dell'organico sono interi;
- ore lavorate/anno, straordinario, IAS, Case di Comunità, recupero liste e ore di apertura sono inserite come interi;
- il campo **Giorni di copertura** non è mostrato: per le UO H24 si usa l'anno solare, per le altre UO con turni si usano i giorni lavorativi settimanali della professione moltiplicati per 52;
- lo stile usa blu, grigi e azzurri; rosso, arancione e verde restano riservati agli esiti.

## Organico in due fasi

1. L'utente compila i cinque campi della dotazione e seleziona **Salva dotazione**.
2. Compare una tabella con due righe, **Dipendenti full-time** e **Dipendenti part-time**. Per ciascuna riga si indicano: abilitati agli sforzi fisici, abilitati al lavoro notturno e beneficiari dell'esenzione Legge 104.
3. Gli idonei sono inizializzati al totale della propria riga; i beneficiari Legge 104 partono da zero. Con **Salva caratteristiche** la scheda viene considerata completa.
4. La Legge 104 riduce la disponibilità di 3 giorni al mese, cioè 36 giorni/anno. I part-time mantengono il peso di 0,5 FTE.

## Formule principali

```text
Durata turno = ore settimanali / giorni lavorativi settimanali
CAF = 1 / (1 - CAS)
FTE workload = ore lavorate × CAF / ore annue disponibili
FTE turni = operatori giornalieri × giorni di copertura derivati × durata turno × CAF / ore annue disponibili
FTE ambulatorio = ore ambulatoriali × CAF / ore annue disponibili
FTE sale = ore annue di sala × operatori × CAF / ore annue disponibili
FTE richiesti = max(FTE workload, FTE turni + ambulatorio + sale + IAS)
FTE nominali = full-time + 0,5 × part-time
FTE netti = FTE nominali − disponibilità corrispondente ai 36 giorni/anno dei beneficiari Legge 104
Skill mix = specializzandi o tirocinanti / dipendenti full-time
Tasso pensionamento = pensionamenti entro 3 anni / (full-time + part-time)
Tasso straordinari = ore straordinario / (ore settimanali × 52)
```

Per le UO radiologiche, il fabbisogno ottenuto dalle sale viene confrontato con il fabbisogno ordinario e viene utilizzato il maggiore, evitando il doppio conteggio.

La fattibilità della turnazione è intenzionalmente preliminare: verifica gli FTE netti, la consistenza dell'organico e gli abilitati al lavoro notturno, richiedendo un margine di una persona in smonto per ogni posizione notturna. Non produce ancora un calendario nominativo.

## Persistenza

Il database locale è `data/fte_app.db` e viene creato al primo avvio. Ogni salvataggio scrive in SQLite. Il file non è incluso nel pacchetto, quindi una nuova installazione parte con lo **Scenario iniziale** dimostrativo.

## Architettura

```text
app.py
screens/
    configurazione.py
    parametri.py
    organico.py
    attivita.py
    radiologia.py
    turnazione.py
    risultati.py
calculations/
    work_availability.py
    biological_rest.py
    fte.py
core/
    progress.py
    scenario_metrics.py
storage/
    database.py
tests/
```

## Avvio

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Test

```bash
PYTHONPATH=. python -m pytest -q
```
