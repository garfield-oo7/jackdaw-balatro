# Pull request descriptions

Three stacked pull requests from `garfield-oo7/jackdaw-balatro` into `TylerFlar/jackdaw-balatro:dev`.
Open them in order; PR 2 contains PR 1's commits and PR 3 contains PR 2's, until the earlier ones merge.

All numbers: 4-core VM, interleaved runs of the stages, medians (7 runs for the rollout, 5 for the
others, 3 for the Python vector env). Single-env runs pinned to one core.

---

## PR 1: Faster engine and env, same runs

**Title:** Faster engine and env, same runs

### What and why

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

### Checks

- [x] `uv run pytest` and `cargo test` pass
- [x] `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `ruff check .` and `ruff format --check .` are clean
- [x] An engine fix has a regression test citing the Lua lines; refrozen fixtures (if any) are listed above with the reason: no fixtures refrozen, no rule changes
- [x] A change of the masks or the action types bumps `ACTION_VERSION`: masks and action types unchanged
- [x] A change users see has a line under "Unreleased" in CHANGELOG.md

---

## PR 2: Vector env thread pool, lighter Python wrappers

**Title:** Vector env thread pool, lighter Python wrappers

### What and why

Stacked on #PR1: review that first; this PR's own commits start at "Step the vector env on its own
spinning thread pool".

| | before | after |
|---|---|---|
| `BalatroVectorEnv`, 64 envs, 4 threads (env-steps/s) | 209k | 492k |
| `BalatroVectorEnv`, 64 envs, 4 threads, `copy=False` | 276k | 571k |
| `BalatroVectorEnv`, 256 envs, 4 threads | 364k | 459k |
| Rust vector env, 4 threads, 16 / 64 / 256 envs | 212k / 398k / 502k | 487k / 620k / 693k |
| `BalatroGymnasiumEnv` default / `copy=False` (steps/s) | 96k / — | 110k / 139k |

Results are the same for every thread count, and the `--verify` hashes are unchanged.

How:
- **Own thread pool** instead of rayon's broadcast (10–25 µs per handoff): the calling thread works
  too, idle workers poll briefly, then yield, then park, and a step never waits for a worker that
  hasn't joined it, so more threads than free cores cost little.
- **Python per step:** the vector env's per-env results come from Rust as one record in their final
  dtypes; the Gym env's observation and mask come in one buffer, read as one structured item.
- **`BalatroGymnasiumEnv(copy=False)`** (opt-in): buffers owned by the env, overwritten by the next
  step, as `BalatroVectorEnv(copy=False)`.

What the envs return is unchanged by default (a new test pins every array's values, dtype, shape,
contiguity and writability against digests from the old code).

### Checks

- [x] `uv run pytest` and `cargo test` pass
- [x] `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `ruff check .` and `ruff format --check .` are clean
- [x] An engine fix has a regression test citing the Lua lines; refrozen fixtures (if any) are listed above with the reason: no engine change
- [x] A change of the masks or the action types bumps `ACTION_VERSION`: masks and action types unchanged
- [x] A change users see has a line under "Unreleased" in CHANGELOG.md

---

## PR 3: PGO release wheels

**Title:** Build the release wheels with profile-guided optimisation

### What and why

Stacked on #PR2: this PR's own commits start at "Build the release wheels with profile-guided
optimisation".

Release wheels for Linux x86_64, macOS arm64 and Windows x64 are built with profile-guided
optimisation. Same outputs: the `--verify` hashes match on the PGO build.

| | before | after |
|---|---|---|
| Rust env, random / `--deep` policy (steps/s) | 240k / 93k | 272k / 106k |
| `BalatroGymnasiumEnv` default / `copy=False` (steps/s) | 110k / 139k | 128k / 181k |
| `BalatroVectorEnv`, 64 envs, 4 threads (env-steps/s) | 492k | 604k |
| Rust vector env, 256 envs, 4 threads | 693k | 853k |

How: build an instrumented wheel, run `scripts/pgo_workload.py` (Gym env, vector env, both
autoreset modes, `copy=False`) and the rollout benchmark with it, merge the profiles with
`llvm-profdata`, build the release wheel with `-Cprofile-use`. No target-cpu flags: the wheels stay
portable. Cross-compiled targets (Linux aarch64, macOS x86_64) keep the plain build.
`scripts/pgo.sh build` runs the same pipeline locally.

The Linux x86_64 PGO pipeline has run end to end; the macOS and Windows legs run on the next
`workflow_dispatch` of the Wheels workflow.

### Checks

- [x] `uv run pytest` and `cargo test` pass
- [x] `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `ruff check .` and `ruff format --check .` are clean
- [x] An engine fix has a regression test citing the Lua lines; refrozen fixtures (if any) are listed above with the reason: no engine change
- [x] A change of the masks or the action types bumps `ACTION_VERSION`: masks and action types unchanged
- [x] A change users see has a line under "Unreleased" in CHANGELOG.md

---

## Overall, upstream `dev` → all three

| | before | after |
|---|---|---|
| Rust env, random policy | 137k | 272k (2.0×) |
| `BalatroGymnasiumEnv` default / `copy=False` | 76k | 128k (1.7×) / 181k (2.4×) |
| `BalatroVectorEnv`, 64 envs, 4 threads | 138k | 604k (4.4×) |
| Rust vector env, 256 envs, 4 threads | 360k | 853k (2.4×) |
