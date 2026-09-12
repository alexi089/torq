#!/usr/bin/env bash
# Usage: source scripts/test-env.sh   (local Supabase must be running in $SIDEAPP_DIR)
set -euo pipefail
SIDEAPP_DIR="${SIDEAPP_DIR:-$HOME/sideapp}"
eval "$(cd "$SIDEAPP_DIR" && supabase status -o env \
  | grep -E '^(API_URL|DB_URL|SERVICE_ROLE_KEY)=' )"
export DATABASE_URL="$DB_URL"
export SUPABASE_URL="$API_URL"
export SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY"
export SIGNING_KEYS_PATH="$SIDEAPP_DIR/supabase/signing_keys.json"
