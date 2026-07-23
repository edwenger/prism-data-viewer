# COMBINED_PAGE_PLAN.md — PRISM1 + PRISM2 Combined Household View

Plan for a 5th landing-page option: a combined view of the households that continue across both
cohorts, one stitched per-individual timeline. Plan only — no implementation yet.

## 1. Verified facts (checked against repo + data)

**Architecture (correction: the stack is Plotly, not Bokeh).**
- Generator: `generate_viewer.py`, single function `create_interactive_viewer(site, output_file,
  is_prism2=False)`, heavily branched on `is_prism2`. Emits standalone Plotly HTML
  (`include_plotlyjs='cdn'`), then re-opens the file and injects a `keyboard_nav_script` before
  `</body>`.
- Navigation: all households' traces live in one figure; a per-household dropdown flips a
  `visible` boolean array over the full trace list. **Per-household trace blocks must have a
  fixed, consistent trace count** — the code pads with empty `go.Scatter(x=[],y=[])` traces to
  keep indices aligned; the injected JS (`hapTraceRanges`, `toggleHaplotypes`, `selectHousehold`)
  depends on these stable ranges.
- Data prep: `process_data.py` → cleaned CSVs. Landing page: `docs/index.html`, a `.sites` grid
  of `.site-card` blocks (4 today).

**Data.**
- Shared ID space: **148 individuals** appear in both `prism_cleaned_nagongera.csv` and
  `prism2_cleaned.csv` (same integer `id`). **All 148 stayed in the same household** across
  cohorts — matching is unambiguous.
- Household_Id format differs: PRISM1 `h_143006701`, PRISM2 bare `143006701`; strip `h_` to align.
- **Matched households: 33** (PRISM1-nagongera ∩ PRISM2). 33/80 PRISM2 households ≈ ~41% ("~1/3"
  confirmed); all 5 analyst-confirmed IDs present.
- **DOB derivable, low-complexity**: both CSVs carry a fractional per-observation `age`;
  `DOB ≈ date − age·365.25`, cross-cohort estimates agree within 0–9 days. PRISM2 also has
  `enrollment_date` + `enrolled_prism1` flag as a cross-check.
- Timeline: PRISM1 2011-08-13→2017-07-06; PRISM2 2017-09-27→2019-11-06; gap ≈ **83 days**. Data
  ends 2019 — lock x-range ~2011-04 → 2020-01.
- Streams: PRISM1 = microscopy density (same assay/units as PRISM2), LAMP binary, gametocytes
  Yes/No, household traps. PRISM2 = + qPCR density, gametocyte qPCR, COI, pfama1 haplotypes,
  membrane-feeding/oocyst.

## 2. Design — per-household stitched view

- **Scope**: matched households only (33), computed at runtime (not hardcoded). Default rows =
  individuals present in **both** cohorts; consider dimmed context rows for P1-only/P2-only
  members (open question).
- **Rows (y)**: one per individual, sorted by **DOB** (oldest→youngest); merge a shared `idx`
  onto both subsets by `id` so each person is ONE row across both periods. Label: birth-year +
  gender (e.g. `b.2005 F`) — recommended over age-at-enrollment (which differs by cohort). The
  "aged-out at 10, re-enrolled at 12" break renders naturally as a within-row time gap.
- **X**: single continuous date axis ~2011→2020; stitching is automatic (both CSVs store real
  dates — just don't split the axis).
- **Boundary/gap**: one layout `vrect` shading the ~83-day gap (2017-07-06→2017-09-27) + a thin
  divider + "PRISM1 | PRISM2" annotation, added once to layout.
- **Traps row (y=−1)**: concatenate PRISM1 + PRISM2 trap summaries into one continuous row;
  reuse existing parity coloring + sporozoite dots.

### Glyph normalization (reuse existing per-period styles where possible)
| Stream | Normalize? | Treatment |
|---|---|---|
| Age/DOB row axis | **Yes (required)** | DOB-derived shared `idx`. Low complexity. |
| Microscopy density bubble | Comparable as-is | Identical YlOrRd log-size glyph both spans; one colorbar. |
| LAMP (P1) vs qPCR (P2) submicroscopic | No — side by side | P1: fixed-size light-yellow; P2: density-sized. Legend "LAMP/qPCR positive (submicro)". |
| Haplotype asterisks | P2 span only | Unchanged. |
| Gametocyte ring | No — per-period | P1 fixed width; P2 width by oocyst prevalence. |
| DMFA/oocyst/COI | P2 hover only | Unchanged. |
| Traps + sporozoite | Unify | Concatenate P1+P2. |

## 3. Concrete change list

`generate_viewer.py`:
1. `compute_matched_households()` → 33 Household_Ids (bare) + 148 shared IDs; assert the 5;
   print counts.
2. `compute_dob(df)` → per-`id` DOB from median(`date − age·365.25`).
3. Extract PRISM1 & PRISM2 trap-loading into reusable helpers.
4. `create_combined_viewer(output_file='docs/combined.html')`: load both CSVs; strip `h_`; filter
   to 33 HH + 148 individuals; per HH build DOB-sorted `idx`, merge; emit PRISM1 trace block
   (`is_prism2=False` glyphs) then PRISM2 block (`is_prism2=True`) preserving padding discipline
   (constant per-HH trace count — pad empty P1 haplotype/qPCR slots); add gap vrect/divider;
   lock x-range; reuse dropdown + injected nav JS. **Recommended**: factor the per-household
   trace-emitting logic out of `create_interactive_viewer` into a shared helper called twice per
   household (minimizes duplication; the alternative is copying the loop).
5. Call it in `__main__`.

`docs/index.html`: 5th `.site-card` → "PRISM1 + PRISM2 Combined", desc "Matched households
continuing across both cohorts (2011–2019) — 33 households, one stitched timeline per individual",
button → `combined.html`.

`README.md`: document the 5th page.

## 4. Staged build order
1. Matching + DOB layer (print: expect 33 HH, 148 individuals). 2. Row layout (DOB sort, idx,
labels). 3. Trace emission reusing per-period glyph code; one household rendering across both
spans. 4. Boundary shading/divider + locked x-range. 5. Unified traps row. 6. Wire dropdown +
nav JS; verify haplotype toggle survives the doubled per-HH trace blocks + padding. 7. Landing
card + README.

## 5. Open questions / risks
- **Shared-only vs all members** (default shared-only; decide on dimmed context rows).
- **Row label** form (birth-year+gender recommended vs current-age).
- **Trace-count/padding** is the main correctness risk — the nav JS assumes constant per-HH trace
  counts; the combined block ~doubles trace groups, so the empty-trace padding must extend so P1's
  absent haplotype/qPCR glyphs occupy fixed slots. Mechanical but the thing to get right.
- **Env**: install `requirements.txt` into a venv (pandas/plotly not present system-wide) before
  running `generate_viewer.py`.
- **x-range**: request says 2011–2020 but data ends 2019-11; lock ~2011 → 2020-01.
- **File size**: expected < 2 MB, in line with existing pages.

## Critical files
`generate_viewer.py` · `docs/index.html` · `data/prism_cleaned_nagongera.csv` ·
`data/prism2_cleaned.csv` · `README.md`
