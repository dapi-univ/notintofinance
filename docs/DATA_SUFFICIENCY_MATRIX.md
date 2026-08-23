# KEJORA Data Sufficiency Matrix

Verified against the implemented warehouse, the approved research roadmap, the current Zapi
`finance:idx` and `finance:pluang` documentation, and bounded live samples on 2026-08-23.
This document defines data requirements, not unlocked analytics formulas. A source marked
`partial` must not be presented to downstream research as complete.

## Dataset completeness classes

| Class | Dataset | Required coverage | Current state | Collection decision |
| --- | --- | --- | --- | --- |
| A — full-universe foundational | IDX EOD OHLC, previous, volume shares, value IDR, frequency | Every active/provider-supported IDX stock, every trading session | 782 of 962 active stocks have stored history; latest session has 642 rows | Use one market-wide `stock-summary` request for ordinary EOD, with isolated row validation. Retain `stock-history` for backfill, reconciliation, and repairs. |
| A — full-universe foundational | Foreign buy/sell shares | Same universe and continuity as EOD | Present wherever EOD history is present | Persist the `stock-summary` fields with EOD. `foreign-flow` is complementary market-wide reconciliation, not a duplicate canonical fact. |
| A — full-universe foundational | Non-regular volume/value/frequency | Same universe and continuity as EOD | Canonical columns exist but current rows are null because `stock-history` does not supply them | Populate from `stock-summary`; keep them separate from regular-market facts. |
| A — market metadata | Listed/tradeable shares and index-related provider fields | Broad market; daily/when changed | Available in `stock-summary`, not canonical | Keep in validated snapshot/provenance for selection research. `WeightForIndex` and `IndexIndividual` are provider fields with ambiguous official-index semantics and must not be labelled official portfolio weights. |
| B — full-universe flow/structural | Per-stock broker summary | Daily for every eligible active ticker if quota supports it | 60 top-N rows from three canaries | Independent daily collector. The source is capped top-N (normally ten per side), not complete broker participation. |
| B — full-universe flow/structural | Tradebook aggregates | Daily for every eligible active ticker if quota supports it | Live contract verified; no canonical history yet | Independent daily collector and typed normalization. Store only returned aggregate views; do not infer missing buckets. |
| C — high-volume microstructure | Running trades | Complete filtered ticker/session tape for a stable, explicit universe | 1,572 canary prints; existing sessions may be partial | Independent cursor collector with floor/filter/count metadata. A session is complete only when `nextCursor` is absent. Do not choose a permanent floor from the current sample. |
| C — ephemeral microstructure | Orderbook snapshots | Explicit cadence for a future stable universe | Seven canary snapshots | Deferred. No full-market collection in this milestone. |

The **Market Universe** is the complete active/provider-supported IDX stock universe. The
**Microstructure Universe** is a separately named, deterministic subset only if measured
quota economics prove complete running-tape collection infeasible for the Market Universe.
No random or alphabetic quota-exhaustion subset is acceptable.

## Analytical-tool requirements

| Tool | Purpose | Required datasets and fields | Grain | History depth | Completeness / universe | Availability and required action |
| --- | --- | --- | --- | --- | --- | --- |
| Candlestick / Price | Price history and range context | EOD open, high, low, close, previous | ticker/day | At least 260 sessions; longer when available | Continuous Market Universe EOD | **Partially supplied.** Existing charts work for 782 tickers. Use market-wide EOD updates and targeted history backfill for remaining supported names. |
| Volume | Participation/activity context | EOD `volume_shares` | ticker/day | 260+ sessions | Complete EOD session; shares, never lots | **Partially supplied** on the same 782-ticker footprint. Preserve raw shares. |
| Frequency Analyzer | Existing `volume_shares / frequency^3` evidence | EOD raw volume shares and non-negative frequency | ticker/day | Selected chart range; 260+ sessions preferred | Both fields valid; frequency zero yields null | **Partially supplied** wherever EOD is present. No formula change. |
| Foreign Analysis | Daily and cumulative foreign flow | Foreign buy shares, foreign sell shares; derived net | ticker/day | 1D through 260+ sessions | Both sides present for every included date | **Partially supplied** on existing EOD coverage. Continue full-universe EOD collection. |
| Directional Activity / Intensity | Compare aggressor-side transaction activity | Tradebook buy/sell frequency and lots; optionally complete running-trade BUY/SELL prints | ticker/day/bucket or print | Daily plus 20–260 sessions | Tradebook view complete as returned; tape complete if used | **Not yet historically supplied.** Normalize daily tradebook; running tape is optional evidence, never silently substituted when partial. |
| Aggressor Analysis | Analyze buyer/seller initiated executions | Running-trade sequence, time, price, lots/shares, BUY/SELL | execution print | Complete sessions over the selected window | `nextCursor` exhausted for every ticker/session | **Partially supplied canary only.** Use resumable filtered collector and expose completeness. No broker identity exists. |
| Broker Accumulation | Observe repeated broker-side buying | Per-stock broker code, BUY rank, lots/shares, value, average price, top-N scope | ticker/broker/day | Minimum 5/10/20 daily observations; longer preferred | Consistent daily top-N observations; not complete market | **Partially supplied canary only.** Collect broker summary independently for all eligible mapped active tickers if quota supports it. |
| Broker Distribution / Concentration | Observe selling and side concentration | Broker BUY/SELL ranks, lots/shares, value, average price, source top-N | ticker/broker/day | 5/10/20+ sessions | Same top-N scope every day; missing day visible | **Partially supplied canary only.** Same broker daily action. Concentration formulas remain unlocked. |
| Big Matched Transaction | Find materially large executions | Complete filtered running prints: sequence, timestamp, price, lots/shares, aggressor | execution print | Complete session plus historical baselines | Complete filtered tape; explicit floor | **Not sufficiently supplied.** Current canaries are partial. No buyer/seller broker identity may be fabricated. |
| Big Trade Detector | Flag statistically/economically large prints | Complete filtered running prints plus EOD volume/value reference | execution print + ticker/day | Enough complete sessions for median/P95/P99 baselines | Complete tape over baseline and target window | **Not supplied.** Measure floors without locking a threshold; preserve tail distribution. |
| Daily Trade Size Baseline | Estimate normal print-size distribution | Running-trade lots/shares/value for a complete filtered day | execution print | Prefer 60–260 complete sessions | Identical declared collection floor and complete cursors | **Not supplied.** Existing partial sessions cannot define a trustworthy baseline. |
| Large Trade Event | Retain a qualified event and market context | Complete running prints, EOD price/volume/value | execution print | Event day plus surrounding EOD/tape | Complete event session | **Not supplied.** Depends on running-tape continuity. |
| Large Trade Cluster | Detect related large prints over time | Complete running prints with sequence/time/action/price/size | execution print | Complete intraday window and multiple sessions | No missing cursor interval | **Not supplied.** Partial sessions must block calculation. |
| Orderbook Imbalance | Compare resting bid/ask liquidity | Timestamped bid/ask levels, price, lots, ranks | ticker/snapshot/level | Intraday cadence defined by future design | Consistent snapshot cadence, not one-off canaries | **Not supplied.** Documented only; full-market collection deferred. |
| Liquidity Pressure | Observe changes in resting liquidity | Repeated orderbook snapshots plus executions for interpretation | ticker/snapshot/level | Intraday sequence | Complete declared cadence | **Not supplied.** Requires a separate quota/storage design. |
| Absorption | Study executions against persistent/restored depth | Orderbook sequence plus complete execution tape | snapshot + execution | Synchronized intraday window | Both feeds complete enough for chosen method | **Not supplied.** No formula is asserted. |
| Foreign Accumulation / Influence | Study persistent foreign participation | Daily foreign buy/sell/net shares, EOD price/volume/value | ticker/day | 5/10/20/60/260 sessions | Continuous EOD foreign history | **Partially supplied.** Extend Market Universe continuity; do not invent monetary or influence fields. |
| Accumulation / Distribution Evidence | Combine independent participation evidence | EOD price/volume/frequency, foreign, broker daily, tradebook; tape only when complete | ticker/day plus optional intraday | 20–260 daily sessions | Each component reports presence/completeness separately | **Partially supplied.** EOD exists; broker/tradebook continuity does not. Formula remains unlocked. |
| Big Money Accumulation Model | Future multi-evidence research model | EOD, foreign, broker, tradebook, complete filtered tape where used; non-regular separately | mixed, summarized to ticker/day | Longitudinal 20–260+ sessions | Evidence-component availability must be exposed | **Not supplied.** Build source histories first; no scoring formula in this milestone. |
| Dryness / Supply Scarcity | Future study of declining availability/activity | EOD volume/value/frequency, tradeable/listed-share context; possibly orderbook later | ticker/day | 20–260+ sessions | Continuous EOD; metadata semantics explicit | **Partially supplied.** EOD exists; durable share metadata and any final formula remain unresolved. |

## Endpoint selection and limitations

| Endpoint | Selected use | Scope / pagination / request cost | Limitation |
| --- | --- | --- | --- |
| `finance:idx/stock-summary` | Ordinary market-wide EOD update | Market-wide, `length` up to 5,000; one request for 963 observed rows | No explicit response `unit`; row fields require strict validation. One malformed row must not reject valid rows. |
| `finance:idx/stock-history` | Backfill, targeted reconciliation, revision repair | Per ticker, up to 2,000 sessions; one request per ticker/range | Does not supply observed non-regular fields. Optional `unit` must equal exactly `shares`. |
| `finance:idx/foreign-flow` | Optional market-wide foreign reconciliation/ranking | Market-wide, paginated up to 200 rows/page | Duplicates canonical buy/sell share facts already present in EOD; not selected for ordinary persistence. |
| `finance:idx/securities` | Active Market Universe discovery | Market-wide, up to 1,000 rows/page | No explicit active/delisted flag; complete successful membership is treated as active. |
| `finance:pluang/resolve` | Optional mapping canary/cache | Per ticker; one request | Not required before canonical ticker calls. Existing 962 mappings remain. |
| `finance:pluang/broker-summary` | Daily per-stock top-N broker flow | Per ticker/range; one request; no cursor | `capped=true` is top-N coverage, not complete broker flow. Historical retention depth remains provider-dependent. |
| `finance:pluang/tradebook` | Daily aggregate structure | Per ticker and tab; one request per requested view | Live `ALL` returned price/time arrays but an empty volume array; `VOLUME` was also empty for the sample. Persist returned facts only. |
| `finance:pluang/running-trades` | Filtered execution tape | Per ticker, opaque cursor; `minLot`, `action`, `cursor`; one request per page | No broker identity. Filtered samples still retained `nextCursor` after four pages. |
| `finance:pluang/orderbook` | Future explicitly scheduled snapshots | Per ticker; one request/snapshot | Ephemeral resting liquidity, not executed flow. Deferred from mass collection. |
| `finance:pluang/tradebook` future formula use | Frequency/size-structure research input | Aggregated price/time/volume views | It does not replace execution-level tape for event sequencing or print distributions. |

`finance:idx/broker-summary` is deliberately not selected for per-stock broker analytics: it
is market-wide broker activity without a ticker or BUY/SELL side.

## Bounded live measurements

On 2026-08-23, one `stock-summary` request returned 963 rows for 2026-08-21. BBCA, BBRI,
BMRI, TLKM, ANTM, and AADI matched stored `stock-history` values for date, OHLC, previous,
volume, value, frequency, and foreign buy/sell. Non-regular fields were present in the
summary and absent from the existing canonical rows.

Running-trade first-page observations used reference closes from the validated 2026-08-21
EOD snapshot. Candidate IDR floors were translated with
`ceil(min_trade_value_idr / (reference_price * 100))`. They are experimental collection
filters, not Big Money classifications.

| Ticker profile | Candidate floor | minLot | First-page rows | Unfiltered first-page rows | First-page retention | Four-page state |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| BBCA — very liquid large cap | IDR 10m | 16 | 147 | 341 | 43.1% | partial; cursor remains; 366 sampled rows |
| ANTM — medium-price active | IDR 10m | 32 | 69 | 226 | 30.5% | partial; cursor remains; 257 sampled rows |
| AADI — lower-activity sample | IDR 10m | 11 | 35 | 110 | 31.8% | partial; cursor remains; 170 sampled rows |

Lower candidate floors of IDR 1m and IDR 5m retained more rows, and every sampled response
still exposed a continuation cursor. These measurements prove that `minLot` reduces returned
rows but do not prove a proportional reduction in requests. No permanent floor is approved.

| Ticker | Floor | Returned / unfiltered first page | Retained | Lot median / P95 / P99 | Trade-value median / P95 / P99 (IDR) |
| --- | ---: | ---: | ---: | --- | --- |
| BBCA | none | 341 / 341 | 341 | 12 / 290 / 2,500 | 7.74m / 187.05m / 1.6125b |
| BBCA | 1m / 5m / 10m | 301 / 215 / 147 (88.3% / 63.0% / 43.1%) | 301 / 215 / 147 | at 10m: 65 / 759 / 6,100 | at 10m: 41.925m / 487.6575m / 3.9345b |
| ANTM | none | 226 / 226 | 226 | 10 / 670 / 1,412 | 3.17m / 212.39m / 447.604m |
| ANTM | 1m / 5m / 10m | 151 / 97 / 69 (66.8% / 42.9% / 30.5%) | 151 / 97 / 69 | at 10m: 114 / 1,353 / 2,500 | at 10m: 36.138m / 428.901m / 792.5m |
| AADI | none | 110 / 110 | 110 | 5 / 75 / 151 | 4.9125m / 73.5m / 148.735m |
| AADI | 1m / 5m / 10m | 84 / 49 / 35 (76.4% / 44.5% / 31.8%) | 84 / 49 / 35 | at 10m: 21 / 151 / 873 | at 10m: 20.6325m / 148.735m / 859.905m |

These are bounded returned-page distributions, not whole-session distributions. Because all
samples remained paginated, they are insufficient to approve a permanent research baseline.

## Request economics and validation gate

Let `U` be eligible tickers and `P` be observed completed cursor pages per ticker/day:

- `stock-summary`: 1 request/day and about 22 requests/month (22 trading days), independent
  of `U` up to the documented response limit.
- `broker-summary`: `U` requests/day and about `22U` requests/month.
- `tradebook`: at least `U` requests/day for `ALL`; additional tabs increase cost. Current
  evidence does not justify a second request solely for an empty volume view.
- `running-trades`: `P * U` requests/day. The bounded sample only establishes `P > 4`, so
  complete-market feasibility is **unknown**, not unlimited and not approved.

| Universe | Broker/day | Broker/month | Tradebook/day (one view) | Tradebook/month | Running/day lower bound (`P > 4`) | Running/month lower bound |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 962 / all current active | 962 | 21,164 | 962 | 21,164 | at least 4,810 | at least 105,820 |
| 500 | 500 | 11,000 | 500 | 11,000 | at least 2,500 | at least 55,000 |
| 250 | 250 | 5,500 | 250 | 5,500 | at least 1,250 | at least 27,500 |
| 100 | 100 | 2,200 | 100 | 2,200 | at least 500 | at least 11,000 |
| 50 | 50 | 1,100 | 50 | 1,100 | at least 250 | at least 5,500 |

Broker and tradebook also share the Zapi monthly allowance with EOD and all other namespaces.
Therefore full-universe daily broker plus tradebook (about 42,328 requests/month before
retries or tape) is not supported by the observed remaining monthly allowance of 23,881.
No mass run is authorized. A full-universe dry-run must recompute current quota, eligible
coverage, and these costs before every expansion.

For complete filtered running tape, all-stock, 500-stock, and 250-stock coverage are already
infeasible under the observed allowance on the measured integer lower bound alone. The
100-stock and 50-stock lower bounds fit in isolation, but feasibility is **not yet proven**:
no sample exhausted, actual pages per completed session are unknown, and broker/tradebook/EOD
share the same allowance. Consequently this milestone does not lock a Microstructure
Universe. The next gate must complete representative sessions first, then choose the largest
stable deterministic universe supported by the measured completed-page cost.

## Downstream completeness contract

For cursor/high-volume sources, trust requires a ticker, dataset, session date, declared
filter/floor, fetched and retained counts, cursor/high-water state, status, and update time.
Only `complete` means provider exhaustion was observed. `partial`, `failed`, and `blocked`
remain visible and must prevent analytics that require a complete tape. Provider failure
never deletes last-valid PostgreSQL facts.
