"""The env controls: the cap on free moves in a row, refused actions, the vector env's autoreset
modes and partial resets, and the action space's version."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from gymnasium.vector import AutoresetMode

from jackdaw import _core
from jackdaw.core import IllegalActionError
from jackdaw.env import (
    ACTION_VERSION,
    DEFAULT_MAX_FREE_MOVES,
    FREE_ACTION_TYPES,
    ActionType,
    BalatroEnvironment,
    BalatroGymnasiumEnv,
    BalatroVectorEnv,
    DirectAdapter,
    FactoredAction,
)
from tests.env.generic import GenericAdapter

_ADAPTERS = pytest.mark.parametrize(
    "adapter", [DirectAdapter, GenericAdapter], ids=["direct", "generic"]
)


def _free_in_mask(mask: Any) -> bool:
    return any(bool(mask.type_mask[t]) for t in FREE_ACTION_TYPES)


def _free_in_table(env: BalatroGymnasiumEnv) -> bool:
    return any(a.action_type in FREE_ACTION_TYPES for a in env._action_table)


# ---------------------------------------------------------------------------
# The free-move cap
# ---------------------------------------------------------------------------


def test_the_default_cap() -> None:
    assert DEFAULT_MAX_FREE_MOVES == 10
    assert BalatroEnvironment(DirectAdapter).max_free_moves == DEFAULT_MAX_FREE_MOVES
    assert BalatroGymnasiumEnv(DirectAdapter).max_free_moves == DEFAULT_MAX_FREE_MOVES
    assert BalatroVectorEnv(1).max_free_moves == DEFAULT_MAX_FREE_MOVES
    assert {t.name for t in FREE_ACTION_TYPES} == {
        "SwapJokersLeft",
        "SwapJokersRight",
        "SwapHandLeft",
        "SwapHandRight",
        "SortHandRank",
        "SortHandSuit",
    }


@_ADAPTERS
def test_balatro_environment_caps_free_moves(adapter: type) -> None:
    env = BalatroEnvironment(adapter_factory=adapter, max_free_moves=3)
    env.reset(seed="CAP")
    _, _, _, mask, _ = env.step(FactoredAction(ActionType.SelectBlind))
    for _ in range(3):
        assert _free_in_mask(mask)
        _, _, _, mask, _ = env.step(FactoredAction(ActionType.SortHandSuit))
    assert not _free_in_mask(mask), "three free moves in a row: none more"
    assert mask.type_mask[ActionType.PlayHand]
    _, _, _, mask, _ = env.step(FactoredAction(ActionType.Discard, card_target=(0,)))
    assert _free_in_mask(mask), "another action starts the count again"


def test_no_cap() -> None:
    env = BalatroEnvironment(adapter_factory=DirectAdapter, max_free_moves=None)
    env.reset(seed="NOCAP")
    _, _, _, mask, _ = env.step(FactoredAction(ActionType.SelectBlind))
    for _ in range(50):
        _, _, _, mask, _ = env.step(FactoredAction(ActionType.SortHandRank))
    assert _free_in_mask(mask)


def _prefer_free(rng: np.random.Generator) -> Callable[[BalatroGymnasiumEnv], int]:
    """A policy that takes a free move whenever the table has one (so it reaches the cap)."""

    def pick(env: BalatroGymnasiumEnv) -> int:
        table = list(env._action_table)
        free = [i for i, a in enumerate(table) if a.action_type in FREE_ACTION_TYPES]
        pool = free if free and rng.random() < 0.9 else list(range(len(table)))
        return int(rng.choice(pool))

    return pick


def test_both_gym_paths_cap_alike() -> None:
    """The Rust Gym env and the generic path (BalatroEnvironment's mask, the Python table)
    apply the cap the same way."""
    rust = BalatroGymnasiumEnv(DirectAdapter, seed_prefix="CAPEQ", max_free_moves=2)
    generic = BalatroGymnasiumEnv(GenericAdapter, seed_prefix="CAPEQ", max_free_moves=2)
    pick = _prefer_free(np.random.default_rng(5))
    rust.reset(seed=4)
    generic.reset(seed=4)
    capped = 0
    for step in range(400):
        assert list(rust._action_table) == list(generic._action_table), f"step {step}"
        if not _free_in_table(rust):
            capped += 1
        action = pick(rust)
        r = rust.step(action)
        g = generic.step(action)
        assert r[1:4] == g[1:4], f"step {step}"
        if r[2] or r[3]:
            rust.reset()
            generic.reset()
    assert capped > 20, "the policy should reach the cap"


def test_the_vector_env_caps_free_moves() -> None:
    vec = BalatroVectorEnv(1, seed_prefix="VCAP", max_free_moves=1)
    _, info = vec.reset(seed=1)
    _, _, _, _, info = vec.step([0])  # SelectBlind
    table = vec.action_table(0)
    sort = next(i for i, a in enumerate(table) if a.action_type == ActionType.SortHandRank)
    _, _, _, _, info = vec.step([sort])
    assert not any(a.action_type in FREE_ACTION_TYPES for a in vec.action_table(0))


# ---------------------------------------------------------------------------
# Refused actions
# ---------------------------------------------------------------------------


class _Refusing(GenericAdapter):
    """Refuses every step, as the engine refuses an action the masks wrongly allowed."""

    def step(self, action: Any) -> Any:
        raise IllegalActionError("pretend")


def test_a_refusal_ends_the_episode() -> None:
    env = BalatroEnvironment(adapter_factory=_Refusing)
    _, _, info = env.reset()
    before = info["game"].state_hash()
    _, terminated, truncated, _, info = env.step(FactoredAction(ActionType.SelectBlind))
    assert (terminated, truncated) == (False, True)
    assert info["refused"] == "pretend"
    assert info["game"].state_hash() == before


def test_a_refusal_can_raise() -> None:
    env = BalatroEnvironment(adapter_factory=_Refusing, on_refusal="raise")
    env.reset()
    with pytest.raises(IllegalActionError):
        env.step(FactoredAction(ActionType.SelectBlind))
    gym = BalatroGymnasiumEnv(_Refusing, on_refusal="raise")
    gym.reset()
    with pytest.raises(IllegalActionError):
        gym.step(0)


def test_the_gym_env_flags_a_refusal() -> None:
    gym = BalatroGymnasiumEnv(_Refusing)
    gym.reset()
    _, _, terminated, truncated, info = gym.step(0)
    assert (terminated, truncated) == (False, True)
    assert info["balatro/refused"] == "pretend"
    assert not info["action_mask"].any()


def test_bad_settings() -> None:
    for make in (BalatroEnvironment, BalatroGymnasiumEnv):
        with pytest.raises(ValueError):
            make(DirectAdapter, on_refusal="ignore")
        with pytest.raises(ValueError):
            make(DirectAdapter, max_free_moves=-1)
    with pytest.raises(ValueError):
        BalatroVectorEnv(1, on_refusal="ignore")
    with pytest.raises(ValueError):
        BalatroVectorEnv(1, autoreset_mode=AutoresetMode.DISABLED)


# ---------------------------------------------------------------------------
# The vector env's autoreset modes and partial resets
# ---------------------------------------------------------------------------


def _same_obs(a: dict[str, np.ndarray], b: dict[str, np.ndarray], where: str) -> None:
    assert list(a) == list(b), where
    for k in a:
        assert a[k].tobytes() == b[k].tobytes(), f"{where}: {k}"


def test_same_step_autoreset_is_the_gym_env() -> None:
    gym = BalatroGymnasiumEnv(DirectAdapter, seed_prefix="SAME_0", reward_shaping=True)
    vec = BalatroVectorEnv(
        1,
        seed_prefix="SAME",
        reward_shaping=True,
        num_threads=1,
        autoreset_mode=AutoresetMode.SAME_STEP,
    )
    assert vec.metadata["autoreset_mode"] is AutoresetMode.SAME_STEP
    rng = np.random.default_rng(2)
    g_obs, g_info = gym.reset(seed=12)
    v_obs, v_info = vec.reset(seed=12)
    episodes = 0
    for pos in range(1500):
        where = f"step {pos}"
        _same_obs(g_obs, {k: v[0] for k, v in v_obs.items()}, where)
        assert g_info["action_mask"].tobytes() == v_info["action_mask"][0].tobytes(), where
        action = int(rng.choice(np.flatnonzero(g_info["action_mask"])))
        g_obs, g_r, g_term, g_trunc, g_info = gym.step(action)
        v_obs, v_r, v_term, v_trunc, v_info = vec.step([action])
        assert (g_r, g_term, g_trunc) == (float(v_r[0]), bool(v_term[0]), bool(v_trunc[0])), where
        if g_term or g_trunc:
            assert v_info["_final_obs"][0]
            _same_obs(g_obs, v_info["final_obs"][0], f"{where} final obs")
            final = v_info["final_info"]
            assert final["_balatro/ante_reached"][0]
            assert g_info["balatro/ante_reached"] == final["balatro/ante_reached"][0]
            assert g_info["balatro/rounds_beaten"] == final["balatro/rounds_beaten"][0]
            # The same step already started the next episode.
            g_obs, g_info = gym.reset()
            episodes += 1
        else:
            assert "final_obs" not in v_info
    assert episodes >= 5


def _two_call_same_step(vec: BalatroVectorEnv) -> BalatroVectorEnv:
    """``vec`` with its same-step autoreset as a ``reset_some`` after each step, as with
    several backs or stakes."""
    vec._core.set_autoreset(None)
    vec._episode_counts = None
    return vec


def _same_step_run(fused: bool, threads: int) -> list[Any]:
    vec = BalatroVectorEnv(
        6,
        seed_prefix="FOLD",
        max_steps=30,
        reward_shaping=True,
        num_threads=threads,
        copy=False,
        autoreset_mode=AutoresetMode.SAME_STEP,
    )
    assert vec._episode_counts is not None
    if not fused:
        _two_call_same_step(vec)
    rng = np.random.default_rng(4)
    seen: list[Any] = []

    def keep(result: tuple[Any, ...]) -> None:
        obs, *rest, info = result
        seen.append(({k: v.copy() for k, v in obs.items()}, [np.copy(r) for r in rest]))
        seen.append(
            {
                k: [None if x is None else {n: a.copy() for n, a in x.items()} for x in v]
                if k == "final_obs"
                else (v.copy() if isinstance(v, np.ndarray) else v)
                for k, v in info.items()
            }
        )

    result: tuple[Any, ...] = vec.reset(seed=5)
    keep(result)
    for pos in range(240):
        actions = [int(rng.choice(np.flatnonzero(m))) for m in result[-1]["action_mask"]]
        result = vec.step(actions)
        keep(result)
        if pos == 80:
            mask = [False, True, True, False, False, True]
            result = vec.reset(seed=[None, 3, None, None, None, None], options={"reset_mask": mask})
            keep(result)
        if pos == 160:
            result = vec.reset()
            keep(result)
    counts = vec._episode_counts
    seen.append([s.episode_count for s in vec._starts] if counts is None else counts.tolist())
    seen.append([vec.state(i) for i in range(6)])
    return seen


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, np.ndarray):
        return isinstance(b, np.ndarray) and a.dtype == b.dtype and a.tobytes() == b.tobytes()
    if isinstance(a, dict):
        return isinstance(b, dict) and list(a) == list(b) and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list | tuple):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    return bool(a == b)


@pytest.mark.parametrize("threads", [1, 3])
def test_a_same_step_autoreset_in_one_call_is_a_step_then_a_reset(threads: int) -> None:
    """With one back and one stake the step that ends an episode starts the next in the same
    call to ``_core``: the same observations, masks, rewards, final observations and infos as
    a ``reset_some`` after the step, partial and full resets in between."""
    two_calls = _same_step_run(False, threads)
    fused = _same_step_run(True, threads)
    assert sum("final_obs" in x for x in two_calls if isinstance(x, dict)) >= 10
    assert _same(fused, two_calls)


def test_several_backs_reset_after_the_step() -> None:
    vec = BalatroVectorEnv(2, back_keys=["b_red", "b_blue"], autoreset_mode=AutoresetMode.SAME_STEP)
    assert vec._episode_counts is None
    assert BalatroVectorEnv(2, autoreset_mode=AutoresetMode.NEXT_STEP)._episode_counts is None


def test_the_fused_autoreset_checks_its_arguments() -> None:
    n = 2
    core = _core.VectorEnv([("b_red", 1, "ARG", None, i) for i in range(n)], 50, True, "sparse")
    obs = np.zeros((n, _core.GYM_OBS_LEN), np.float32)
    masks = np.zeros((n, _core.MAX_ACTIONS), np.uint8)
    record = np.zeros(n * 30, np.uint8)
    final = np.zeros((n, _core.GYM_OBS_LEN), np.float32)
    counts = np.zeros(n, np.uint64)
    actions = np.zeros(n, np.int64)
    core.reset([("b_red", 1, f"ARG{i}", None, None) for i in range(n)], obs, masks)
    before = [core.state(i) for i in range(n)]
    with pytest.raises(ValueError, match="set_autoreset"):
        core.step(actions, [], obs, masks, record, final_obs=final, episode_counts=counts)
    with pytest.raises(ValueError, match="together"):
        core.step(actions, [], obs, masks, record, final_obs=final)
    with pytest.raises(ValueError, match="one start per env"):
        core.set_autoreset([("b_red", 1, "ARG", None)])
    with pytest.raises(ValueError, match="unknown back"):
        core.set_autoreset([("b_nope", 1, "ARG", None)] * n)
    core.set_autoreset([("b_red", 1, "ARG", None)] * n)
    with pytest.raises(ValueError, match="overlap"):
        core.step(actions, [], obs, masks, record, final_obs=obs, episode_counts=counts)
    with pytest.raises(ValueError, match="episode_counts"):
        core.step(actions, [], obs, masks, record, final_obs=final, episode_counts=counts[:1])
    counts[1] = np.iinfo(np.uint64).max
    with pytest.raises(IndexError, match="episode count"):
        core.step(actions, [], obs, masks, record, final_obs=final, episode_counts=counts)
    assert [core.state(i) for i in range(n)] == before


def test_a_resetting_env_ignores_its_action() -> None:
    """NEXT_STEP: the step after an episode end resets that sub-env whatever its action, a
    negative one included."""
    vec = BalatroVectorEnv(2, seed_prefix="NEG", max_steps=3)
    vec.reset(seed=1)
    for _ in range(3):
        _, _, terminated, truncated, info = vec.step([0, 0])
    assert truncated.all()
    obs, rewards, _, _, info = vec.step([-1, -(2**40)])
    assert not rewards.any() and info["action_mask"].any(axis=1).all()
    with pytest.raises(IndexError):
        vec.step([-1, 0])


def test_a_partial_reset() -> None:
    vec = BalatroVectorEnv(3, seed_prefix="PART", num_threads=2)
    obs, info = vec.reset(seed=30)
    for _ in range(3):
        actions = [int(np.flatnonzero(m)[0]) for m in info["action_mask"]]
        obs, _, _, _, info = vec.step(actions)
    before = {k: v.copy() for k, v in obs.items()}
    after, info = vec.reset(seed=[None, 9, None], options={"reset_mask": [False, True, False]})
    for k in before:
        assert after[k][0].tobytes() == before[k][0].tobytes()
        assert after[k][2].tobytes() == before[k][2].tobytes()
    fresh = BalatroGymnasiumEnv(DirectAdapter, seed_prefix="PART_1")
    f_obs, f_info = fresh.reset(seed=9)
    _same_obs(f_obs, {k: v[1] for k, v in after.items()}, "reset env")
    assert f_info["action_mask"].tobytes() == info["action_mask"][1].tobytes()
    assert vec.state(0).round == 1 and vec.state(1).round == 0
    with pytest.raises(ValueError):
        vec.reset(options={"reset_mask": [True]})


# ---------------------------------------------------------------------------
# The action space's version
# ---------------------------------------------------------------------------


def test_the_action_version() -> None:
    assert ACTION_VERSION == 2
    for env in (
        BalatroEnvironment(DirectAdapter),
        BalatroGymnasiumEnv(DirectAdapter),
        BalatroVectorEnv(1),
    ):
        assert env.action_version == ACTION_VERSION
    assert BalatroGymnasiumEnv.metadata["action_version"] == ACTION_VERSION
    assert BalatroVectorEnv(1).metadata["action_version"] == ACTION_VERSION
