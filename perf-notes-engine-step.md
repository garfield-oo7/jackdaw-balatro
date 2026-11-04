# Perf notes: engine step path and the env's action table

Branch `perf/wip-engine-step`, based on upstream `dev` 06b1ada. Scope: `crates/jackdaw-core` per-step
path (event queue, `run_event`, `flow.rs`, `area.rs`, scoring, hand evaluation) and
`crates/jackdaw-env/src/gym.rs` / `mask.rs`. Not covered here: the vector env and Python bindings,
`Game::new_run` and the observation encoder.

## Method

- Instruction counts (Ir) with callgrind on the `profiling` build of the `rollout` example:
  `rollout 40000` (random policy) and `rollout 20000 --deep`.
- `--deep`: the benchmark's heuristic (it materialises the whole action table with
  `ActionTable::actions()` and scores every play) is 54% of the run's instructions. To see the
  env's own cost, `--deep` runs use a scratch copy of the example with `#[inline(never)]` on
  `heuristic`, and the figure quoted is "env-only" = total Ir minus the heuristic's inclusive Ir.
  (Without that, a change anywhere can shift register allocation inside the inlined heuristic by
  several million Ir either way.)
- Each idea is measured alone against the base (not stacked).
- callgrind counts each iteration of `rep stos/movs`, so memset/memcpy differences are not
  quoted as wins.
- Wall clock: release `rollout 300000` and `rollout 200000 --deep`, binaries run interleaved
  (order alternating each round), medians of 7 runs, on a 4-core machine shared with two other
  benchmarking engineers (noisy, about +-10%).
- Parity: `rollout 300000 --verify` must print `1d7a46c86f811c53` and
  `rollout 200000 --verify --deep` must print `df57b9920117639a`.

Base Ir: random 1,153,398,836; deep env-only 671,407,972 (total 1,471,649,445, heuristic
800,241,473).

## Kept

| idea | random Ir | deep env-only Ir | status |
|---|---|---|---|
| parse-highlighted: skip hand evaluation when the blind can't read the hand | 1,131,334,660 (-1.91%) | 670,212,212 (-0.18%) | kept |
| queue-inline: `#[inline(always)]` on `Game::queue` | 1,136,285,458 (-1.48%) | 659,632,092 (-1.75%) | kept (binary +4%) |
| draw-next: `draw_cards_flipped` takes the next cards as a run (truncate/drain, no flag array, no retain) | 1,139,007,251 (-1.25%) | 664,015,906 (-1.10%) | kept |
| sort-hand: insertion sort of the hand on its keys | 1,140,243,200 (-1.14%) | 666,490,703 (-0.73%) | kept |
| hand-eval: one pass for the x-of-a-kind groups, derived `Default` for `Group` | 1,141,192,754 (-1.06%) | 667,296,657 (-0.61%) | kept |
| combo-cache: legal-card bits once per table, last-slot memo | 1,148,523,423 (-0.42%) | 669,711,077 (-0.25%) | kept |

All six together: parity hashes unchanged, `cargo test --workspace --exclude jackdaw-py`,
clippy `-D warnings` and `cargo fmt --check` pass.

## Rejected

| idea | numbers | why |
|---|---|---|
| `#[inline]` (hint only) on `Game::queue` | random 1,153,400,189 (+0.00%) | LTO ignores the hint |
| `draw_cards_flipped` taken-set as a `[u64; 4]` bitset instead of `[bool; 256]` | random +1.3M Ir vs the bool version | slower |
| `#[inline]` on `evaluate_poker_hand` (avoid the `PokerHands` copy) | random -0.5M Ir more | not worth it |
| micro-optimising `subsample_bits` | its loop is ~37 instructions per Floyd draw, the draws are fixed by parity | nothing to gain |
| faster `ActionTable::actions()` | 13% of `--deep` Ir, but only the benchmark heuristic and the Python `action_table()` call it; the env steps through `get()` | benchmark cost, not env cost |

## Open ideas (not done)

- `Areas::shuffle`'s pre-sort by sort id (about 1% of random Ir): a scan of `by_sort` would do it
  in O(max sort id); needs a guard for runs with many created cards.
- A `DrawCard` run as one event (about 2% of random Ir in queueing and popping draws): a larger
  change to the queue's shape.
