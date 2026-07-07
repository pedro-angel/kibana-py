#!/bin/sh
# Fail if a secret-looking file is TRACKED by git. Defense-in-depth beyond .gitignore:
# gitignore does nothing for a file committed *before* it was ignored. Fail closed. POSIX sh.
set -u
hits=$(git ls-files \
  | grep -E '(^|/)(\.env(\..+)?|.+\.pem|.+\.key|.+\.p12|id_rsa|id_ed25519|credentials\.json|service-account.*\.json|.+\.tfvars(\..+)?|.+\.tfstate(\..+)?)$' \
  | grep -vE '\.example$' || true)
if [ -n "$hits" ]; then
  echo "FAIL: secret-looking file(s) tracked by git — untrack, rotate the secret, and gitignore it:"
  printf '  %s\n' $hits
  exit 1
fi
echo "ok: no secret-looking files tracked"
exit 0
