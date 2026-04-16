# Fase 03 — Ottimizzazioni Performance

## Obiettivo

Rendere svg_polish il piu' veloce possibile su SVG di qualsiasi dimensione.
Ogni ottimizzazione deve essere misurabile con benchmark prima/dopo.

## Benchmark di Riferimento

Creare `benchmarks/bench_optimizer.py`:

```python
"""Benchmark suite per misurare le performance dell'optimizer."""
import time
from pathlib import Path
from svg_polish.optimizer import scourString, parse_args

FIXTURES = Path("tests/fixtures")

def bench(name, svg_str, options=None, iterations=100):
    start = time.perf_counter()
    for _ in range(iterations):
        scourString(svg_str, options)
    elapsed = time.perf_counter() - start
    print(f"{name}: {elapsed:.3f}s ({iterations} iter, {elapsed/iterations*1000:.1f}ms/iter)")

if __name__ == "__main__":
    complex_svg = (FIXTURES / "complex-scene.svg").read_text()
    xlink_svg = (FIXTURES / "xlink-references.svg").read_text()
    
    bench("complex-scene (default)", complex_svg)
    bench("xlink-references (default)", xlink_svg)
    bench("complex-scene (max-opt)", complex_svg, 
          parse_args(["--enable-viewboxing", "--shorten-ids", "--create-groups"]))
```

## Ottimizzazioni Completate

- [x] Cache `_getStyle`/`_setStyle` su nodi DOM
- [x] `frozenset` per `svgAttributes`, `referencingProps`, `TEXT_CONTENT_ELEMENTS`
- [x] Merge 10 `getElementsByTagName` in singolo traversal con dispatch
- [x] O(n) list building in `clean_path` (era O(n^2) con `del data[i]`)
- [x] `re.sub` per whitespace (era O(n^2) con `while "  " in text`)
- [x] Pre-computed `_name_to_hex` per colori
- [x] Parametri opzionali per evitare ricalcolo mappe DOM

## Ottimizzazioni Pianificate

### Alta Priorita'

- [ ] **Eliminare global `scouringContext`** — Creare `ScouringPrecision` con `__slots__`,
  passare come parametro. Rende il codice rientrante e piu' testabile.

- [ ] **Backtracking in `removeDefaultAttributeValues`** — Invece di `tainted.copy()` per ogni
  figlio, usare add/discard sulla stessa set. Riduce allocazioni per documenti profondi.

- [ ] **Cache `node.getAttribute()` hot calls** — Profilare e cachare gli attributi letti
  piu' frequentemente (`id`, `style`, `fill`, `stroke`).

- [ ] **Lazy parsing in `findReferencedElements`** — Non parsare CSS degli `<style>` element
  ad ogni chiamata. Cachare il risultato sul nodo.

### Media Priorita'

- [ ] **`convertColors` iterativo** — Sostituire la ricorsione con uno stack esplicito
  per evitare overhead di chiamata su documenti profondi.

- [ ] **Compilare regex `url(#...)` una sola volta** — `findReferencingProperty` usa
  confronti stringa manuali. Una regex precompilata sarebbe piu' chiara e potenzialmente
  piu' veloce.

- [ ] **`serializePath` con join ottimizzato** — Pre-allocare la lista di stringhe
  invece di concatenare.

### Bassa Priorita'

- [ ] **Parallelizzare operazioni indipendenti** — `convertColors` e `reducePrecision`
  sono indipendenti e potrebbero essere eseguiti in parallelo (ma GIL limita).

- [ ] **Profiling con cProfile** — Eseguire profiling su SVG reali grandi (>1MB)
  per identificare colli di bottiglia non previsti.

## Verifica

Ogni ottimizzazione deve:
1. Non alterare l'output (golden test)
2. Mostrare miglioramento misurabile nel benchmark
3. Mantenere coverage al 100%
