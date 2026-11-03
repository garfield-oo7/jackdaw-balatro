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
- A pull request with performance work states the headline numbers (before and after, how they
  were measured) and how each speed-up was achieved, and nothing more.
- Don't rewrite history that has been pushed, or force-push, without the owner's go-ahead.

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
