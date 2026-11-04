# Perf notes: vector env and Python bindings

Base: `upstream/dev` 06b1ada. Machine: 4 cores, shared with two other benchmarking sessions
(load average 3-7 during the measurements), so wall-clock numbers are noisy; deterministic
measures (callgrind Ir, cProfile call counts) come first.

Methods:
- Ir: `valgrind --tool=callgrind` on the whole Python process, `BalatroVectorEnv(64,
  num_threads=1, copy=False)`, random legal actions, `OPENBLAS_NUM_THREADS=1 PYTHONHASHSEED=0`;
  Ir(200 warmup + 400 steps) - Ir(200 warmup + 100 steps) = 300 steps, so start-up cancels.
- Wall clock, in-process: the patched build, a fused env and a two-call env (same build,
  `set_autoreset(None)`) and a NEXT_STEP env stepped in alternating blocks; median of the paired
  per-block ratios (300-400 blocks).
- Wall clock, cross-build: base and patched wheels run alternately, 7-11 runs each, median.

## 1. SAME_STEP autoreset in one call to `_core` (kept)

What: with `autoreset_mode=SAME_STEP` and one back and one stake per sub-env (the default),
`_core.VectorEnv.step(..., final_obs=, episode_counts=)` steps every env and, for an env whose
episode ended, writes its last observation to `final_obs` and resets it on the seed
`f"{seed_prefix}_{count}"` (prefix and back/stake registered once with `set_autoreset`) in the
same pool pass. Before: `step`, then a second pool dispatch through `reset_some`, with a Python
`_reset_tuple` per ended env. Several backs or stakes (drawn with `random.choice`) keep the
two-call path, so Python's RNG draws are unchanged.

Numbers:
- Ir (threads=1, 300 steps, n=64): SAME_STEP 700.0M -> 689.3M (-1.5%); NEXT_STEP 587.4M ->
  588.1M (+0.12%: kwargs parsing, one extra Python attribute test).
- cProfile (n=64, 3000 steps): function calls 203,752 -> 113,952; `_core` calls per step 2 -> 1
  (`reset_some` gone: it took 58 us/call uncontended, ~7 resets per call); `_reset_tuple` calls
  20,950 -> 0.
- In-process paired A/B, threads=4, under contention: n=16 x1.13-1.18, n=64 x1.08-1.11,
  n=256 x1.04-1.12; threads=1 n=64 x1.01-1.03 (one outlier run at load 6.7: n=16 x0.88).
- Cross-build medians, threads=4: n=64 245k -> 272k and 166k -> 182k env-steps/s; n=16
  178k -> 243k and 173k -> 189k (NEXT_STEP, unchanged code path, moved +14% in the same
  session: the noise level).
- Fused SAME_STEP is now 0.72-0.80 of NEXT_STEP's env-steps/s (two-call: 0.63-0.74). The rest
  is inherent: SAME_STEP steps every env every step (NEXT_STEP spends ~11% of its env-steps on
  resets at this episode length) and builds `info["final_obs"]` (~16 us/step for 7 ended envs).

Parity: rollout hashes unchanged (1d7a46c86f811c53, --deep df57b9920117639a); the frozen
SAME_STEP digest `c257fdfba478b4ed` in tests/env/test_env_outputs.py passes on the fused path;
new tests compare fused and two-call runs byte for byte (Rust: `a_fused_autoreset_is_a_step_
then_a_reset`, threads 1 and 4; Python: `test_a_same_step_autoreset_in_one_call_is_a_step_then
_a_reset`, threads 1 and 3, with partial and full resets in between).

Also fixed: a negative action for a sub-env that resets on the step raised IndexError (the docs
say its action is ignored).

## Rejected

- `for_each_home`'s per-step `Vec<Mutex<Option<T>>>`, bounds and counters, and the per-item
  Mutex: Rust `vector` example, 64 envs, threads=1, 1000 steps: vector.rs's own lines ~2.5M Ir
  and the Mutex lock/unlock 0.26M Ir (4 Ir per item) of 1,728M total (0.16%). Not worth it.
- `actions.to_vec` in `_core.VectorEnv.step`: 64 int64 copied; the whole argument conversion
  with 0 resets is 0.67 us per call. Not measurable.
- Faster `info["final_obs"]` construction (structured-dtype views, column lists): 15.3-17.2 us
  vs 15.7 us for 7 ended envs. No gain.
- NEXT_STEP pending resets from the registered starts (no Python reset tuples): would save
  `_reset_tuple` x7 = 3.6 us plus PyO3 extraction of 7 tuples = 1.1 us per step at n=64 (~3% of
  an uncontended step), for another `_core` kwarg. Not done; a possible follow-up.
- `copy=True` costs ~10 us/step at n=64 over `copy=False` (fresh arrays and views): inherent to
  the copy semantics.
