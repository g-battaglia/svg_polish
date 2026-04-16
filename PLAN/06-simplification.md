# Fase 06 — Semplificazione Architetturale

## Obiettivo

Ridurre la complessita' di `optimizer.py` (~4700 righe) spezzandolo in moduli coesi
senza alterare l'API pubblica.

## Struttura Proposta

```
src/svg_polish/
├── __init__.py              # API pubblica: optimize(), optimize_file()
├── optimizer.py             # Pipeline principale: scourString(), parse_args()
├── stats.py                 # ScourStats (gia' estratto)
├── css.py                   # Parser CSS (gia' estratto)
├── svg_regex.py             # Parser path SVG (gia' estratto)
├── svg_transform.py         # Parser transform SVG (gia' estratto)
├── constants.py             # NUOVO: colors, default_properties, NS, svgAttributes
├── types.py                 # NUOVO: Unit, SVGLength, type aliases
├── dom.py                   # NUOVO: findElementsWithId, findReferencedElements, renameID
├── style.py                 # NUOVO: _getStyle, _setStyle, repairStyle, convertColor
├── gradient.py              # NUOVO: gradient collapse, dedup, duplicate stops
├── path.py                  # NUOVO: clean_path, serializePath, parseListOfPoints
├── transform_opt.py         # NUOVO: optimizeTransform, optimizeAngle
├── serialize.py             # NUOVO: serializeXML, make_well_formed
├── cli.py                   # NUOVO: parse_args, run, start, getInOut
└── py.typed
```

## Regole di Estrazione

1. **Non rompere l'API** — `from svg_polish.optimizer import scourString, parse_args` deve continuare a funzionare
2. **Import lazy** — I nuovi moduli sono importati da `optimizer.py`, non dall'utente
3. **Un modulo per dominio** — Ogni modulo ha una responsabilita' chiara
4. **Nessuna dipendenza circolare** — DAG di dipendenze pulito
5. **Test invariati** — I test importano da `optimizer.py` e continuano a funzionare

## Ordine di Estrazione

1. `constants.py` — zero dipendenze, piu' semplice
2. `types.py` — dipende solo da `constants.py`
3. `dom.py` — dipende da `constants.py`
4. `style.py` — dipende da `dom.py`, `constants.py`
5. `gradient.py` — dipende da `dom.py`, `style.py`
6. `path.py` — dipende da `svg_regex.py`, `constants.py`
7. I restanti in qualsiasi ordine

## Rischi

- **Performance**: import aggiuntivi hanno costo minimo (~1ms) ma da verificare
- **Complessita'**: troppi moduli possono rendere il codice piu' difficile da navigare
- **Backwards compatibility**: utenti che importano funzioni interne da `optimizer.py`

## Decisione

Questa fase e' OPZIONALE e da valutare dopo le fasi 01-04.
Il file unico da ~4700 righe e' gestibile con buona documentazione e sezioni chiare.
La splitting ha senso solo se il team cresce o se moduli specifici vengono riusati altrove.
