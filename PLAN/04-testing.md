# Fase 04 — Strategia Test e Sicurezza

## Obiettivo

Ogni modifica al codice deve essere coperta da test. I test devono essere:
- **Esaustivi**: coprire ogni branch, ogni edge case
- **Veloci**: la suite completa deve girare in <5 secondi
- **Stabili**: nessun test flaky, nessuna dipendenza dall'ordine
- **Leggibili**: ogni test ha un nome che descrive cosa testa

## Test Esistenti

| File | Test | Cosa copre |
|------|------|------------|
| `test_optimizer.py` | 261 | Test originali Scour (unittest) |
| `test_public_api.py` | 19 | API pubblica `optimize()`, `optimize_file()` |
| `test_css.py` | 3 | Parser CSS minimale |
| `test_parsers.py` | 32 | `svg_regex.py` e `svg_transform.py` |
| `test_coverage.py` | 93 | Edge case e branch non coperti |
| `test_remaining_coverage.py` | 31 | Gap coverage finali |
| `test_fixtures.py` | 30 | SVG fixture reali |
| `test_golden.py` | 4 | Regressione output char-per-char |
| **Totale** | **473** | **100% coverage** |

## Test da Aggiungere

### Test di Regressione Aggiuntivi

- [ ] Golden test per ogni flag CLI (`--strip-xml-prolog`, `--no-line-breaks`, ecc.)
- [ ] Golden test con SVG contenenti `<style>` CSS inline
- [ ] Golden test con SVG contenenti `<script>` (devono essere preservati)
- [ ] Golden test con SVG con namespace custom (devono essere preservati con `--keep-editor-data`)

### Test di Performance

- [ ] Test che verifica che `clean_path` e' O(n) e non O(n^2)
  ```python
  def test_clean_path_linear_time():
      """Path optimization must scale linearly with segment count."""
      small = make_path(100)
      large = make_path(10000)  # 100x more segments
      t_small = time_it(lambda: scourString(small))
      t_large = time_it(lambda: scourString(large))
      # Should be ~100x, not ~10000x
      assert t_large / t_small < 200
  ```

### Test di Robustezza

- [ ] SVG malformato (tag non chiusi, attributi invalidi)
- [ ] SVG vuoto (`<svg></svg>`)
- [ ] SVG con solo whitespace
- [ ] SVG enorme (>1MB) — non deve crashare per memoria
- [ ] Path con migliaia di segmenti
- [ ] Gradienti con centinaia di stop
- [ ] ID con caratteri speciali (unicode, spazi)

### Test di Correttezza

- [ ] Ogni funzione di `clean_path` testata individualmente
- [ ] `convertColor` con tutti i 147 colori CSS nominati
- [ ] `optimizeTransform` con ogni tipo di trasformazione
- [ ] `serializeXML` con ogni combinazione di indentazione
- [ ] Round-trip: `parse(serialize(parse(input))) == parse(input)`

### Property-Based Testing (hypothesis)

- [ ] Aggiungere `hypothesis` alle dev dependencies
- [ ] Generare SVG casuali validi e verificare che l'output sia SVG valido
- [ ] Generare path data casuali e verificare che la semplificazione sia corretta
- [ ] Generare colori casuali e verificare che la conversione sia idempotente

## Comandi

```bash
# Esegui tutti i test
uv run pytest tests/ -x -q

# Test con coverage dettagliata
uv run pytest tests/ --cov=svg_polish --cov-report=term-missing

# Solo golden test (veloce verifica regressione)
uv run pytest tests/test_golden.py -v

# Test specifico
uv run pytest tests/test_optimizer.py::NomeTest -v

# Test con output verbose per debugging
uv run pytest tests/ -v --tb=long
```
