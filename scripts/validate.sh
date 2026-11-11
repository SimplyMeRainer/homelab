#!/usr/bin/env bash
# Validation only: never invoke a cloud apply, guest playbook or service startup.
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
MODE=full
for arg in "$@"; do
  case "$arg" in
    --tests-only) MODE=tests ;;
    --help|-h)
      printf '%s\n' 'Usage: bash scripts/validate.sh [--tests-only]' \
        'Runs offline tests and configuration checks. Dependencies may download from public registries.' \
        'No infrastructure deployment, SSH, cloud credentials or Docker daemon is required.'
      exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
  esac
done
for tool in python3 git; do
  command -v "$tool" >/dev/null || { printf 'Missing validation tool: %s\n' "$tool" >&2; exit 1; }
done
export PYTHONDONTWRITEBYTECODE=1
printf '\n[tests] component and integration contracts\n'
for suite in foundation/tests ansible/tests services/tests tests/integration; do
  test -d "$suite" || { printf 'Missing kit test directory: %s\n' "$suite" >&2; exit 1; }
  printf '\n[tests] %s\n' "$suite"
  python3 -m unittest discover -s "$suite" -p 'test_*.py' -v
done
if [ "$MODE" = tests ]; then
  printf '\nPASS: offline component tests. Native validation was not requested.\n'
  exit 0
fi
for tool in terraform ansible-playbook docker helm curl; do
  command -v "$tool" >/dev/null || { printf 'Missing validation tool: %s\n' "$tool" >&2; exit 1; }
done
printf '\n[terraform] formatting, provider schemas and mock-provider plans\n'
terraform fmt -check -recursive terraform
TF_ROOTS=$(python3 - <<'PY'
from pathlib import Path
import subprocess
paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], text=True).split('\0')
roots = sorted({str(Path(p).parent) for p in paths if p.startswith('terraform/') and p.endswith('/versions.tf')})
if not roots:
    raise SystemExit('No Terraform roots found')
print('\n'.join(roots))
PY
)
while IFS= read -r module; do
  printf '\n[terraform] %s\n' "$module"
  terraform -chdir="$module" init -backend=false -input=false -no-color
  terraform -chdir="$module" validate -no-color
  terraform -chdir="$module" test -no-color
 done <<< "$TF_ROOTS"
printf '\n[ansible] native syntax checks (no play execution)\n'
PLAYBOOKS=$(python3 - <<'PY'
from pathlib import Path
import subprocess
import yaml
paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], text=True).split('\0')
for name in sorted(paths):
    path = Path(name)
    if path.suffix not in {'.yml', '.yaml'} or not name.startswith(('foundation/', 'ansible/', 'services/')):
        continue
    if any(part in {'tests', 'templates'} for part in path.parts):
        continue
    data = yaml.safe_load(path.read_text())
    if isinstance(data, list) and any(isinstance(play, dict) and ('hosts' in play or 'import_playbook' in play) for play in data):
        print(name)
PY
)
test -n "$PLAYBOOKS" || { printf 'No Ansible entrypoints found\n' >&2; exit 1; }
while IFS= read -r playbook; do
  printf '\n[ansible] %s\n' "$playbook"
  ansible-playbook --syntax-check -i localhost, "$playbook"
 done <<< "$PLAYBOOKS"
printf '\n[helm] checksum-locked charts and native schema renders\n'
CHART_DIR=${CHART_DIR:-runtime/charts}
export CHART_DIR
umask 077
mkdir -p "$CHART_DIR"
CHARTS=$(python3 - <<'PY'
import json
import re
from urllib.parse import urlsplit
for chart in json.load(open('kubernetes/charts.lock.json')):
    assert re.fullmatch(r'[A-Za-z0-9._+-]+', chart['name'])
    assert re.fullmatch(r'[A-Za-z0-9._+-]+', chart['version'])
    assert re.fullmatch(r'[a-f0-9]{64}', chart['sha256'])
    assert urlsplit(chart['url']).scheme == 'https'
    assert not any(c.isspace() for c in chart['url'])
    print(chart['url'], chart['sha256'], chart['name']+'-'+chart['version']+'.tgz', sep='\t')
PY
)
tmpfile=
trap 'if [ -n "${tmpfile:-}" ]; then rm -f -- "$tmpfile"; fi' EXIT
while IFS=$'\t' read -r url digest filename; do
  archive="$CHART_DIR/$filename"
  test ! -L "$archive" || { printf 'Refusing symlink chart: %s\n' "$archive" >&2; exit 1; }
  if [ ! -e "$archive" ]; then
    tmpfile=$(mktemp "$CHART_DIR/.download.XXXXXX")
    curl --fail --location --silent --show-error --output "$tmpfile" -- "$url"
    python3 - "$tmpfile" "$digest" <<'PY'
import hashlib, pathlib, sys
assert hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() == sys.argv[2], 'Downloaded chart checksum mismatch'
PY
    mv -- "$tmpfile" "$archive"
    tmpfile=
  fi
  python3 - "$archive" "$digest" <<'PY'
import hashlib, pathlib, sys
assert hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() == sys.argv[2], 'Cached chart checksum mismatch'
PY
 done <<< "$CHARTS"
bash kubernetes/tests/render.sh
printf '\nPASS: tests and native validation. No infrastructure was deployed.\n'
