---
description: "Documentazione ossessiva: docstring, commenti, variabili, dizionari, riga per riga"
agent: polish
---

Esegui la fase 02 (Documentazione) dal piano in `PLAN/02-documentation.md`.

Lavora sulla checklist, un item alla volta. Il tuo obiettivo e' che un developer
che non ha mai visto questo codice possa capire TUTTO leggendo solo il file.

Per ogni funzione, assicurati che la docstring abbia:
- Riga di sommario
- Descrizione algoritmo (se non banale)
- Args con tipo e descrizione
- Returns con descrizione
- Complessita' se rilevante

Per ogni dizionario/costante a livello di modulo:
- Commento che spiega cosa contiene, chi lo usa, perche' esiste

Per ogni riga non banale:
- Commento inline che spiega il PERCHE'

Aggiungi header comment per separare le sezioni logiche del file.

Dopo ogni batch di modifiche: `uv run pytest tests/ -x -q`
