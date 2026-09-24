#!/usr/bin/env bash
set -euo pipefail

exhibit_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
pid_file="$exhibit_dir/.exhibit-server.pid"

if [ ! -f "$pid_file" ]; then
    echo "No running VEIL server was found."
    exit 0
fi

server_pid="$(cat "$pid_file")"
if ! [[ "$server_pid" =~ ^[0-9]+$ ]]; then
    echo "The VEIL PID file is invalid; nothing was stopped." >&2
    exit 1
fi

if ! kill -0 "$server_pid" 2>/dev/null; then
    rm -f "$pid_file"
    echo "The VEIL server was already stopped."
    exit 0
fi

command_line="$(tr '\0' ' ' < "/proc/$server_pid/cmdline" 2>/dev/null || true)"
if [[ "$command_line" != *"BDAC.exhibit.server"* ]]; then
    echo "PID $server_pid does not belong to the VEIL server; nothing was stopped." >&2
    exit 1
fi

kill "$server_pid"
for _ in {1..50}; do
    if ! kill -0 "$server_pid" 2>/dev/null; then
        rm -f "$pid_file"
        echo "VEIL was stopped."
        exit 0
    fi
    sleep 0.1
done

echo "VEIL did not stop within five seconds." >&2
exit 1
