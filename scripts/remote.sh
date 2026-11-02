#!/usr/bin/env bash
set -euo pipefail
# No mirror deletion and no local receipt upload.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-}"
MANIFEST="${2:-}"
case "$MODE" in sync|create|update|verify) ;; *) echo 'Usage: remote.sh sync|create|update|verify path/to/article.json' >&2; exit 2;; esac
: "${WECHAT_REMOTE_HOST:?Configure an SSH alias in WECHAT_REMOTE_HOST}"
REMOTE_ROOT="${WECHAT_REMOTE_ROOT:-/srv/wechat-workflow}"
REMOTE_ENV="${WECHAT_REMOTE_ENV:-/srv/wechat-config/publisher.env}"
[[ "$WECHAT_REMOTE_HOST" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || { echo 'Use a simple SSH alias' >&2; exit 2; }
for p in "$REMOTE_ROOT" "$REMOTE_ENV"; do
  [[ "$p" =~ ^/[a-zA-Z0-9_./-]+$ && "$p" != *'..'* ]] || { echo 'Use a simple absolute remote path' >&2; exit 2; }
done
cd "$ROOT"
python3 scripts/publisher.py check "$MANIFEST"
LIST="$(mktemp)"
trap 'rm -f "$LIST"' EXIT
python3 - "$MANIFEST" "$ROOT" > "$LIST" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, 'scripts')
from publisher import load_article
a=load_article(sys.argv[1]); root=Path(sys.argv[2]).resolve()
for p in a['files']:
    rel=p.relative_to(root).as_posix()
    if not rel.startswith('work/') or '\n' in rel or not all(c.isalnum() or c in '/._-' for c in rel):
        raise SystemExit('Place the article in work/ with simple path names')
    print(rel)
PY
REL="$(head -n 1 "$LIST")"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=12)
ssh "${SSH_OPTS[@]}" "$WECHAT_REMOTE_HOST" "mkdir -p '$REMOTE_ROOT/scripts' && chmod 700 '$REMOTE_ROOT'"
scp -q "${SSH_OPTS[@]}" scripts/publisher.py "$WECHAT_REMOTE_HOST:$REMOTE_ROOT/scripts/publisher.py"
rsync -a --files-from="$LIST" -e 'ssh -o BatchMode=yes -o ConnectTimeout=12' "$ROOT/" "$WECHAT_REMOTE_HOST:$REMOTE_ROOT/"
if [[ "$MODE" == sync ]]; then
  echo 'Article files synchronized; WeChat API was not called'
else
  ssh "${SSH_OPTS[@]}" "$WECHAT_REMOTE_HOST" \
    "cd '$REMOTE_ROOT' && set -a && . '$REMOTE_ENV' && set +a && .venv/bin/python scripts/publisher.py '$MODE' '$REL'"
fi
