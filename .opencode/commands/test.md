---
description: "Test completi: esegui suite, verifica coverage, aggiungi test mancanti"
agent: polish
---

Esegui una verifica completa della salute del progetto:

## Step 1: Esegui tutti i test
!`cd /Users/giacomo/dev/svg_polish && uv run pytest tests/ -x -q`

## Step 2: Verifica coverage
!`cd /Users/giacomo/dev/svg_polish && uv run pytest tests/ --cov=svg_polish --cov-report=term-missing -q`

## Step 3: Verifica golden test
!`cd /Users/giacomo/dev/svg_polish && uv run pytest tests/test_golden.py -v`

## Step 4: Lint
!`cd /Users/giacomo/dev/svg_polish && uv run ruff check src/svg_polish/`

## Step 5: Type check
!`cd /Users/giacomo/dev/svg_polish && uv run mypy src/svg_polish/ 2>&1 || true`

Analizza i risultati e riporta:
- Numero test passati/falliti
- Coverage percentuale per ogni modulo
- Eventuali errori lint o type
- Suggerimenti per test aggiuntivi se trovi gap

Se trovi linee non coperte, scrivi test per coprirle.
Se trovi errori, correggili immediatamente.
