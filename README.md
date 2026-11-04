<div align="center">
  <h1>Jackdaw</h1>
  <div><img src="docs/jackdaw.png" alt="Jackdaw Logo" width="300" height="300"/></div>
  <br/>
  <a href="https://tylerflar.github.io/jackdaw-balatro/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue" alt="Documentation"/></a>
</div>

---

> [!NOTE]
> **Fork notes (garfield-oo7/jackdaw-balatro only; not for upstream).** The section below tracks
> performance work in progress on this fork. Leave it out of any pull request to upstream, like
> AGENTS.md and CLAUDE.md.

## Fork: performance work in progress

Three branches on this fork, each started from upstream `dev` (`06b1ada`), make the engine and
the envs faster without changing the game. None is ready for upstream yet: see
[Before an upstream pull request](#before-an-upstream-pull-request).

| Branch | Tip | What it does |
|---|---|---|
| `perf/wip-vector-env` | `11652a1` | `BalatroVectorEnv` in `SAME_STEP` mode resets an ended episode in the same engine call as the step (one call instead of two); a sub-env that resets ignores its action, even a negative one |
| `perf/wip-reset-obs` | `9c3a4b5` | Five changes to starting a run (deck copy, RNG hashing and arithmetic, the round's card picks, one observation division) and a `resets` benchmark example |
| `perf/wip-engine-step` | `d7d0391` | Seven changes to the step path (hand evaluation on highlight, card draws, hand sort, pair/three/four grouping, action-table cache, shuffle, an inlined event queue) |
| `fix/seeded-episode-starts` | `2512a30` | With several `back_keys` or `stakes`, the back and stake come from the episode's seed, so `reset(seed=s)` always starts the same run |

Each perf branch has a `perf-notes-*.md` at its root listing every idea tried, its numbers, and
the ones rejected and why.

### Measured gains

Rust benchmarks, pinned to one core (`taskset -c 3`), 20 interleaved rounds, medians, quiet
4-core machine:

| Variant | Random-policy step | `--deep` step | Reset |
|---|---|---|---|
| Base (upstream `dev`) | 3.575 µs | 9.634 µs | 6.905 µs |
| `perf/wip-reset-obs` | −5.6% | −3.0% | −22.5% |
| `perf/wip-engine-step` | −10.9% | −2.5% | no change |
| All three combined | −16.7% | −7.6% | −19.7% |

`BalatroVectorEnv` `SAME_STEP`, one call against two in the same process, 600 alternating
blocks, 4 threads: +17% env-steps/s at 16 envs, +10% at 64, +12% at 256 (the middle half of the
paired ratios lies above 1 at every size). `NEXT_STEP` is unchanged.

Instruction counts (callgrind), which have no run-to-run noise, agree: the reset branch executes
18.6% fewer instructions per reset, and the engine branch 7.8% fewer per random-policy step.

Single commits can't be told apart in wall-clock time (each saves 1-3%; runs vary by 5-8%). Two
are unproven: force-inlining `Game::queue` (`5a8a8d5`) and the action table's legal-card cache
(`44c4bc8`) make the random step 3-5 points faster but `--deep` slightly slower.

### Before an upstream pull request

From a review of all three branches (no parity problem found; the three merge cleanly, and the
merge passes both hashes, `cargo test`, `uv run pytest`, clippy and ruff):

1. **`perf/wip-vector-env`**
   - **Blocking:** `_core.VectorEnv.set_autoreset` checks only that the back exists. It must
     validate each start as a new run does (the back is a deck, the stake is 1-8, the challenge
     is valid). Today a stake of 9 fails in the middle of a step, after other envs have stepped,
     leaving an env ended and not reset. `BalatroVectorEnv` can't reach this; direct `_core`
     callers (Jackdaw Arena) can.
   - Correct the doc of `VectorEnv::step_autoreset`: a failed reset fails after the envs stepped.
   - Raise an episode-count overflow as `ValueError` or `OverflowError`, not `IndexError`.
   - Move the negative-action fix into its own commit (or its own pull request).
   - Run the Python fused-vs-two-call equivalence test with `copy=True` too.
2. **`perf/wip-reset-obs`**: reword the message of `80459e9` (the code falls back to
   `lua::floor` for any value outside (0, 2^52), not only "positive" ones). The integer division
   (`60be13f`) is optional: too small to measure.
3. **`perf/wip-engine-step`**: correct the messages of `c71e14a` (on equal keys the old fast path
   put the card before its equals) and `57509f6` (measured against `44c4bc8`, not `06b1ada`; drop
   its `resets` claim). Drop `5a8a8d5` and `44c4bc8` unless a measurement shows a gain.
4. **All three**: rebuild each branch from upstream `dev` without its `perf-notes-*.md`, add a
   CHANGELOG line, and re-measure every number in the pull request on that branch against `dev`
   (AGENTS.md). One pull request per branch.

### Checking parity

On every branch, before every commit:

```bash
cargo run --release -p jackdaw-env --example rollout 300000 --verify          # 1d7a46c86f811c53
cargo run --release -p jackdaw-env --example rollout 200000 --verify --deep   # df57b9920117639a
cargo run --release -p jackdaw-env --example resets 20000 --verify            # 16704def8fcaca77 (where the example exists)
```

Then `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`,
`cargo test --workspace --exclude jackdaw-py`, `uv run pytest` and `ruff check .`.

### Measuring without noise

A single timing run on a shared machine varies by 5-8%, more than most single changes save.

- Use instruction counts as the first evidence: build with `cargo build --profile profiling -p
  jackdaw-env --example rollout`, then run `valgrind --tool=callgrind` on it. Callgrind counts
  `rep stos`/`rep movs` once per iteration, so `memset`/`memcpy` look larger than they are.
- For wall-clock time, pin each run to one core (`taskset -c 3`), interleave base and change
  (rotate the order each round), take at least 20 rounds, and compare medians and the middle
  half of the runs. Run nothing else meanwhile.
- `--deep` includes the benchmark's own heuristic (about half its time), so it understates
  env-side gains.
- For the vector env, compare variants in one process in alternating blocks (paired ratios);
  separate processes vary too much.

---

Jackdaw is a Balatro simulator built for RL research: a bit-exact Balatro 1.0.1o engine written in Rust with a Python interface, Gymnasium-style environments (single and vectorized) with entity-based observations and a factored action space, and a bridge that plays live Balatro in lockstep through [BalatroBot](https://github.com/coder/balatrobot).

## Motivation

With [BalatroBot](https://github.com/coder/balatrobot) already existing, why build a separate simulator?

BalatroBot drives the real game, which runs at the game's speed and can race or crash when pushed. RL training needs many fast, parallel environments: one jackdaw environment steps about 180,000 times a second, and `BalatroVectorEnv` over a million times a second on 8 threads. And the Python API exposes every part of the game, with read-only views, snapshots, exact score previews and a state builder, which helps with debugging and research. See the [Python API](https://tylerflar.github.io/jackdaw-balatro/api).

The engine follows the game's Lua source function by function, down to the RNG. It was checked step by step against a Python reference engine, against LuaJIT for the RNG and hand evaluation, and in lockstep against the live game: 200 organic games and every validation scenario without an unexplained difference.

## Install

### Add to your project

```bash
uv add git+https://github.com/TylerFlar/jackdaw-balatro.git --branch main   # the latest release
uv add git+https://github.com/TylerFlar/jackdaw-balatro.git --tag v0.2.0    # a given release
```

`main` holds the releases; the default branch, `dev`, is the work toward the next one. Installing from git compiles the Rust engine, so it needs a Rust toolchain ([rustup](https://rustup.rs)). The [releases](https://github.com/TylerFlar/jackdaw-balatro/releases) also have prebuilt wheels for Linux, macOS and Windows (CPython 3.12+), which don't.

### For development

```bash
git clone https://github.com/TylerFlar/jackdaw-balatro
cd jackdaw-balatro
uv sync --dev
```

`uv sync` builds the `jackdaw._core` extension with maturin. See [development](https://tylerflar.github.io/jackdaw-balatro/development) for the toolchain and [CONTRIBUTING.md](CONTRIBUTING.md) for the branch flow.

## Quick Start

```python
from jackdaw.env import BalatroEnvironment, DirectAdapter

env = BalatroEnvironment(adapter_factory=DirectAdapter)
obs, mask, info = env.reset()

terminated = truncated = False
while not (terminated or truncated):
    action = your_model.act(obs, mask)
    obs, terminated, truncated, mask, info = env.step(action)
```

## Gymnasium Wrapper

`BalatroGymnasiumEnv` exposes the game as a flat `Discrete(500)` action space with an `action_masks()` method, so it works with action-masking RL libraries such as sb3-contrib's MaskablePPO. `BalatroVectorEnv` steps many of them at once in Rust. Jackdaw doesn't depend on any RL library; install the one you use in your own project.

[`examples/`](examples) has a complete MaskablePPO demo: training with TensorBoard logs and checkpoints, an evaluation against a random agent and the hand-written `smart_agent`, and its results. Its dependencies are the `train` dependency group (`uv sync --group train`), which isn't part of the package.

See the [RL Project Guide](https://tylerflar.github.io/jackdaw-balatro/rl-guide) for the observations, actions, rewards and environments.

## Jackdaw Arena

[Jackdaw Arena](https://arena.tylerflar.com) is a hosted, verifiable benchmark for agents trained on jackdaw. Your agent plays over HTTPS on seeds the server picks and keeps secret until each episode ends. Every episode counts against a fixed budget (500 on `red-1`, the protocol of [`examples/`](examples)), and every result is verified by replay, then published with its seed and tape. Its client provides `ArenaEnv`, a drop-in for `BalatroGymnasiumEnv`, and an `evaluate()` that takes the examples' chooser signature. See [Evaluating on Jackdaw Arena](https://tylerflar.github.io/jackdaw-balatro/arena).

## Live Validation

Swap the adapter to play against real Balatro via [BalatroBot](https://github.com/coder/balatrobot) — the interface is identical. `LiveAdapter` keeps a shadow run in the simulator, checks every live answer against it, and takes observations and masks from it, so an agent sees exactly what it saw in training:

```python
from jackdaw.bridge import LiveAdapter, LiveBackend
from jackdaw.env import BalatroEnvironment

env = BalatroEnvironment(
    adapter_factory=lambda: LiveAdapter(LiveBackend("127.0.0.1", 12346))
)
# Same obs and actions; the mask only offers what BalatroBot can execute
```

`jackdaw lockstep` plays organic games on one or more BalatroBot instances this way and writes a repro bundle for every divergence; `jackdaw lockstep replay` reruns one on the simulator. See [Lockstep against the live game](https://tylerflar.github.io/jackdaw-balatro/live).

## Architecture

```
crates/
  jackdaw-core/     The engine: Lua numerics and RNG, cards, scoring, every joker,
                    consumable, tag, voucher, boss, deck and challenge rule, snapshots
  jackdaw-data/     Generated tables (centers, blinds, tags, hands...) from the game's prototypes
  jackdaw-env/      Observation encoder, action masks, Gym enumeration, vector env, rewards
  jackdaw-bot/      BalatroBot v1.5.2's API: view, endpoints, validator, `jackdaw serve`
  jackdaw-py/       The PyO3 extension, jackdaw._core

jackdaw/
  core/             The Python API: Game, read-only views, GameBuilder
  engine/           The action types and the game's data tables (codegen input)
  env/              BalatroEnvironment, BalatroGymnasiumEnv, BalatroVectorEnv, rewards, agents
  bridge/           BalatroBot backends; LiveAdapter, the deviation catalog, lockstep
  cli/              The jackdaw command and its validation scenarios
```

## CLI

```bash
jackdaw validate                            # all validation scenarios against live Balatro
jackdaw validate --category jokers          # joker scenarios only
jackdaw validate --scenario joker_jolly     # one scenario
jackdaw lockstep --instances 4 --seeds 200  # organic games on 4 BalatroBot instances
jackdaw lockstep replay BUNDLE              # rerun a divergence on the simulator
jackdaw serve                               # BalatroBot's API on the simulator
```

> One of the biggest ways to contribute is by writing validation scenarios! See the [validation docs](https://tylerflar.github.io/jackdaw-balatro/validation) to get started.

## Development

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) and Rust.

```bash
uv sync --dev          # install with dev dependencies (builds the Rust extension)
uv run pytest          # Python tests
cargo test             # Rust tests
uv run pytest -m benchmark   # performance benchmarks
uv run pytest -m live        # against live Balatro (needs BalatroBot)
uv run pytest -m lockstep    # long sim-against-sim lockstep runs over jackdaw serve
uv run ruff check . && uv run ruff format --check .
```

Pull requests go to the `dev` branch; `main` holds the releases. See [CONTRIBUTING.md](CONTRIBUTING.md) and the [changelog](CHANGELOG.md).

## License

MIT
