## What and why

Stacked on the vector pool PR (`perf/vector-pool-python`): this PR's own commits start at "Build the release wheels with profile-guided
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

## Checks

- [x] `uv run pytest` and `cargo test` pass
- [x] `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `ruff check .` and `ruff format --check .` are clean
- [x] An engine fix has a regression test citing the Lua lines; refrozen fixtures (if any) are listed above with the reason: no engine change
- [x] A change of the masks or the action types bumps `ACTION_VERSION`: masks and action types unchanged
- [x] A change users see has a line under "Unreleased" in CHANGELOG.md
