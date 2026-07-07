#!/bin/sh
# commit-msg hook: require a provenance/evidence trailer in the commit body.
# $1 = path to the commit message file. POSIX sh; uses git interpret-trailers.
set -u
msg="${1:?usage: check-commit-trailer.sh <commit-msg-file>}"
if git interpret-trailers --parse < "$msg" \
   | grep -qiE '^(Signed-off-by|Co-Authored-By|Evidence|Refs|Verified-by):'; then
  exit 0
fi
echo "FAIL: commit message needs a provenance trailer in the body, e.g.:"
echo "  Signed-off-by: Name <email>  (add with: git commit -s)"
echo "  Co-Authored-By: Name <email>   |   Evidence: <path-or-url>   |   Refs: <issue>"
exit 1
