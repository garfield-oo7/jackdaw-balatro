# Agent instructions

Rules for AI coding agents (Claude Code and others) working in this fork,
`garfield-oo7/jackdaw-balatro`. They are this fork's workflow rules: leave this file and
CLAUDE.md out of pull requests to the upstream repository.

## Commits and pull requests

- Never add an AI agent as a co-author: no `Co-Authored-By: Claude ...` or similar line.
- Never put a link to an agent session (for example a `Claude-Session: https://claude.ai/code/...`
  line) or any other agent attribution in a commit message, a pull request, an issue or a code
  comment.
- Never put a model name or identifier in commits, pull requests or code.
- Author and commit as the fork's owner, `Agamjyot Singh Chadha <agamjyot01@gmail.com>`, never
  as an agent identity such as `Claude <noreply@anthropic.com>`. In a fresh environment set it
  first: `git config --global user.name "Agamjyot Singh Chadha"` and
  `git config --global user.email "agamjyot01@gmail.com"`, and check it with
  `git log -1 --format='%an <%ae>'` after the first commit.

## Where work goes

- Push only to this fork (`origin`, `garfield-oo7/jackdaw-balatro`), never to the upstream
  repository `TylerFlar/jackdaw-balatro`: no commits, pushes or branches there.
- Pull requests to upstream are opened by the fork's owner, against upstream's `dev` branch
  (see CONTRIBUTING.md). An agent prepares the branch on the fork and the description.
- A branch for an upstream pull request starts from upstream's `dev`
  (`git fetch https://github.com/TylerFlar/jackdaw-balatro dev`), never from the fork's `main`,
  which carries this file and CLAUDE.md. Before handing it over, check that
  `git diff --stat FETCH_HEAD..BRANCH` lists neither file.
- A pull request with performance work states the headline numbers (before and after, how they
  were measured) and how each speed-up was achieved, and nothing more.
- Don't rewrite history that has been pushed, or force-push, without the owner's go-ahead.

## Before a pull request goes upstream

Lessons from the maintainer's review of #39–#41 (fixed in upstream #42 and #44). Check each one
before handing the owner a branch.

- **Public interfaces keep their shape.** A speed-up keeps every public signature and return
  value, `jackdaw._core` included: Jackdaw Arena and agents call it directly. Add an opt-in
  (a keyword argument) instead of changing what an existing call returns, and pin the old form
  with a test. (#42: `_core.GymEnv.reset`/`step` had started returning the mask with the
  observation; upstream made it `mask=True`.)
- **Replacing a dependency keeps what users saw of it.** List the environment variables,
  defaults and knobs the old one read, and keep each. (#44: `num_threads=0` stopped honouring
  `RAYON_NUM_THREADS` when the pool replaced rayon.)
- **Bound untrusted input before it sizes anything.** Snapshot imports, files and environment
  variables are checked for range before they become an allocation or an index. (#42: one huge
  sort id in a snapshot aborted the process.)
- **Docs say what the code does, costs included.** When a review, a test or a benchmark finds
  the code and its docs disagree, fix one of them in the same pull request; "pre-existing" is
  no reason to ship it. (#44: idle threads polled 200 µs, not the documented 100, which our own
  review had flagged; a step does wait for a thread descheduled mid-env.)
- **Opt-in shared buffers name the wrappers they break with.** `copy=False` style options say
  which common wrappers hold an observation across a reset (SB3's `DummyVecEnv`, gymnasium's
  `SyncVectorEnv` in SAME_STEP mode) and so need the default.
- **CI and release changes have run before review.** Run a changed workflow on the fork
  (Actions → workflow → Run workflow) for every leg it touches, and make the workflow install
  every tool its scripts need. (#44: the PGO legs needed `setup-uv`.)
- **Build and release steps install pinned dependencies,** from `uv.lock` with
  `--require-hashes`, never freshly resolved: the release build runs next on the same machine.
- **Equality and cache-key checks over a struct destructure it**, naming every field, so a
  field added later can't be left out of the check. (#44: `DeckTemplate::made_with`.)
- **Every number is measured on that branch.** A speed-up quoted in a pull request or the
  changelog is measured on that exact branch against its base, not taken from a combined run.
- **Titles say what changes**, as a short sentence ("Faster engine and env, same runs"), not the
  branch name.

## Game parity

The engine is a 1-1 clone of Balatro 1.0.1o's Lua source. A change, a performance change
included, must not change what the game does: the same RNG draws in the same order, the same
floating-point operations, the same event order, snapshots, observations, masks and action
tables. Before committing an engine or env change, check:

- `cargo run --release -p jackdaw-env --example rollout 300000 --verify` prints the reference
  hash, and so does `--deep` (`rollout 200000 --verify --deep`). Both hashes must stay the same
  unless a change is meant to change the game, which then follows CONTRIBUTING.md.
- `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`,
  `cargo test --workspace --exclude jackdaw-py`, `uv run pytest`, `ruff check .`.

## Agent settings

The owner runs Claude Code with Claude's attribution off and a 500k-token context window. In a
fresh (for example cloud) session, set the same in `~/.claude/settings.json`:

```json
{
  "attribution": { "commit": "", "pr": "", "sessionUrl": false },
  "autoCompactWindow": 500000
}
```
