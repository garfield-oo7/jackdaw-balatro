## What and why

Stacked on the engine speed-ups PR (`perf/engine-speedups`): review that first; this PR's own commits start at "Step the vector env on its own
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

## Checks

- [x] `uv run pytest` and `cargo test` pass
- [x] `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `ruff check .` and `ruff format --check .` are clean
- [x] An engine fix has a regression test citing the Lua lines; refrozen fixtures (if any) are listed above with the reason: no engine change
- [x] A change of the masks or the action types bumps `ACTION_VERSION`: masks and action types unchanged
- [x] A change users see has a line under "Unreleased" in CHANGELOG.md
