# CLAUDE.md — Claude Code adapter

This project follows the engineering methodology in **[AGENTS.md](./AGENTS.md)**. That file is the single source of truth; this adapter only wires it into Claude Code and adds nothing to the rules.

## How this works here

- **Canonical methodology:** [`AGENTS.md`](./AGENTS.md) holds the instruction priority, the index of principles, and how to apply them. Read it for anything non-trivial.
- **Skills:** each principle is a full skill at `skills/<slug>/SKILL.md`. The files carry YAML frontmatter (`name`, `description`), so Claude Code auto-discovers them as skills — no manual registration. Other agents reach the same files through their own mechanism (Cursor rules, Copilot instructions, a `read skills/<slug>/SKILL.md` step); the content is identical.
- **Before acting, load the relevant skill.** Match the task to the principles in `AGENTS.md`, then read the matching `SKILL.md` in full before you implement. Most non-trivial tasks touch two or three. Don't back-fill the process after writing code.
- **User instructions override.** Order is: the user's explicit request first, this methodology second, your built-in defaults last. If the user contradicts a principle, do what they asked — you may note the trade-off, you don't overrule them.

The skills are written in actions, not Claude-specific tool names ("run the test suite against real infrastructure," "create a checkpoint commit"), so they apply unchanged in any agent. The shipped cloud agent referenced inside them is an illustrative example only — never a prerequisite.

## Install

See `INSTALL.md` at the root of the agent-methodology pack repo for the install modes — copy, sync bot,
or (for the maintainer's own hosts) the pinned plugin. In short: put `AGENTS.md` + `skills/` at the project root with this file
as `./CLAUDE.md`; Claude Code reads the skills by path, and discovers them as native skills once they
sit under a skills directory. Don't hand-maintain a per-slug install list here — the pack ships the
modes, and the pinned-plugin path installs the whole tier through one symlink.
