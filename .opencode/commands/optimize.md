---
description: "Ottimizzazione performance: elimina allocazioni, riduce complessita', profila"
agent: polish
---

Esegui la fase 03 (Ottimizzazione) dal piano in `PLAN/03-optimization.md`.

Concentrati sulle ottimizzazioni ad alta priorita':
1. Eliminare il global `scouringContext` — creare classe con `__slots__`
2. Backtracking in `removeDefaultAttributeValues` invece di `tainted.copy()`
3. Cache per attributi DOM letti frequentemente
4. Lazy parsing CSS in `findReferencedElements`

Per ogni ottimizzazione:
1. Misura il tempo PRIMA con un test rapido
2. Implementa la modifica
3. Esegui `uv run pytest tests/ -x -q` — DEVE passare
4. Esegui `uv run pytest tests/test_golden.py -v` — output IDENTICO
5. Misura il tempo DOPO
6. Riporta il miglioramento

MAI sacrificare correttezza per velocita'.
