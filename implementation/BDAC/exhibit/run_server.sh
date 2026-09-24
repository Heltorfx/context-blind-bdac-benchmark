#!/usr/bin/env bash
set -euo pipefail

implementation_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exhibit_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
pid_file="$exhibit_dir/.exhibit-server.pid"

# Non-interactive WSL shells do not always load the user's Conda initialization.
for conda_profile in \
    "$HOME/miniforge3/etc/profile.d/conda.sh" \
    "$HOME/miniconda3/etc/profile.d/conda.sh" \
    "/opt/conda/etc/profile.d/conda.sh"; do
    if [ -f "$conda_profile" ]; then
        # shellcheck disable=SC1090
        . "$conda_profile"
        break
    fi
done

if ! command -v conda >/dev/null 2>&1; then
    echo "Conda was not found in WSL. Please install or initialize the sage environment." >&2
    exit 1
fi

conda activate sage
cd "$implementation_dir"

if [ -f "$pid_file" ]; then
    previous_pid="$(cat "$pid_file")"
    if [[ "$previous_pid" =~ ^[0-9]+$ ]] && kill -0 "$previous_pid" 2>/dev/null; then
        echo "The VEIL server is already running with PID $previous_pid." >&2
        exit 1
    fi
    rm -f "$pid_file"
fi

python3 -m BDAC.exhibit.server "$@" &
server_pid=$!
printf '%s\n' "$server_pid" > "$pid_file"

cleanup() {
    if [ -f "$pid_file" ] && [ "$(cat "$pid_file")" = "$server_pid" ]; then
        rm -f "$pid_file"
    fi
}
trap cleanup EXIT

set +e
wait "$server_pid"
server_status=$?
set -e

if [ "$server_status" -eq 130 ] || [ "$server_status" -eq 143 ]; then
    exit 0
fi
exit "$server_status"
