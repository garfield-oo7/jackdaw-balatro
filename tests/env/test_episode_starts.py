"""How the envs pick an episode's back and stake when they are given several.

The pick is drawn from the episode's run seed (:func:`~jackdaw.env.rust_gym.episode_start`),
so ``reset(seed=s)`` starts the same run every time, and the unseeded episodes
(``f"{seed_prefix}_{n}"``) start the same runs in every process, whatever else draws from
Python's global :mod:`random`. Every env picks the same way.
"""

from __future__ import annotations

import random
from typing import Any

import pytest

from jackdaw.core import Game
from jackdaw.env import (
    BalatroEnvironment,
    BalatroGymnasiumEnv,
    BalatroVectorEnv,
    DirectAdapter,
)
from jackdaw.env.rust_gym import episode_start
from tests.env.generic import GenericAdapter

BACKS = ["b_red", "b_blue", "b_yellow", "b_green", "b_black"]
STAKES = [1, 2, 3, 4, 5, 6, 7, 8]
_ADAPTERS = pytest.mark.parametrize(
    "adapter", [DirectAdapter, GenericAdapter], ids=["direct", "generic"]
)


def _start(game: Game) -> tuple[str, int, str]:
    """The run's back, stake and seed."""
    run = game.to_dict()["run"]
    return run["back"], run["stake"], game.seed


def test_the_pick_is_a_function_of_the_seed() -> None:
    assert episode_start("S7", BACKS, STAKES) == episode_start("S7", BACKS, STAKES)
    picks = [episode_start(f"S{i}", BACKS, STAKES) for i in range(400)]
    assert {b for b, _ in picks} == set(BACKS)
    assert {s for _, s in picks} == set(STAKES)
    # The back doesn't decide the stake.
    assert len(set(picks)) > 30
    # One of each: no draw.
    assert episode_start("S7", ["b_blue"], [3]) == ("b_blue", 3)


def test_the_pick_is_pinned() -> None:
    # A change here changes which run a seed starts: say so in the changelog.
    assert [episode_start(s, BACKS, STAKES) for s in ("0", "1", "TRAIN_0", "TRAIN_1")] == [
        ("b_black", 7),
        ("b_green", 5),
        ("b_blue", 4),
        ("b_red", 8),
    ]


def _gym_starts(env: Any, game: Any) -> list[tuple[str, int, str]]:
    """Seeded resets, then unseeded ones, with the global generator stirred in between."""
    starts = []
    for seed in range(10):
        random.random()
        env.reset(seed=seed)
        starts.append(_start(game()))
    for _ in range(4):
        random.random()
        env.reset()
        starts.append(_start(game()))
    return starts


@_ADAPTERS
def test_gym_env_starts_do_not_depend_on_the_global_random(adapter: type) -> None:
    runs = []
    for global_seed in (1, 2):
        random.seed(global_seed)
        env = BalatroGymnasiumEnv(adapter, back_keys=BACKS, stakes=STAKES, seed_prefix="EP")
        runs.append(_gym_starts(env, lambda env=env: env.game))
    assert runs[0] == runs[1]
    assert len({back for back, _, _ in runs[0]}) > 1
    for back, stake, seed in runs[0]:
        assert (back, stake) == episode_start(seed, BACKS, STAKES)
    assert [seed for _, _, seed in runs[0]] == [str(s) for s in range(10)] + [
        f"EP_{n}" for n in range(10, 14)
    ]


@_ADAPTERS
def test_balatro_environment_starts_do_not_depend_on_the_global_random(adapter: type) -> None:
    runs = []
    for global_seed in (1, 2):
        random.seed(global_seed)
        env = BalatroEnvironment(adapter, back_keys=BACKS, stakes=STAKES, seed_prefix="EP")
        runs.append(_gym_starts(env, lambda env=env: env._adapter.game))
    assert runs[0] == runs[1]
    for back, stake, seed in runs[0]:
        assert (back, stake) == episode_start(seed, BACKS, STAKES)


def test_vector_sub_envs_start_as_the_gym_env() -> None:
    venv = BalatroVectorEnv(
        num_envs=4, back_keys=BACKS, stakes=STAKES, seed_prefix="EP", num_threads=1
    )
    gyms = [
        BalatroGymnasiumEnv(DirectAdapter, back_keys=BACKS, stakes=STAKES, seed_prefix=f"EP_{i}")
        for i in range(4)
    ]
    # Unseeded, then seeded: sub-env i gets seed s + i.
    for seed in (None, 20, None):
        venv.reset(seed=seed)
        for i, env in enumerate(gyms):
            env.reset(seed=None if seed is None else seed + i)
            assert _start(venv.game(i)) == _start(env.game), (seed, i)
    assert len({_start(venv.game(i))[0] for i in range(4)} | {_start(g.game)[0] for g in gyms}) > 1
