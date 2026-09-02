#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <github-repo-url> <branch> <destination>" >&2
  exit 2
fi

REPO_URL=$1
REF=$2
DEST=$3

rm -rf "$DEST"
mkdir -p "$DEST"

if GIT_TERMINAL_PROMPT=0 git clone --branch "$REF" --single-branch "$REPO_URL" "$DEST"; then
  echo "OK: fetched app source with git clone into $DEST"
  exit 0
fi

echo "WARNING: git clone failed; trying the public GitHub codeload archive fallback." >&2

if [[ ! "$REPO_URL" =~ ^https://github\.com/([^/]+)/([^/]+)$ ]]; then
  echo "FATAL: archive fallback supports only https://github.com/<owner>/<repo>.git URLs." >&2
  exit 1
fi

OWNER=${BASH_REMATCH[1]}
REPO=${BASH_REMATCH[2]}
REPO=${REPO%.git}
if [[ -z "$OWNER" || -z "$REPO" ]]; then
  echo "FATAL: could not derive a GitHub owner and repository from $REPO_URL" >&2
  exit 1
fi

# Git branch names may contain slashes; encode them so they remain one URL path value.
ENCODED_REF=${REF//\//%2F}
ARCHIVE_URL="https://codeload.github.com/$OWNER/$REPO/tar.gz/refs/heads/$ENCODED_REF"
ARCHIVE_PATH=$(mktemp /tmp/byod-app-source.XXXXXX.tar.gz)
trap 'rm -f "$ARCHIVE_PATH"' EXIT

rm -rf "$DEST"
mkdir -p "$DEST"
if ! curl -fL --retry 3 --retry-delay 2 "$ARCHIVE_URL" -o "$ARCHIVE_PATH"; then
  echo "FATAL: GitHub archive download failed after git clone also failed." >&2
  exit 1
fi
tar -xzf "$ARCHIVE_PATH" --strip-components=1 -C "$DEST"

if ! test -f "$DEST/deploy/stage_x_ubuntu_pilot/scripts/01_one_deploy_from_vps_config.sh"; then
  echo "FATAL: downloaded archive does not contain the expected Stage XII deploy script." >&2
  exit 1
fi

echo "OK: fetched app source from the GitHub codeload archive into $DEST"
