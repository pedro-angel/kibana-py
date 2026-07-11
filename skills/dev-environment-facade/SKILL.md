---
name: dev-environment-facade
description: Use when wiring a project's dev workflow (local stack, test tiers, gates, docs), or when naming make targets in a repo that has siblings — build a thin self-documenting Makefile facade over real scripts, name targets from the shared cross-repo vocabulary, and split env files by owner so targets consume them but never write them.
---

# One Entry Point, Zero Ownership Confusion

A project's dev workflow deserves one discoverable surface: a thin facade
(`make help` tells the whole story) that delegates to real scripts and tools,
plus environment files whose ownership is so clear that no target ever needs
to rewrite what a human maintains. The facade encodes *which tool with which
flags*; procedures live in scripts; generated and hand-edited configuration
never share a file.

## When to use

Reach for this skill when adding a task runner or Makefile, when designing how
tests obtain credentials from a local stack, or when a "just run this one
command" developer experience is the goal.

Red-flag thoughts — if you catch yourself thinking any of these, STOP:

- "I'll put the logic in the Makefile." (Recipes are one-liners; logic lives in scripts.)
- "The test target can regenerate the env file while it's at it." (Targets consume; provisioning writes.)
- "I'll preserve the user's lines while rewriting the file." (Preservation machinery means the ownership split is missing.)
- "The recipe can just `source` the env file." (Shell-sourcing hand-edited files couples correctness to shell syntax; load in-process.)
- "The suite skipped, and skipped is green." (A certifying gate that passes on zero executed tests is a hole.)
- "Any 200 from the service proves the credential works." (Probe the endpoint — some are auth-blind.)
- "The script calls it `up`, so the target is `stack-up`." (Names come from the vocabulary; a borrowed verb must deliver at least its home meaning and destroy nothing that meaning leaves intact.)

## The rule

1. **Delegate, never duplicate.** Every recipe is a one-liner invoking a
   script or a tool; multi-step procedures live in `scripts/`. The facade is
   self-documenting: `.DEFAULT_GOAL := help`, every target annotated with a
   `## description`, help rendered by a grep/awk over `$(MAKEFILE_LIST)` —
   and the grep's character class must include digits, or a target like
   `test-e2e` silently vanishes from the help. Every facade target is
   `.PHONY` — vocabulary names (`build`, `docs`, `test`) shadow common
   directory names, and a non-phony target silently reports a directory
   "up to date" instead of keeping its promise.
2. **Mirror gate commands character-identically, and check the mirror.**
   Where the facade and a certifying gate run the same command, the strings
   must be byte-identical in both files, enforced by a `grep -F` loop —
   drift between "what developers run" and "what certifies done" is silent
   otherwise.
3. **Split env files by owner.** Machine-generated values (URLs, minted
   credentials) live in a file only the provisioning script writes — atomic
   temp-plus-rename, and *conditional*: keep a still-valid credential rather
   than minting on every run, validating against an endpoint that actually
   discriminates (probe it: some status endpoints return 200 to a bogus
   key). User-owned values live in a separate file no script ever writes or
   deletes. If the machine file contains foreign lines, abort with
   instructions — never silently drop them.
4. **Consumers load env in-process, at the last responsible moment.** Test
   suites read the env files themselves (a small loader in the test tree),
   at fixture time — never at conftest import, because test runners import
   deselected suites' conftests during collection, and a broken stack state
   must not brick unrelated runs. Merge with explicit-environment-wins
   semantics (`setdefault`), and *warn* when a shell export shadows a
   differing file value — a silent precedence inversion aims mutating suites
   at the wrong system.
5. **Absent and broken are different states.** No machine env file → skip
   the dependent suites ("no stack claimed"). File present but a required
   key missing, empty, or shadowed empty → fail hard with a
   cause-distinguishing message. A present file claims a working stack;
   silence on a broken claim is how gates go green on zero tests.
6. **Destructive verbs never touch user-owned files**, and the destructive
   target's own `## help` line carries the warning about what it does
   delete.
7. **One vocabulary across sibling repos, semantics attached.** Target
   names come from the shared vocabulary below, not from whatever the
   wrapped tool calls the operation — a backend's verb is acceptable only
   while the target delivers at least what the verb means at home and
   destroys nothing the verb's home meaning leaves intact. A name that
   appears in more than one repo is a contract: same name, same promise,
   everywhere — `make check` certifying security scans in one repo while
   omitting them in the sibling is the failure this rule exists to
   prevent.

## The target vocabulary

Promises are minimums — a repo may hold its target to more (a coverage
floor on `test`, a linkcheck inside `docs`), never to less: green must
never mean less than the name promises. Three tiers, by how strongly a
name is standardized (machine-readable list: `vocabulary.txt` beside this
file):

1. **Universal — every facade, identical promise.** `help` (default goal;
   lists every target), `setup` (bare clone → working toolchain:
   dependencies plus hooks; the stack is `stack-start`'s job), `test` (the
   unit suite: fast, no external dependencies; unit's target *is* `test` —
   there is no `test-unit`, and `test` never runs other tiers), `check`
   (the local PR gate — its floor below), `clean` (generated caches and
   artifacts only), `dod` (the Definition-of-Done gate, GO/NO-GO; a repo
   with no gate yet fails here with instructions — a stub that exits 0 is
   rule 5's hole wearing a new name; the same ruling covers a `test` with
   no unit suite behind it). "Every" is scoped: every repo that
   ships this facade — a repo with no dev workflow gets no facade, not a
   facade of stubs.
2. **Family verbs — none present without its capability; required
   exactly when it fires unless the manifest role says `optional` or
   `mutating` (see Enforcement); absence always beats rebinding.** Local stack:
   `stack-start` / `stack-stop` (non-destructive; data survives) /
   `stack-status` / `stack-destroy` (destructive — rule 6's help-line
   warning applies). Test tiers: `test-<tier>`, an open family
   (`test-integration`, `test-contract`, `test-e2e`, `test-benchmark`, a
   project's `test-python-matrix`) — the prefix is reserved for
   test-running targets, a tier target provisions the stack state it
   needs through the stack verbs, and a bare tier name (`e2e`,
   `contract`, `benchmark`) is never a target. Ship: `build` produces
   *and validates* everything the repo ships — wheel plus twine check,
   image plus smoke test; wanted granularity joins the prefix
   (`build-wheel`, `build-image`) with `build` composing them, and
   multi-step recipes delegate to a script per rule 1. Quality leaves,
   each with its own promise: `lint` (the repo's static analyzers in one
   shot — style, types, architecture contracts; security stays out, and
   analyzers `hooks` already certifies need not re-run: jointly the two
   leaves cover the set),
   `fix` (apply every auto-fix the analyzers or the hook manager offer;
   mutates the tree; never part of `check`), `audit` (dependency vulnerability scan), `sast` (static
   security scan of first-party code), `hooks` (run every configured
   commit hook against all files — named for the capability, not for
   whichever hook manager currently provides it). Docs: `docs` (strict
   build; warnings fail), `docs-serve` (live reload). `clean-all`:
   `clean` plus the toolchain `setup` created (the venv or equivalent) —
   never `.git/hooks`, which may hold user-authored hooks, and never the
   stack or its volumes (that is `stack-destroy`) — destructive, so rule
   6's help-line warning applies to it too.
3. **Project-specific — free naming, two constraints.** Never bind a
   universal or family name — or a reserved prefix (`test-`, `stack-`,
   `build-`; the manifest's `prefix` tier) — to different semantics, and
   no alias targets: a promise answers to one name.
   Extensions may join a family prefix as tier-3 names (`stack-seed`,
   `stack-env`); a concept a second repo needs gets promoted to family
   tier *here*, in the methodology, not standardized ad hoc between
   repos.

**`check`'s floor.** `check` runs, at minimum, every *read-only* quality
leaf whose capability fires — `lint`, `audit`, `sast`, `hooks`, never the
mutating `fix` — plus the unit suite and, where docs exist, the strict
docs build. The floor keys to capability markers, not to the target list:
deleting the `audit` target does not shrink the floor, only losing the
capability does. It is deliberately *not* defined as "everything my CI
runs": a repo whose CI skips security scans would then compliantly skip
them too, and the sibling divergence this vocabulary exists to prevent
would survive full compliance. CI may gate more than `check`, never less
— though comparing CI against the floor is review's job, alongside
promise-sameness. Compose `check` from the leaf targets — the command
strings then live once, in the leaf recipes, which is also where rule 2's
gate mirror greps them.

Verb overlap with a backend is not the sin; a borrowed word that warns
of less than the target destroys is. `stack-stop` coincides with
compose's `stop` exactly; `stack-start` promises *more* than compose's
`start` (which only restarts, never creates) — excess in the
non-destructive direction, which is safe. Compose's own `down`, though,
leaves volumes intact, so a volume-deleting `stack-down` destroys what
its borrowed word promises to spare; that pair is why the stack family
says `destroy`, which needs no glossary. Borrow a backend's word only
when the target delivers at least what the word means at home *and*
destroys nothing the word's home meaning leaves intact.

## Why

Each half protects the other. A facade without the ownership split ends up
rewriting mixed files with preserve-the-user's-lines machinery — rewrite
races, "teardown ate my config," and migration dances follow. An ownership
split without the facade leaves the knowledge of which script writes what in
people's heads. And both fail quietly without the gate rules: mirrored
commands drift, skipped suites read as green, and the first sign is a release
certified by a gate that ran nothing. The costs arrive late and misattributed
— a developer whose stray shell export silently redirects a mutating test
suite at a real system will debug everything except their own environment.

## In practice

Three field builds shaped this skill. The first (a Python client library)
established the facade: twenty one-line targets over `local-stack.sh` and
venv binaries, a self-documenting help, and integration tests that read the
stack's generated `.env`/`.env.local` themselves — make consumed, never
wrote. The second (an MCP server) ported the facade onto a uv/pytest repo and
added the mirror discipline: nine command strings byte-identical between the
Makefile and a Definition-of-Done gate, grep-verified in acceptance; its
probes also caught that the obvious credential-validity endpoint
(`/api/status`) returns 200 to a bogus API key — the conditional mint would
have kept dead keys forever, and only probing found the discriminating
endpoint. The third build split that repo's mixed env file by owner, and two
review findings became rules here: an import-time loader was reproduced
bricking plain unit runs (collection imports deselected conftests — rule 4's
"fixture time" is not a style preference), and the switch from shell-sourcing
to `setdefault` silently *inverted* precedence for anyone with a stray
`KIBANA_URL` export — hence rule 4's shadow warning. A fourth event turned
naming into a rule: the first two builds, sharing an author and this
methodology, had drifted apart — `stack-up/stack-down` in one, `stack-start/
stack-destroy` in the other; bare `e2e` versus `test-integration`; `image`
where the vocabulary says `build`; a missing `dod`; and, the finding that
mattered, a `check` that certified security scans in one repo while
omitting them in its sibling — invisibly to anyone habituated to the
sibling's `check`, since each repo faithfully mirrored its own CI (which
is why the floor is defined by content, not by CI). The vocabulary above
is the prescriptive reconciliation of that drift, and the first
migration (the MCP server) has since landed it: the reference checker
ran RED against the drifted Makefile — eighteen violations — the
migration turned it GREEN, and the full gate certified the result
against the live stack. The checker itself supplied one more lesson in
this skill's own spirit: its first draft failed *open* — a single
trailing space in a manifest row silently dropped a floor leaf from
enforcement — which is why the shipped checker normalizes its input and
hard-fails on unknown tiers, roles, and capability tokens. The library's
migration follows.

## Anti-patterns

- Logic in recipes — a Makefile that is itself a program.
- A test or gate target that writes, rewrites, or deletes an env file.
- Preserve-user-lines rewrite machinery instead of an ownership split.
- Shell-sourcing hand-edited env files inside recipes or gate scripts.
- Loading env at conftest import time ("it's only for the contract suite" —
  collection imports it everywhere).
- Validating a credential against an endpoint you never probed for
  auth-blindness.
- Skip-on-broken-state: treating a present-but-keyless env file the same as
  no file at all.
- A help grep whose character class silently hides targets with digits.
- Deriving target names from the backend instead of the vocabulary —
  `stack-up` because compose says `up`, or a destructive `stack-down`
  whose borrowed word promises less than it deletes.
- The same universal name making different promises in sibling repos — a
  `check` that runs security scans in one and skips them in the next.
- A conformance checker that fails open — a malformed manifest row
  silently skipping the very check it names.

## Enforcement

What a machine can check: bare `make` exits 0 and its (ANSI-stripped) output
lists every target, diffed against an enumerated list; a `grep -F` loop over
the mirrored command strings passes against both the Makefile and the gate
script; a grep proves no recipe or gate line writes the env files (the
provisioning script is the only writer); the certifying gate's suite runs
assert `passed ≥ 1` and `skipped = 0` in their logs; and the broken-state
path is provoked in acceptance — env file present but keyless must yield a
hard failure, file absent must yield the skip. For the vocabulary, the
machine checks names and composition — whether two repos' same-named
targets keep the same *promise* is review's job, and the checker should
not pretend otherwise. The canonical list is this skill's
`vocabulary.txt` (tiers universal/family/prefix/banned, plus per-name
capability and role columns); checkers consume that file, never a
hand-copied list. Name checks run against the Makefile's real target
namespace (`make -qp`'s database — parse the output and ignore the exit
status, nonzero by design under a phony default goal), not the help text
— an unannotated compatibility alias hides from help but not from the
database — matched anchored on exact names: every universal name
present *and expanding to at least one command* (a `.PHONY` ghost whose
rule was deleted is rule 5's green-on-nothing hole), no banned name
present, `test-integration` never satisfying a check for `test`, and for every target under a manifest `prefix` row the
bare remainder (`python-matrix` from `test-python-matrix`) derived and
asserted absent — that derivation is all a checker does with prefix
rows; rebinding judgments stay with review. The help check stays for
legibility (rule 1: every target listed and annotated). Family
names are required exactly when their capability marker fires, unless
the manifest role says `optional` or `mutating` (then allowed, never
required); the manifest's tokens mean: stack = a compose file or a
committed stack-managing script (a non-compose stack a checker cannot
detect falls to review); suite = the tier's suite registered in the
repo's test config (a directory or marker); ship = a packaging manifest
declaring a shippable artifact (a pyproject `[project]` table, a
package.json, a Dockerfile); analyzers = static-analyzer config outside
the hook config (when `hooks` certifies the full set, `lint` may be
absent); autofix = any analyzer or hook config that offers auto-fixes;
deps = a dependency manifest; source = first-party code; hookcfg = a
hook-manager config; docs = a docs build config; env = `setup` creates
a toolchain directory (a venv or equivalent). `check`'s floor
derives from the manifest's `floor` role: for each such name whose
capability fires, every command `make -n <name>` prints must appear in
`make -n check`'s output — both sides expanded, so leaf recipes may use
make variables, *except* the strings rule 2 mirrors into a certifying
gate: those stay literal, because that mirror is byte-level and greps
the *leaf* recipes, where each command string lives once. A repo
has adopted the vocabulary when the conformance check runs green in its
own CI. The reference checker ships beside the manifest
(`vocabulary-conformance.sh`, battle-tested by the first migration): it
matches names literally, reads the real target database, and fails
closed — a malformed manifest row is a hard error, never a silent skip.
Its limits are deliberate and stated: GNU make with the Makefile at the
repo root; no target the checker expands may invoke make or carry `+`
recipes (`$(MAKE)` and `+` lines execute under `-n`; a literal make
defeats the chatter filter — the guard covers every expanded target and
one level into `check`, deeper recursion is the adopter's to prevent,
and `-qp` already runs `$(shell)` at parse time); and rule 2's
facade↔gate mirror loop is not its job — that stays a per-repo
acceptance check. Consuming repos execute the vendored copy — a forked
checker freezes its parser off the sync path.

## Related skills

- [../configuration-single-source-of-truth/SKILL.md](../configuration-single-source-of-truth/SKILL.md)
- [../grounded-verifiable-gates/SKILL.md](../grounded-verifiable-gates/SKILL.md)
- [../battle-testing-on-real-infra/SKILL.md](../battle-testing-on-real-infra/SKILL.md)
- [../environment-research/SKILL.md](../environment-research/SKILL.md)
- [../secrets-and-teardown-discipline/SKILL.md](../secrets-and-teardown-discipline/SKILL.md)
- [../reversible-by-default-confirm-consequential/SKILL.md](../reversible-by-default-confirm-consequential/SKILL.md)
