#!/usr/bin/env bash
# Integration test for "I want to cache a username and password for a repository"
set -euo pipefail

TMP_DIR="$(mktemp -d -t gfr_cred_test_XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

export GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_GLOBAL="$TMP_DIR/gitconfig"
export GIT_TERMINAL_PROMPT=0

touch "$GIT_CONFIG_GLOBAL"

# 1. Execute decisive guide command
git config --global credential.helper cache

# 2. Assert config helper
HELPER="$(git config --global credential.helper)"
test "$HELPER" = "cache"

# 3. Store credentials
printf "protocol=https\nhost=example.invalid\nusername=testuser\npassword=secretpass\n\n" | git credential approve

# 4. Assert retrieval
OUTPUT="$(printf "protocol=https\nhost=example.invalid\n\n" | git credential fill)"
echo "$OUTPUT" | grep -q "username=testuser"
echo "$OUTPUT" | grep -q "password=secretpass"

echo "PASS: Credential caching successfully verified."
