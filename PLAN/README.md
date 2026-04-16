# SVG Polish — Piano di Refactoring Completo

Questo piano guida il refactoring ossessivo di `svg_polish`, modulo per modulo, funzione per funzione, riga per riga. L'obiettivo finale e' un codebase che sia:

- **Pulitissimo**: ogni funzione fa una cosa sola, nomi chiari, zero codice morto
- **Documentatissimo**: docstring complete, commenti inline dove il perche' non e' ovvio, variabili e dizionari spiegati
- **Velocissimo**: zero allocazioni inutili, zero traversal ridondanti, complessita' ottimale
- **Sicurissimo**: test per ogni path, golden test per regressione, coverage 100%

## Stato Attuale

| Metrica | Valore |
|---------|--------|
| Test totali | 473 |
| Coverage | 100% |
| Type hints | 100% funzioni |
| Docstrings | 100% funzioni |
| Lint (ruff) | 0 errori |

## Fasi del Piano

| # | File | Fase | Priorita' |
|---|------|------|-----------|
| 01 | [01-code-cleanup.md](01-code-cleanup.md) | Pulizia e semplificazione codice | ALTA |
| 02 | [02-documentation.md](02-documentation.md) | Documentazione ossessiva | ALTA |
| 03 | [03-optimization.md](03-optimization.md) | Ottimizzazioni performance | MEDIA |
| 04 | [04-testing.md](04-testing.md) | Strategia test e sicurezza | ALTA |
| 05 | [05-type-safety.md](05-type-safety.md) | Type safety avanzata | MEDIA |
| 06 | [06-simplification.md](06-simplification.md) | Semplificazione architetturale | BASSA |

## Regole d'Ingaggio

1. **Mai rompere i test** — eseguire `uv run pytest tests/ -x -q` dopo ogni modifica
2. **Mai alterare l'output** — i golden test (`tests/test_golden.py`) devono passare sempre
3. **Coverage al 100%** — mai scendere sotto, aggiungere test se serve
4. **Commit atomici** — un commit per ogni modifica logica, mai commit giganti
5. **Misurare prima e dopo** — ogni ottimizzazione deve essere misurabile

## Come Usare

L'agente OpenCode configurato in `.opencode/` eseguira' questo piano automaticamente:

```bash
# Avvia l'agente polish
opencode

# Oppure esegui comandi specifici
opencode /clean      # Pulizia codice
opencode /document   # Documentazione
opencode /optimize   # Ottimizzazione
opencode /test       # Test completi
```
