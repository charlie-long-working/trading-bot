#!/usr/bin/env bash
# Publish the static OI playbook site to the `gh-pages` branch (GitHub Pages).
#
#   scripts/publish_static.sh               # export → privacy check → sync → amend → push
#   scripts/publish_static.sh --no-push     # everything except the push (local test)
#   scripts/publish_static.sh --skip-export # republish the current web/data/latest.json
#
# Guarantees:
#   - gh-pages always holds exactly ONE commit (amend + force-with-lease); history stays local
#     in var/static-history/ (gitignored).
#   - Only refs/heads/gh-pages is ever pushed. main is never touched.
#   - Aborts if the privacy test fails or a file outside the site allowlist would be published.
#   - Lock dir prevents overlapping runs; log: ~/Library/Logs/trading-bot-static.log (local).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="gh-pages"
REMOTE="${STATIC_REMOTE:-origin}"
WT="$ROOT/var/gh-pages-wt"
LOCK="$ROOT/var/publish_static.lock"
LOG="${STATIC_LOG:-$HOME/Library/Logs/trading-bot-static.log}"
PY="$ROOT/.venv/bin/python"
# Files allowed on gh-pages (anything else aborts the publish)
SITE_FILES=".nojekyll app.js data/latest.json index.html style.css"

PUSH=1
EXPORT=1
for arg in "$@"; do
  case "$arg" in
    --no-push) PUSH=0 ;;
    --skip-export) EXPORT=0 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 64 ;;
  esac
done

mkdir -p "$(dirname "$LOG")" "$ROOT/var"
if [[ -t 1 ]]; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >>"$LOG" 2>&1
fi

log() { echo "[publish_static] $(date -u +%Y-%m-%dT%H:%M:%SZ) $*"; }
die() { log "ABORT: $*"; exit 1; }

# ---- lock (mkdir is atomic) ----
if ! mkdir "$LOCK" 2>/dev/null; then
  pid="$(cat "$LOCK/pid" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    log "another run in progress (pid $pid) → skip"
    exit 0
  fi
  log "stale lock (pid ${pid:-?}) → taking over"
  rm -rf "$LOCK"
  mkdir "$LOCK"
fi
echo $$ >"$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

log "start (push=$PUSH export=$EXPORT)"
[[ -x "$PY" ]] || die ".venv/bin/python missing"

# ---- 1. export ----
if [[ "$EXPORT" == 1 ]]; then
  set +e
  PYTHONPATH="$ROOT" "$PY" scripts/export_static_snapshot.py
  rc=$?
  set -e
  if [[ $rc == 2 ]]; then
    log "every scan failed → latest.json kept, nothing new to publish"
    exit 2
  elif [[ $rc != 0 ]]; then
    die "exporter failed (rc=$rc)"
  fi
fi
[[ -s web/data/latest.json ]] || die "web/data/latest.json missing"

# ---- 2. privacy gate on the exported file ----
STATIC_SNAPSHOT_PATH="$ROOT/web/data/latest.json" PYTHONPATH="$ROOT" \
  "$PY" -m unittest -q tests.test_static_snapshot_privacy || die "privacy test failed (web/data/latest.json)"

# ---- 3. identity: must be the repo's noreply address ----
EMAIL="$(git config user.email || true)"
NAME="$(git config user.name || true)"
[[ "$EMAIL" == *@users.noreply.github.com ]] || die "git user.email is not a GitHub noreply address"
[[ -n "$NAME" ]] || die "git user.name not set"
export GIT_AUTHOR_NAME="$NAME" GIT_AUTHOR_EMAIL="$EMAIL" GIT_COMMITTER_NAME="$NAME" GIT_COMMITTER_EMAIL="$EMAIL"

# ---- 4. gh-pages worktree (detached; no local branch, so any checkout can publish) ----
REMOTE_SHA="$(git ls-remote --heads "$REMOTE" "refs/heads/$BRANCH" | awk '{print $1}')"
git worktree prune
if [[ -n "$REMOTE_SHA" ]]; then
  git fetch -q "$REMOTE" "+refs/heads/$BRANCH:refs/remotes/$REMOTE/$BRANCH"
fi
if [[ ! -e "$WT/.git" ]]; then
  rm -rf "$WT"
  if [[ -n "$REMOTE_SHA" ]]; then
    git worktree add -q --detach "$WT" "$REMOTE_SHA"
  else
    git worktree add -q --detach --no-checkout "$WT" HEAD
  fi
fi
if [[ -n "$REMOTE_SHA" ]]; then
  git -C "$WT" reset -q --hard "$REMOTE_SHA"   # mirror the published commit
  FIRST=0
else
  FIRST=1                                       # no gh-pages yet → orphan commit below
fi
git -C "$WT" clean -qfdx

# ---- 5. sync site files ----
rsync -a --delete \
  --exclude '.git' --exclude '.DS_Store' --exclude '.gitkeep' --exclude '.*.tmp-*' \
  "$ROOT/web/" "$WT/"

STATIC_SNAPSHOT_PATH="$WT/data/latest.json" PYTHONPATH="$ROOT" \
  "$PY" -m unittest -q tests.test_static_snapshot_privacy || die "privacy test failed (gh-pages copy)"

if [[ "$FIRST" == 1 ]]; then
  git -C "$WT" read-tree --empty
fi
git -C "$WT" add -A
PUBLISHED="$(git -C "$WT" diff --cached --name-only --diff-filter=d HEAD 2>/dev/null || true)"
ALL_FILES="$(git -C "$WT" ls-files | sort | tr '\n' ' ' | sed 's/ $//')"
EXPECTED="$(echo $SITE_FILES | tr ' ' '\n' | sort | tr '\n' ' ' | sed 's/ $//')"
[[ "$ALL_FILES" == "$EXPECTED" ]] || die "unexpected files on gh-pages: [$ALL_FILES] (allowed: [$EXPECTED])"

if [[ "$FIRST" == 0 ]] && git -C "$WT" diff --cached --quiet HEAD; then
  log "no change vs published gh-pages → nothing to do"
  exit 0
fi
if [[ "$FIRST" == 0 ]] && git -C "$WT" diff --cached --quiet HEAD -- data/latest.json; then
  log "latest.json unchanged (site files changed: ${PUBLISHED//$'\n'/ })"
fi

GEN="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["generated_at"])' "$WT/data/latest.json")"
MSG="Static OI playbook snapshot $GEN"

# ---- 6. single commit ----
if [[ "$FIRST" == 1 ]]; then
  TREE="$(git -C "$WT" write-tree)"
  NEW="$(git -C "$WT" commit-tree "$TREE" -m "$MSG")"   # orphan: no parent
  git -C "$WT" reset -q --soft "$NEW"
else
  git -C "$WT" commit -q --amend --reset-author -m "$MSG"
fi
COUNT="$(git -C "$WT" rev-list --count HEAD)"
[[ "$COUNT" == 1 ]] || die "gh-pages would have $COUNT commits (expected 1)"
NEW_SHA="$(git -C "$WT" rev-parse HEAD)"
log "commit $NEW_SHA ($MSG)"

# ---- 7. last-chance leak grep over everything about to be pushed (files + commit message) ----
LEAK_PATTERNS=("/Users/" "/home/" "$HOME")
for ident in "$(id -un)" "$(hostname -s 2>/dev/null || true)" "$(scutil --get ComputerName 2>/dev/null || true)" \
             "$(git config --global user.email 2>/dev/null || true)"; do
  [[ ${#ident} -ge 3 && "$ident" != *@users.noreply.github.com ]] && LEAK_PATTERNS+=("$ident")
done
SCAN="$(mktemp -d)"
git -C "$WT" log -1 --format='%an%n%ae%n%cn%n%ce%n%B' >"$SCAN/commit.txt"
git -C "$WT" archive HEAD | tar -x -C "$SCAN"
for pat in "${LEAK_PATTERNS[@]}"; do
  if grep -rqiF -- "$pat" "$SCAN"; then
    rm -rf "$SCAN"
    die "leak grep matched a local identity/path pattern in the gh-pages commit (not pushed)"
  fi
done
if grep -rqE '[0-9]{6,12}:[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_|sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY' "$SCAN"; then
  rm -rf "$SCAN"
  die "leak grep matched a token/key pattern in the gh-pages commit (not pushed)"
fi
rm -rf "$SCAN"
log "leak grep: clean"

# ---- 8. push gh-pages only ----
if [[ "$PUSH" == 0 ]]; then
  log "--no-push: stop before push"
  exit 0
fi
git -C "$WT" push -q --force-with-lease="refs/heads/$BRANCH:$REMOTE_SHA" "$REMOTE" "$NEW_SHA:refs/heads/$BRANCH"
git fetch -q "$REMOTE" "+refs/heads/$BRANCH:refs/remotes/$REMOTE/$BRANCH"
log "pushed $BRANCH = $NEW_SHA"
