# DrawLab — Swiss & Knockout Draw Analyzer

An extensible prototype that analyzes **every legal draw** (up to a configurable cap), compares the **best and worst** for each region, calculates the **random baseline**, compares a supplied **actual draw**, and estimates **individual team advancement** via Monte Carlo.

## Quick start

Python 3.10+; core requires **no third-party packages**.

```bash
cd drawlab
python cli.py demo.json --samples 500 --baseline 3000 --csv results.csv > results.json
python -m unittest -v
```

Graphical app:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Input

See [`demo.json`](demo.json). Teams require unique `id`, `region`, `elo`, and optional `seed`. `history` is a list of full played rounds (each event has `round`, `a`, `b`, `winner`). To rank the real draw, add `"actual_draw": [["A","C"],["B","D"],...]` for the current round.

Rule options:

- `format`: `swiss` / `knockout`.
- `wins_to_advance`, `losses_to_eliminate`: Swiss thresholds.
- `same_region`: `off`, `first`, `always`.
- `avoid_rematches`: `true` / `false`.
- `swiss_same_record`: `true` / `false`.
- `opening_seed_pairs`: e.g. `[[1,4],[2,3]]`; first-round seed-pair restrictions.
- `bo1`, `bo_decider`, `bo_knockout`: odd best-of counts.
- `rating_scale`: logistic Elo scaling (default 400).

**Tournament status:** Start from 0-0 with `history: []`, or enter all previously finished rounds and analyze the current state. Swiss accepts any even team count, subject to valid full record-pool matchings. Knockout currently accepts only powers of 2 (2,4,8,16,32,...) and models successive randomly drawn single-elimination rounds; it does not yet fix bracket positions through an entire elimination tree.

**Sampling:** The core samples complete valid matchings **uniformly**, via recursive continuation counts. This may differ from a physical sequential draw/rejection algorithm. Small candidate spaces are exhaustively enumerated. Beyond the cap, the CLI/UI samples distinct legal candidate draws and reports approximate best/worst. Match results use fixed Elo converted to BO1/3/5 probability. Each downstream round is drawn randomly.

**Important limitations:** There is no support yet for Swiss record-pool floating, byes, third-place matches, best-of rating calibration, home advantage, side selection, locked TV brackets, custom tie-breakers, dynamic Elo ratings, or conditional sequential-draw algorithms. Strict avoidance rules may generate states with no legal continuation; these are flagged as **failed simulations** and must be resolved by a competition-specific fallback policy, not silently discarded. Monte Carlo SE is given separately from Elo model uncertainty. The UI makes no network requests, and ratings are user-provided.

**Interpretation:** Compare `actual - random baseline` separately at each round from the actual pre-draw state. Such conditional effects cannot be summed across rounds to get total draw luck. For a joint analysis, explicitly simulate the entire tournament from 0-0, comparing an agreed draw-policy strategy to a pure random baseline.
