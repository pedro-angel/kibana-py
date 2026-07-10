---
name: secrets-and-teardown-discipline
description: Use when handling credentials, IaC, or ephemeral cloud — make secrets un-committable, grant least privilege, tear down to zero, own only your scope.
---

# Secrets, Least Privilege, Teardown, and Scope Ownership

Make secrets — and identifying details — structurally impossible to commit, grant the narrowest privilege that works, always tear down ephemeral infrastructure and verify it reached zero, and provision only inside the lifecycle you own. Prevention is structural — not a reviewer remembering to look.

## When to use

Reach for this whenever you touch any of:

- Credentials, API keys, tokens, connection strings, or `.env`-style config.
- Identifying details of private infrastructure: hostnames, usernames, home paths, internal domains, non-public IPs — reconnaissance data, even when they unlock nothing.
- Infrastructure-as-code (Terraform, Pulumi, CloudFormation, CDK, Bicep) — especially anything that grants IAM roles or creates secret containers.
- Ephemeral or throwaway cloud environments spun up for a demo, test, or review.
- Resources you create inside a project, account, or namespace someone else owns.

Red-flag thoughts — if you catch yourself thinking any of these, STOP and apply this skill:

- "I'll just paste the real value in for now and rotate it later."
- "The reviewer will notice if a secret slips into the diff."
- "Project-wide access is simpler than scoping it to one resource."
- "`destroy` ran without errors, so it's all gone."
- "I'll manage the whole project lifecycle since I'm already in here."
- "It's only a quick test environment, the rules don't apply."

## The rule

1. **Gitignore secrets by pattern, allowlist only the template.** Ignore every secret-bearing file by glob (`.env`, `.env.*`, `*.tfvars`, `*.tfstate*`) and force-allow exactly one non-secret template back in (`!.env.example`). A secret should be physically unable to enter a commit, regardless of who is reviewing. Identifying details get the same structural treatment: a pre-commit check that derives the authoring machine's own identity at runtime and denies entries from a per-user registry that lives *outside* any repo — outside, because the list of your private names is itself a secret.
2. **Provision the container, inject the value out-of-band.** In IaC, create the secret *container* with a placeholder; never put the real value in code or state. Add the real value through a separate channel — a CLI write (`gcloud secrets versions add`, `aws secretsmanager put-secret-value`), a CI secret store, or a manual console step. The value lives only in the secret manager, never in the repo and never in IaC state.
3. **Grant least privilege resource-by-resource.** Scope each grant to the specific resource: secret access to *that* secret, storage access to *that* bucket — not the project or account (an AWS IAM policy scoped to a single resource ARN, or an Azure RBAC assignment scoped to one resource, says the same thing in another provider's terms). Gate optional grants behind a condition (e.g. a `count`/`for_each` flag) so they exist only when that feature is on. Use separate identities for separate phases — a build identity and a runtime identity — so neither inherits the other's reach. No broad `Editor`, no project-wide `secretAccessor`.
4. **Deploy private by default.** Ship with internal-only ingress and no public-invoker binding. A service that does not need to be on the public internet must not be reachable from it until you deliberately open it.
5. **Engineer one-command teardown, then verify zero.** Set the flags that let a single destroy command actually complete (`force_destroy = true` on buckets, `deletion_protection = false` on databases) so nothing blocks teardown. After every ephemeral cycle, run the destroy *and then verify zero independently* — e.g. `terraform state list` returns empty AND a provider-side query (`gcloud asset search-all-resources`, `aws resourcegroupstaggingapi get-resources`, or a billing/cost report) shows no surviving resources. For a fully throwaway environment, delete the enclosing project/account afterward to sweep up residue your IaC never tracked (staging buckets, default logs, leftover disks).
6. **Own only your scope.** When you provision inside an externally-owned project, refuse its lifecycle structurally: do not declare a `project` (or account/org) resource your IaC could later destroy. Externalize what you don't own, and say so plainly in the docs so the next person knows the boundary.

## Why

Secrets that *can* be committed eventually *are* — by a tired teammate, an autoformatter, or an agent that globs `*`. A gitignore pattern blocks all of those at once; reviewer vigilance scales to zero. Real values in IaC state are just as exposed as values in code, because state is a plaintext file that gets copied, cached, and backed up. Broad IAM grants turn one compromised identity into total blast radius; resource-scoped grants cap the damage to exactly what that identity touches. And "destroy ran fine" is not "zero cost" — orphaned buckets, disks, and IP reservations bill silently for months. Verifying zero, and deleting the throwaway container, is the only way to actually stop the meter. Managing a lifecycle you don't own is how a stray `destroy` deletes someone else's project.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent shipped to a serverless cloud — the discipline showed up in three artifacts:

- The `.gitignore` carried `.env` and `.env.*` with a single `!.env.example` exception, so no contributor could commit a real key even by accident, while the template stayed in the repo.
- The Terraform `iam.tf` deliberately kept `cloudsql.client` and secret access *out* of the always-on project-level roles: `cloudsql.client` was gated behind the `enable_cloud_sql` flag, while secret access was scoped to the specific secret resources — the DB-URL secret *additionally* flag-gated, and the ticketing-system-token secret always-on but still resource-scoped (never project-wide). The design goal, documented inline, was that the default serverless deployment should carry no standing privilege it never uses.
- A recorded end-to-end teardown showed `24 destroyed`, after which the project itself was deleted "to remove the CI staging bucket and guarantee zero cost" — destroy, then delete the enclosing project to sweep residue the IaC never tracked. (The artifact captured the destroy count and the project-delete sweep; the explicit verify-zero check in between is the step this skill recommends adding, not one that recording demonstrates.)

You can apply all three without knowing anything about that project: ignore-by-pattern, scope-by-resource, destroy-then-verify-then-sweep.

## Anti-patterns

- Relying on a reviewer to catch a committed credential instead of making it un-committable by gitignore.
- Putting a real secret value in IaC state or a committed `tfvars` file.
- Granting project-wide `secretAccessor` or `Editor` when one resource-scoped binding would do.
- Calling `terraform destroy` "done" without listing resources to confirm zero — leaving a staging bucket or reserved IP quietly billing.
- Quietly managing a project/account lifecycle your tool does not own, so your teardown can delete more than you created.

## Enforcement

Most of this skill already ships as machinery: gitignore secret globs, `detect-private-key`, `check-no-tracked-secrets.sh`, and `check-no-private-identifiers.sh` (identity, not just credentials) in git-controls-starter — all fail-closed at commit time. What remains checkable: IaC linted for resource-scoped grants (no broad roles), and teardown certified by a verify-zero script — state list empty AND a provider-side query empty — that fails on any survivor instead of trusting a clean destroy log.

## Related skills

- [../reversible-by-default-confirm-consequential/SKILL.md](../reversible-by-default-confirm-consequential/SKILL.md)
- [../configuration-single-source-of-truth/SKILL.md](../configuration-single-source-of-truth/SKILL.md)
- [../battle-testing-on-real-infra/SKILL.md](../battle-testing-on-real-infra/SKILL.md)
- [../hexagonal-with-enforced-contracts/SKILL.md](../hexagonal-with-enforced-contracts/SKILL.md)
- [../structural-security-boundary/SKILL.md](../structural-security-boundary/SKILL.md)
