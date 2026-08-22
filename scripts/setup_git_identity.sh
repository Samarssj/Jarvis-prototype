#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v gh >/dev/null 2>&1; then
  printf '%s\n' 'GitHub CLI (gh) is required to configure the canonical commit identity.' >&2
  exit 1
fi

login="$(gh api user --jq '.login')"
user_id="$(gh api user --jq '.id')"

if [[ -z "$login" || -z "$user_id" || ! "$user_id" =~ ^[0-9]+$ ]]; then
  printf '%s\n' 'Unable to determine the authenticated GitHub account.' >&2
  exit 1
fi

email="${user_id}+${login}@users.noreply.github.com"
git -C "$repo_root" config user.name "$login"
git -C "$repo_root" config user.email "$email"
git -C "$repo_root" config core.hooksPath .githooks

printf 'Configured %s with %s\n' "$login" "$email"
printf 'Enabled repository hooks at %s\n' "$repo_root/.githooks"
