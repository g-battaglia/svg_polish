# Fase 01 — Pulizia e Semplificazione Codice

## Principi Clean Code

- Ogni funzione fa **una sola cosa**
- Nomi di variabili che dicono esattamente cosa contengono
- Nessun commento che spiega il "cosa" (il codice deve parlare da solo)
- Commenti solo per il "perche'" quando non e' ovvio
- Zero codice morto, zero import inutili
- Costanti con nomi UPPER_SNAKE_CASE e raggruppate per dominio

## Checklist per `optimizer.py`

### Variabili e Nomi

- [x] Rinominare variabili a singola lettera (`s`, `i`, `j`, `c`, `m`, `w`, `h`) con nomi descrittivi
- [x] Rinominare `num` generico in nomi specifici (`num_bytes_saved`, `num_elements_removed`, ecc.)
- [x] Rinominare `id` (shadowing builtin) in `elem_id` o `node_id`
- [x] Rinominare `str` parametro in `SVGLength.__init__` (shadowing builtin)
- [x] Rinominare `input`/`output` in `start()` (shadowing builtins)
- [x] Unificare naming: `camelCase` vs `snake_case` — preferire `snake_case` per nuove funzioni

### Struttura e Organizzazione

- [x] Raggruppare costanti in sezioni chiare con commenti di separazione
- [ ] Spostare `colors` dict, `default_properties`, `default_attributes` in un modulo `constants.py`
- [ ] Spostare `Unit` e `SVGLength` in un modulo `types.py`
- [x] Raggruppare funzioni per area: DOM traversal, style, gradient, path, serialize, CLI
- [ ] Estrarre funzioni interne troppo lunghe (>50 righe) in helper con nomi chiari

### Codice Morto e Ridondanze

- [x] Rimuovere commenti `# TODO` obsoleti
- [x] Rimuovere commenti `# Cyn:` che sono note storiche non piu' rilevanti
- [x] Eliminare `generateDefaultOptions()` (wrapper inutile di `sanitizeOptions()`)
- [x] Semplificare pattern `if x != "":` in `if x:`
- [ ] Eliminare variabile `i = 0` seguita da `for i in range(i, ...)` — usare direttamente il range

### Pattern da Semplificare

- [x] `len(val) >= 7 and val[0:5] == "url(#"` → `val.startswith("url(#")`
- [x] `val[5 : val.find(")")]` → regex precompilata per estrarre URL ref
- [x] `for i in range(len(list))` → `for i, item in enumerate(list)` o iterazione diretta
- [ ] `node.attributes.item(i).nodeName for i in range(node.attributes.length)` → helper method
- [ ] Catene `if/elif` ripetute per tipi di comando path → dispatch dict

## Verifica

```bash
uv run pytest tests/ -x -q                    # Tutti i test passano
uv run pytest tests/test_golden.py -v          # Output identico
uv run ruff check src/svg_polish/              # Zero errori
uv run ruff check src/svg_polish/ --statistics # Nessun warning
```
