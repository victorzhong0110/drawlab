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

## Drag-and-drop pairing editor

The Streamlit app includes a browser-based draggable draw board (implemented as a local Streamlit custom component in `draw_editor/index.html`; no npm build or external JS needed). Drag one team onto another to exchange their places, or click two teams to swap. Moves are rejected if they violate current round record pools, seed restrictions, same-region avoidance, historical rematch avoidance, or the complete matching requirement. Use **Random legal draw** to construct a new legal pairing and **Reset** to restore the starting pairing. After editing, select **Analyze edited draw** to compare the chosen draw against a fresh random legal baseline, including per-region expected qualifiers and per-team advance probabilities. The original **Analyze all legal draws** functionality is still available for best/worst candidate analysis.

A drag affects only the current draw; it does not simulate or change past game results. Enter complete historical match outcomes before editing a later-round draw. The editor is a local Streamlit custom component and loads without a third-party frontend service.

## Auto-recalculating drag preview (v0.3)

Enable **Automatically analyze after each legal drag** in the Streamlit sidebar. On each legal drag or click-to-swap, the app immediately computes the edited pairing against a random legal-draw baseline and updates a regional impact chart and team advancement probability table. Set preview sample counts separately from the higher-quality full analysis.

An in-session bounded cache (100 results) is keyed by the complete input state, rules, seed and canonical pairing. Repeatedly visiting a pairing reuses its simulation. The random baseline is shared across all pairings in the same state. Changing teams, Elo, constraints, historical results, or random seed invalidates the relevant cache keys. The preview is low-sample Monte Carlo and is **not** a global-best claim; run the full analysis for candidate ranking and more reliable differences. A rough Monte Carlo standard error for the difference is reported.


## Bilingual interface / 中英文界面

In the Streamlit sidebar, choose **Language / 语言** → **中文** (default) or **English**. The drag-and-drop editor and the analytical table labels follow the selection. Team IDs, JSON schema, CLI flags and CSV import keys remain in English so switching language does not change calculation inputs.

在左侧栏选择 **Language / 语言**，可切换**中文（默认）**或 **English**。拖拽编辑器、分析标签和多数提示会同步切换。JSON 字段和内部队伍 ID 不翻译，防止影响计算和数据兼容。

## S16 example and automatic Elo-scale calibration

Use `s16_worlds_2026.json` in the upload control. The app now loads team counts, seed rules, series rules, rematch avoidance, ratings and history from the file on first import. The Elo rating scale can be auto-fitted when JSON contains at least 20 **BO1/map-level** records under `calibration_matches` with keys `a`, `b`, `winner` (and optional `best_of: 1`, `weight`). Series outcomes without map-level results are skipped. Without sufficient training results the UI clearly reports fallback to the JSON's `rules.rating_scale`, normally 400; scores alone cannot identify a reasonable scale. The S16 file uses previously discussed LoL Pro Elo scores, **not a verified pre-event Elo snapshot**. The calibration helper estimates probability scale only, it does not re-estimate individual team Elo ratings.

## v0.6 Swiss Draw Studio / 瑞士轮抽签沙盘

- `studio_frontend/index.html`: native Streamlit component with a **team pool above a multi-round bracket**. Drag a team into the current round's slot, or click a team and then a slot. Partial matches remain uncommitted; complete pairs become locked candidates.
- `studio.py`: validates partial matchings, enumerates **all legal completions** up to the configured cap, or samples legal completions uniformly conditional on locked pairs using exact continuation counts.
- The **Analyze Remaining Draws** button scores all feasible completions or a sampled subset, and draws Streamlit region-expectation, impact, team qualification, and remaining-draw-value charts. Old editor is retained below as a legacy compatibility path.
- Future rounds show **placeholders until results are entered**. The tool does not assert that future teams or results are known.
- Large candidate sets and Monte Carlo outputs remain approximate. The displayed best/worst are candidate extrema, not global guarantees when sampled. UI drag interaction has not been browser-verified.
