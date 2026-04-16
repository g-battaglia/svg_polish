# Fase 05 — Type Safety Avanzata

## Stato Attuale

- Tutte le 80 funzioni hanno type hints (parametri + return)
- `from __future__ import annotations` abilitato
- `TYPE_CHECKING` block per import `Document`, `Element`
- `py.typed` marker presente

## Miglioramenti Pianificati

### TypedDict per Opzioni

Sostituire `optparse.Values` con un `TypedDict` tipizzato:

```python
class ScourOptions(TypedDict, total=False):
    digits: int
    cdigits: int
    simple_colors: bool
    style_to_xml: bool
    group_collapse: bool
    group_create: bool
    keep_defs: bool
    keep_editor_data: bool
    remove_descriptive_elements: bool
    strip_ids: bool
    shorten_ids: bool
    shorten_ids_prefix: str
    # ... tutti i campi
```

### Tipi piu' Specifici

- [ ] `dict[str, str]` per style maps → `StyleMap = dict[str, str]`
- [ ] `dict[str, Element]` per identified elements → `IdentifiedElements`
- [ ] `dict[str, set[Element]]` per referenced IDs → `ReferencedIDs`
- [ ] `list[tuple[str, list[Decimal]]]` per path data → `PathData`
- [ ] `list[tuple[str, list[Decimal]]]` per transform data → `TransformData`

### Protocol per Nodi DOM

```python
class SVGNode(Protocol):
    def getAttribute(self, name: str) -> str: ...
    def setAttribute(self, name: str, value: str) -> None: ...
    def removeAttribute(self, name: str) -> None: ...
    @property
    def nodeName(self) -> str: ...
    @property
    def nodeType(self) -> int: ...
```

### Mypy Strict

- [ ] Abilitare `mypy --strict` e risolvere tutti gli errori
- [ ] Eliminare tutti gli `Any` dove possibile
- [ ] Aggiungere `@overload` per funzioni con return type variabile

## Verifica

```bash
uv run mypy src/svg_polish/ --strict
```
