## What and why

The Rust env steps 1.8 times as fast and `BalatroGymnasiumEnv` 1.25 times, with the same runs,
observations, masks and action tables: the rollout benchmark's `--verify` hashes are unchanged
(`1d7a46c86f811c53` over 300k random steps, `df57b9920117639a` over 200k `--deep` steps).

| | before | after |
|---|---|---|
| Rust env, random policy (steps/s) | 137k | 249k |
| Rust env, `--deep` policy (steps/s) | 81k | 95k |
| `BalatroGymnasiumEnv` (steps/s) | 76k | 96k |
| `BalatroVectorEnv`, 64 envs, 4 threads (env-steps/s) | 138k | 209k |
| new run (µs, `tests/perf.rs`) | 7.59 | 5.65 |
| play 5 cards, no jokers / 5 jokers (µs) | 2.00 / 4.45 | 1.71 / 3.63 |

Cloning a game is a little slower (0.77 → 0.85 µs): the arena copies its slot lists too.

`cargo run --release -p jackdaw-env --example rollout` (new) measures the Rust env; with `--verify`
(and `--deep`) it hashes every observation, mask, action table and reward, and a snapshot every
16 steps.

How:
- **Action table built on read.** Card actions are kept as references to cached selections plus
  the subsample's bitset; a step reads one of ~400. Same draws, same order.
- **Cards stay put.** Areas hold slots into one arena; draws, shuffles and sorts move u32s instead
  of 350-byte cards.
- **New run.** The starting deck is copied from a template when it isn't erratic; the boss pick,
  voucher links and joker checks go by id instead of strings.
- **Observation.** Exact table lookups for `log_scale`, a faster hand analysis checked against the
  original on 200k random areas, and id-indexed tables instead of string lookups; written straight
  into the Gym layout.
- **Smaller engine items.** One sweep over the playing cards, no allocation in the mask's
  consumable check, highlighted cards scored in place, no debuff pass under a blind that debuffs
  nothing, the hand drawn at once when facing can't vary.
- Snapshot import rejects cards that share a sort id, and a `next_sort_id` not above them all.

## Checks

- [x] `uv run pytest` and `cargo test` pass
- [x] `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `ruff check .` and `ruff format --check .` are clean
- [x] An engine fix has a regression test citing the Lua lines; refrozen fixtures (if any) are listed above with the reason: no fixtures refrozen, no rule changes
- [x] A change of the masks or the action types bumps `ACTION_VERSION`: masks and action types unchanged
- [x] A change users see has a line under "Unreleased" in CHANGELOG.md
