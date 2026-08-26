#!/usr/bin/env bash

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$APP_DIR/server.log"
PIDFILE="$APP_DIR/server.pid"

# Already running?
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Server is already running."
    exit 0
fi

# Background supervisor
# server.py + mlbb_async_pydun (when run standalone) are hardcoded to:
#   - Storage: SERVER ONLY (Redis + MongoDB) — all tokens pushed to server
#   - Session: Persistent Session Mode (1) — fastest connection pooling
nohup bash -c "
    cd '$APP_DIR'

    while true; do
        echo \"[\$(date)] Starting server.py\" >> '$LOG'
        python3 server.py >> '$LOG' 2>&1

        CODE=\$?
        echo \"[\$(date)] server.py stopped (exit \$CODE). Restarting in 5 seconds...\" >> '$LOG'
        sleep 5
    done
" >/dev/null 2>&1 &

echo $! > "$PIDFILE"

echo "Server started in background."
echo "24/7 auto-restart enabled."
echo "Storage: SERVER ONLY (Redis + MongoDB) | Session: Persistent (fast)"
echo "PID: $(cat "$PIDFILE")"
