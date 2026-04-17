---
description: "Pulizia codice: rinomina variabili, elimina codice morto, semplifica pattern"
agent: polish
---

Esegui la fase 01 (Code Cleanup) dal piano in `PLAN/01-code-cleanup.md`.

Lavora sulla checklist, un item alla volta. Dopo ogni modifica:
1. Esegui `uv run pytest tests/ -x -q`
2. Se passa, procedi al prossimo item
3. Se fallisce, correggi e ritesta

Concentrati su:
- Rinominare variabili con nomi descrittivi
- Eliminare codice morto e commenti obsoleti
- Semplificare pattern ripetitivi
- Applicare principi Clean Code

Riporta cosa hai cambiato e il risultato dei test.
