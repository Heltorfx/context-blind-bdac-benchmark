#!/usr/bin/env bash
set -euo pipefail

port="${1:-8766}"
response="$(curl --fail --silent --show-error \
    --request POST \
    "http://127.0.0.1:${port}/api/reset")"

if [[ "$response" != *'"ok": true'* ]]; then
    echo "The VEIL server did not confirm the reset: $response" >&2
    exit 1
fi

echo "VEIL was reset. Connected users can start again."
