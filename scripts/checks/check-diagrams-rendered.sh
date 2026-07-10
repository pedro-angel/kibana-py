#!/bin/sh
# Post-docs-build check: every Mermaid fence in docs/source must have produced a
# rendered node in the built HTML (fence count == node count).
#
# The incident this catches: a Sphinx -W pipeline with no Mermaid extension silently
# forced a fresh doc back to fenced ASCII art — the docs-as-deliverable anti-pattern —
# because nothing verified the renderer was provisioned and actually fired. The build
# alone can't catch it: an unrendered fence is just a code block, not a warning.
#
# Runs from the repo root, AFTER a docs build (wired into `make docs`, which CI reuses).
# Fail-closed: a missing build directory is a FAIL, not a skip.
set -u

SRC=docs/source
OUT=docs/build/html

[ -d "$OUT" ] || {
  echo "FAIL: $OUT not found — run the docs build first (this check verifies its output)."
  exit 1
}

fences=$(grep -rF '```{mermaid}' "$SRC" --include='*.md' | wc -l | tr -d ' ')
nodes=$(grep -roF 'class="mermaid"' "$OUT" | wc -l | tr -d ' ')

if [ "$fences" -eq 0 ]; then
  echo "ok: no mermaid fences in $SRC — nothing to verify"
  exit 0
fi

if [ "$fences" -ne "$nodes" ]; then
  echo "FAIL: $fences mermaid fence(s) in $SRC but $nodes rendered node(s) in $OUT."
  echo "  A fence that didn't render is shipping as a dead code block — check that"
  echo "  sphinxcontrib.mermaid is in conf.py extensions and the [docs] extra."
  exit 1
fi

echo "ok: $fences/$fences mermaid fences rendered"
