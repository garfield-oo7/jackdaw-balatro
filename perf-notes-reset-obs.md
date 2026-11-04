# Perf notes: starting a run and the env's observation

Area: `Game::new_run` (RNG seeding, deck, round picks, pools, blind select) and the env's
observation/mask encoding. Base: upstream `dev` 06b1ada. Parity reference hashes:
`rollout 300000 --verify` = `1d7a46c86f811c53`, `rollout 200000 --verify --deep` =
`df57b9920117639a`; the new `resets 20000 --verify` example = `16704def8fcaca77` at base.

## Method

- Ir: callgrind on the profiling build (`cargo build --profile profiling -p jackdaw-env
  --example rollout --example resets`): `resets 5000` (reset + obs + mask, 5000 seeds),
  `rollout 40000` (random policy) and `rollout 20000 --deep`.
- Wall-clock: interleaved A/B (A, B, A, B ...), median of 9-11 runs each, on a shared 4-core
  machine with two other engineers building and benchmarking: noisy, labelled "contended".

Base Ir: resets 5000 = 301,394,369 (60.3K per reset incl. obs/mask); random 40000 =
1,153,398,452; deep 20000 = 1,463,852,753.

## Ideas

Ir deltas below are cumulative steps in the order measured (resets 5000 unless noted);
per-patch numbers against the base are in the commits.

| Idea | Status | Resets Ir | Notes |
|---|---|---|---|
| Deck from template: copy each 352-byte card straight into its slot (collect, then number) | kept | 301.39M -> 279.62M (-7.2%) | The push loop copied each card twice (stack, then heap) |
| Build the `Game` in place in `new_run` | kept (with deck copy) | -1.15M (-0.45%) | One 3 KB move fewer |
| `hash_steps_many`: chains longest first (running ones are a prefix), finiteness checked once at the end, positive-truncation floor; primed keys listed longest first | kept | 279.62M -> 266.36M (-4.7%) | `hash_steps_many` 52.2M -> 38.3M |
| Share the non-Stone candidate bitmap between idol, mail and castle picks | kept | 266.36M -> 256.24M (-3.8%) | Also at every round end. random -3.4% / deep -1.0% cumulative at this point |
| `random_n`/`random_range`: floor of `r*k` as a truncation for k >= 1 | kept | 255.09M -> 250.30M (-1.9%) | shuffles, every element pick |
| `Tw223::seeded`: plain arithmetic unless the seed is NaN | kept | 250.30M -> 247.73M (-1.0%) | |
| `advance`: plain arithmetic while finite | kept | 247.73M -> 245.89M (-0.7%) | |
| `py_floordiv`: integer quotient for whole operands (no `fmod`/`floor` calls) | kept | 245.89M -> 245.43M | random: removes 2 `fmod` calls per step (~5.3M Ir of 1153M) |
| Don't prime the four `_resample` keys | rejected | -12.9M Ir (-5.2%) | but wall-clock +1.2% (11 runs, contended): the primed hashes overlap, a lone one is latency-bound |
| Last-byte pre-check in the primed-key search | rejected | +2.3M | worse |
| `Key::n` integrality without `trunc` | rejected | -0.28M | not worth the diff |
| Reuse the previous Game's allocations | rejected earlier | | allocator ~1.5% of Ir |
| encode_playing_cards tables | not pursued | | divisions already folded into switch tables by LLVM; ~90-137 Ir/card, <1% possible |
| G_RATIO log1p memo | not pursued | | ~0.25% of random |

Combined wall-clock so far (contended, 9 runs each, interleaved): resets 6.672 -> 6.054 us
(-9.3%) after the first three ideas.

Parity on the combined tree: all three verify hashes unchanged;
`cargo test --workspace --exclude jackdaw-py`, clippy `-D warnings`, `cargo fmt --check` pass.
