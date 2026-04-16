# Fase 02 — Documentazione Ossessiva

## Obiettivo

Ogni riga di codice non banale deve essere comprensibile senza dover leggere il contesto circostante.
Un nuovo developer deve poter capire cosa fa ogni funzione, variabile, dizionario e costante
semplicemente leggendo il file.

## Regole di Documentazione

### Docstring delle Funzioni

Ogni funzione DEVE avere una docstring che includa:

1. **Riga di sommario** — cosa fa la funzione, in una riga
2. **Descrizione estesa** (se la logica non e' banale) — algoritmo usato, complessita', edge case
3. **Args** — ogni parametro con tipo e descrizione
4. **Returns** — cosa ritorna e in quali condizioni
5. **Raises** — eccezioni possibili (se rilevanti)
6. **Example** (per funzioni public API)

Formato:

```python
def scourString(in_string: str, options: optparse.Values | None = None) -> str:
    """Optimize an SVG string and return the result.

    Parses *in_string* as XML, runs the full optimization pipeline
    (namespace cleanup, style repair, color conversion, gradient dedup,
    path optimization, ID shortening, transform optimization, serialization),
    and returns the optimized SVG string.

    The pipeline runs ~15 optimization passes in a fixed order.
    If an optimization increases the output size, it is rolled back.

    Args:
        in_string: Raw SVG/XML string to optimize.
        options: Optimizer options from :func:`parse_args`. ``None`` uses defaults.
        stats: Optional :class:`ScourStats` to collect metrics. Created internally
            if not provided.

    Returns:
        The optimized SVG string. Guaranteed to render identically to the input
        (lossless optimization).

    Example:
        >>> from svg_polish.optimizer import scourString
        >>> result = scourString('<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#ff0000"/></svg>')
        >>> 'fill="red"' in result
        True
    """
```

### Commenti Inline

- **Perche', non cosa**: `# avoid recomputing on each iteration` (buono) vs `# increment i` (inutile)
- **Decisioni non ovvie**: spiegare PERCHE' un approccio e' stato scelto
- **Riferimenti a spec**: `# SVG 1.1 spec section 8.3.2: path shorthand commands`
- **Avvertenze**: `# WARNING: this mutates the referencedIDs dict via nodes.pop()`
- **Performance**: `# O(n) list building instead of O(n^2) del-in-loop`

### Variabili e Costanti

Ogni dizionario, lista, set e costante a livello di modulo deve avere un commento che spiega:

```python
# Named CSS colors mapped to their rgb() equivalents.
# Used by convertColor() as input; _name_to_hex (below) is the pre-computed hex form.
colors = {
    "aliceblue": "rgb(240, 248, 255)",
    ...
}

# Pre-computed name -> shortest hex form, built at import time from `colors` dict.
# Avoids regex parsing in the hot convertColor() path.
_name_to_hex = { ... }

# CSS/SVG default property values that can safely be removed.
# Source: https://www.w3.org/TR/SVG/propidx.html
# Key = property name, Value = default value.
default_properties = { ... }

# SVG attributes checked for url(#id) references during DOM traversal.
# Frozen for O(1) membership testing.
referencingProps = frozenset([...])
```

### Sezioni del File

Ogni sezione logica del file deve avere un header comment:

```python
# =============================================================================
# DOM Traversal and Reference Tracking
# =============================================================================

def findElementsWithId(...): ...
def findReferencedElements(...): ...

# =============================================================================
# ID Management (shortening, renaming, protection)
# =============================================================================

def shortenIDs(...): ...
def renameID(...): ...
```

## Checklist

### `optimizer.py` — Costanti e Dizionari

- [ ] `NS` — documentare ogni namespace
- [ ] `colors` — aggiungere header comment
- [ ] `_name_to_hex` — aggiungere header comment
- [ ] `default_properties` — aggiungere source reference
- [ ] `default_attributes` / `default_attributes_universal` / `default_attributes_per_element` — spiegare struttura
- [ ] `svgAttributes` — spiegare cosa sono e perche' frozenset
- [ ] `referencingProps` — spiegare ruolo nel tracking riferimenti
- [ ] `TEXT_CONTENT_ELEMENTS` — spiegare criterio di inclusione
- [ ] `_LENGTH_SCOUR_TYPES` / `_LENGTH_SCOUR_ATTRS` — spiegare ottimizzazione
- [ ] `XML_ENTS_*` — spiegare i tre dizionari di escape
- [ ] `KNOWN_ATTRS_ORDER` / `KNOWN_ATTRS_ORDER_BY_NAME` — spiegare ordinamento attributi

### `optimizer.py` — Funzioni (espandere docstring esistenti)

- [ ] `scourString` — documentare la pipeline completa step by step
- [ ] `clean_path` — documentare le 8 fasi dell'algoritmo
- [ ] `serializeXML` — documentare logica di indentazione e whitespace
- [ ] `convertColor` — documentare i 3 path (named, rgb, hex)
- [ ] `removeDefaultAttributeValues` — documentare meccanismo tainted set
- [ ] `collapse_singly_referenced_gradients` — documentare mutazione dict
- [ ] `removeDuplicateGradients` — documentare bucket key e loop di dedup
- [ ] `optimizeTransform` — documentare le 10+ regole di semplificazione

### Altri Moduli

- [ ] `css.py` — documentare parser CSS minimale
- [ ] `svg_regex.py` — documentare grammatica path SVG
- [ ] `svg_transform.py` — documentare grammatica transform SVG
- [ ] `stats.py` — documentare ogni campo di ScourStats
- [ ] `__init__.py` — documentare API pubblica

## Verifica

```bash
# Controllare che ogni funzione abbia una docstring
python3 -c "
import ast
with open('src/svg_polish/optimizer.py') as f:
    tree = ast.parse(f.read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        if not ast.get_docstring(node):
            print(f'MISSING: {node.lineno}: {node.name}')
" || echo "All functions documented"
```
