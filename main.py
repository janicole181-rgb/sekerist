from flask import Flask, request, jsonify, render_template_string
import asyncio
import threading
import time
import os
import queue
import aiohttp
from datetime import datetime, timezone
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import random
import sys
import json

app = Flask(__name__)

# Configuration
TOKEN_EXPIRY_SECONDS = 14 * 60
POOL_TARGET = int(os.environ.get("POOL_TARGET", "100"))
NUM_WORKERS = int(os.environ.get("NUM_WORKERS", "5"))  # Reduced for Railway
API_PORT = int(os.environ.get("PORT", os.environ.get("API_PORT", "8080")))
SOLVER_TIMEOUT = float(os.environ.get("SOLVER_TIMEOUT", "30"))

# Token pool
token_pool = deque()
served_tokens = set()
pool_lock = threading.Lock()
served_lock = threading.Lock()
pool_running = threading.Event()

# Statistics
stats = {
    "total_requests": 0,
    "single_requests": 0,
    "tokens_generated": 0,
    "tokens_served": 0,
    "tokens_expired": 0,
    "generation_failures": 0,
    "active_workers": 0,
    "pool_size": 0,
    "peak_queue": 0,
    "duplicates_rejected": 0,
    "tokens_flushed": 0,
    "last_received": "---",
    "last_served": "---",
    "start_time": datetime.now(timezone.utc).isoformat(),
}
stats_lock = threading.Lock()

print(f"Starting CN31 Token Server...")
print(f"Port: {API_PORT}")
print(f"Workers: {NUM_WORKERS}")
print(f"Pool target: {POOL_TARGET}")
print(f"Python version: {sys.version}")

def is_token_fresh(entry):
    age = time.time() - entry["generated_at"]
    return age < TOKEN_EXPIRY_SECONDS

def prune_expired():
    removed = 0
    with pool_lock:
        fresh = deque()
        while token_pool:
            entry = token_pool.popleft()
            if is_token_fresh(entry):
                fresh.append(entry)
            else:
                removed += 1
        token_pool.extend(fresh)
    if removed:
        with stats_lock:
            stats["tokens_expired"] += removed
            stats["pool_size"] = len(token_pool)
    return removed

def take_token():
    prune_expired()
    with pool_lock:
        while token_pool:
            entry = token_pool.popleft()
            if not is_token_fresh(entry):
                with stats_lock:
                    stats["tokens_expired"] += 1
                continue
            token_val = entry["token"]
            with served_lock:
                if token_val in served_tokens:
                    continue
                served_tokens.add(token_val)
            with stats_lock:
                stats["tokens_served"] += 1
                stats["pool_size"] = len(token_pool)
                stats["last_served"] = datetime.now(timezone.utc).isoformat()
            return entry
    return None

def cleanup_served_tokens():
    with served_lock:
        if len(served_tokens) > 10000:
            excess = len(served_tokens) - 5000
            for _ in range(excess):
                served_tokens.pop()

def add_token_to_pool(token_value, worker_id):
    """Add one successful token to the shared web-server pool."""
    if not token_value:
        return False

    token_value = str(token_value).strip()
    if not token_value:
        return False

    with served_lock:
        if token_value in served_tokens:
            with stats_lock:
                stats["duplicates_rejected"] += 1
            return False

    entry = {
        "token": token_value,
        "generated_at": time.time(),
        "worker": worker_id,
    }

    with pool_lock:
        if any(item["token"] == token_value for item in token_pool):
            with stats_lock:
                stats["duplicates_rejected"] += 1
            return False
        token_pool.append(entry)
        pool_size = len(token_pool)

    with stats_lock:
        stats["tokens_generated"] += 1
        stats["pool_size"] = pool_size
        stats["last_received"] = datetime.now(timezone.utc).isoformat()
        if pool_size > stats["peak_queue"]:
            stats["peak_queue"] = pool_size

    print(f"[Worker {worker_id}] Token added (pool: {pool_size}/{POOL_TARGET})")
    return True

async def fast_pool_worker(worker_id):
    """Run the fast persistent-session solver loop."""
    try:
        import mlbb_async_pydun as fast_solver
        from fake_useragent import UserAgent
        from loguru import logger
        
        print(f"[Worker {worker_id}] Initializing solver...")
        
        if not fast_solver.initialize_global_model():
            print(f"[Worker {worker_id}] Model initialization failed")
            return
            
        if not fast_solver._get_py_dun163_ctx():
            print(f"[Worker {worker_id}] dun163_py backend unavailable")
            return

        try:
            ua = UserAgent().random
        except Exception:
            ua = "Mozilla/5.0"

        domain = fast_solver.DUN163_DOMAINS[
            worker_id % len(fast_solver.DUN163_DOMAINS)
        ]
        recycle_seconds = float(os.environ.get("SESSION_RECYCLE_SECONDS", "300"))

        print(f"[Worker {worker_id}] Ready with persistent async session")
        
        while pool_running.is_set():
            connector = aiohttp.TCPConnector(
                limit=1,
                ssl=False,
                enable_cleanup_closed=True,
            )
            headers = {
                "User-Agent": ua,
                "X-Forwarded-For": fast_solver.generate_random_ip(),
                "X-Real-IP": fast_solver.generate_random_ip(),
            }
            consecutive_failures = 0
            session_started = time.time()

            try:
                async with aiohttp.ClientSession(
                    connector=connector,
                    headers=headers,
                ) as session:
                    solver = fast_solver.AsyncDun163(
                        id_=fast_solver.ID,
                        referer=fast_solver.REFERER,
                        fp_h=fast_solver.FP_H,
                        ua=ua,
                        thread_id=worker_id,
                        domain=domain,
                        session=session,
                        executor=fast_solver._shared_executor,
                    )

                    ir_token = None
                    if fast_solver.USE_IRTOKEN:
                        try:
                            ir_token = await fast_solver.request_up()
                            print(f"[Worker {worker_id}] Got irToken")
                        except Exception as exc:
                            print(f"[Worker {worker_id}] irToken request failed: {exc}")

                    while (
                        pool_running.is_set()
                        and time.time() - session_started < recycle_seconds
                    ):
                        with pool_lock:
                            current_size = len(token_pool)
                        if current_size >= POOL_TARGET:
                            await asyncio.sleep(1)
                            prune_expired()
                            continue

                        with stats_lock:
                            stats["active_workers"] += 1

                        try:
                            token_value = await asyncio.wait_for(
                                solver.run(
                                    irToken=ir_token if fast_solver.USE_IRTOKEN else None,
                                    use_persistent_session=True,
                                ),
                                timeout=SOLVER_TIMEOUT,
                            )
                            if token_value:
                                consecutive_failures = 0
                                add_token_to_pool(token_value, worker_id)
                                print(f"[{worker_id}] Generated token: {token_value[:30]}...")
                            else:
                                consecutive_failures += 1
                                with stats_lock:
                                    stats["generation_failures"] += 1
                                if consecutive_failures >= 10:
                                    print(f"[Worker {worker_id}] Too many failures, recycling session")
                                    break
                        except asyncio.TimeoutError:
                            consecutive_failures += 1
                            with stats_lock:
                                stats["generation_failures"] += 1
                            if consecutive_failures >= 10:
                                break
                        except Exception as exc:
                            consecutive_failures += 1
                            with stats_lock:
                                stats["generation_failures"] += 1
                            print(f"[Worker {worker_id}] Error: {exc}")
                            if consecutive_failures >= 10:
                                break
                        finally:
                            with stats_lock:
                                stats["active_workers"] -= 1

                        cleanup_served_tokens()
                        await asyncio.sleep(0.1)
            except Exception as exc:
                print(f"[Worker {worker_id}] Session stopped: {exc}")

            if pool_running.is_set():
                await asyncio.sleep(1)
                
    except ImportError as e:
        print(f"[Worker {worker_id}] Import error: {e}")
        print(f"[Worker {worker_id}] Make sure mlbb_async_pydun.py and all dependencies exist")
        return
    except Exception as e:
        print(f"[Worker {worker_id}] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return

def pool_worker(worker_id):
    """Bridge the Flask thread pool to one persistent async solver loop."""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(fast_pool_worker(worker_id))
    except Exception as exc:
        print(f"[Worker {worker_id}] Fatal error: {exc}")

def start_pool():
    pool_running.set()
    print(f"Starting {NUM_WORKERS} workers...")
    for i in range(1, NUM_WORKERS + 1):
        t = threading.Thread(target=pool_worker, args=(i,), daemon=True)
        t.start()
        time.sleep(0.5)  # Stagger startup
    print(f"✅ Token pool started: {NUM_WORKERS} workers, target {POOL_TARGET}")

def pruner_loop():
    while pool_running.is_set():
        prune_expired()
        time.sleep(30)

# HTML Dashboard
FRONTEND_HTML = r"""
<!DOCTYPE html>
<html>
<head>
    <title>CN31 Token Server</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #e0e0e0;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #1a1a2e;
        }
        .header h1 {
            font-size: 28px;
            background: linear-gradient(135deg, #f8789c, #c77dff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .status {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 14px;
        }
        .dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #10b981;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: #14141f;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #1f1f35;
        }
        .card .label {
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .card .value {
            font-size: 32px;
            font-weight: bold;
            margin-top: 8px;
            font-variant-numeric: tabular-nums;
        }
        .card .value.rose { color: #f8789c; }
        .card .value.amber { color: #f5a623; }
        .card .value.green { color: #10b981; }
        .card .value.blue { color: #60a5fa; }
        .card .value.purple { color: #c77dff; }
        .card .value.red { color: #f87171; }
        .section {
            background: #14141f;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #1f1f35;
        }
        .section h2 {
            font-size: 18px;
            margin-bottom: 16px;
            color: #fff;
        }
        .endpoint {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: #1a1a2e;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .endpoint .method {
            font-family: monospace;
            font-weight: bold;
            color: #f5a623;
            min-width: 50px;
        }
        .endpoint .path {
            font-family: monospace;
            color: #e0e0e0;
        }
        .endpoint .desc {
            color: #888;
            margin-left: auto;
            font-size: 13px;
        }
        .btn {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(16, 185, 129, 0.3);
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .result-box {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 16px;
            margin-top: 16px;
            word-break: break-all;
            font-family: monospace;
            font-size: 14px;
            display: none;
        }
        .result-box.show { display: block; }
        .result-box .token { color: #10b981; }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #1a1a2e;
            text-align: center;
            color: #666;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 CN31 Token Server</h1>
            <div class="status">
                <div class="dot"></div>
                <span>Live</span>
                <span style="color: #666; margin-left: 10px;" id="clock"></span>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="label">Pool Size</div>
                <div class="value rose" id="pool-size">0</div>
            </div>
            <div class="card">
                <div class="label">Generated</div>
                <div class="value amber" id="generated">0</div>
            </div>
            <div class="card">
                <div class="label">Served</div>
                <div class="value green" id="served">0</div>
            </div>
            <div class="card">
                <div class="label">Workers</div>
                <div class="value blue" id="workers">0</div>
            </div>
            <div class="card">
                <div class="label">Rate</div>
                <div class="value purple" id="rate">0</div>
            </div>
            <div class="card">
                <div class="label">Uptime</div>
                <div class="value red" id="uptime">0m</div>
            </div>
        </div>

        <div class="section">
            <h2>📡 Get Token</h2>
            <button class="btn" id="fetch-btn" onclick="fetchToken()">Get Token</button>
            <div class="result-box" id="result"></div>
        </div>

        <div class="section">
            <h2>🔌 API Endpoints</h2>
            <div class="endpoint">
                <span class="method">GET</span>
                <span class="path">/get-token</span>
                <span class="desc">Get one fresh token</span>
            </div>
            <div class="endpoint">
                <span class="method">GET</span>
                <span class="path">/stats</span>
                <span class="desc">View pool statistics</span>
            </div>
            <div class="endpoint">
                <span class="method">GET</span>
                <span class="path">/health</span>
                <span class="desc">Health check</span>
            </div>
        </div>

        <div class="footer">
            CN31 Token Server • TTL 14 minutes • Auto-generating
        </div>
    </div>

    <script>
        function updateClock() {
            const now = new Date();
            document.getElementById('clock').textContent = now.toLocaleTimeString();
        }
        updateClock();
        setInterval(updateClock, 1000);

        async function fetchToken() {
            const btn = document.getElementById('fetch-btn');
            const result = document.getElementById('result');
            btn.disabled = true;
            btn.textContent = 'Fetching...';
            
            try {
                const resp = await fetch('/get-token');
                const data = await resp.json();
                if (data.token) {
                    result.innerHTML = `<div class="token">✅ ${data.token}</div>`;
                    result.className = 'result-box show';
                } else {
                    result.innerHTML = `❌ ${data.error || 'No tokens available'}`;
                    result.className = 'result-box show';
                }
            } catch (e) {
                result.innerHTML = `❌ Error: ${e.message}`;
                result.className = 'result-box show';
            }
            
            btn.disabled = false;
            btn.textContent = 'Get Token';
            refreshStats();
        }

        async function refreshStats() {
            try {
                const resp = await fetch('/stats');
                const data = await resp.json();
                document.getElementById('pool-size').textContent = data.pool_size || 0;
                document.getElementById('generated').textContent = data.tokens_generated || 0;
                document.getElementById('served').textContent = data.tokens_served || 0;
                document.getElementById('workers').textContent = data.active_workers || 0;
                
                if (data.start_time) {
                    const start = new Date(data.start_time);
                    const now = new Date();
                    const minutes = Math.floor((now - start) / 60000);
                    document.getElementById('uptime').textContent = minutes + 'm';
                    
                    const rate = minutes > 0 ? Math.round((data.tokens_generated || 0) / minutes) : 0;
                    document.getElementById('rate').textContent = rate + '/m';
                }
            } catch (e) {
                console.error('Stats error:', e);
            }
        }

        refreshStats();
        setInterval(refreshStats, 3000);
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(FRONTEND_HTML)

@app.route("/get-token", methods=["GET"])
def get_token_endpoint():
    with stats_lock:
        stats["total_requests"] += 1
        stats["single_requests"] += 1

    token_entry = take_token()
    if token_entry:
        age_seconds = int(time.time() - token_entry["generated_at"])
        return jsonify({
            "status": "success",
            "token": token_entry["token"],
            "age_seconds": age_seconds,
            "expires_in_seconds": TOKEN_EXPIRY_SECONDS - age_seconds,
            "generated_at": datetime.fromtimestamp(token_entry["generated_at"], tz=timezone.utc).isoformat(),
        })

    return jsonify({
        "status": "error",
        "error": "No fresh tokens available. Workers are generating, try again shortly.",
        "pool_size": len(token_pool),
    }), 503

@app.route("/stats", methods=["GET"])
def stats_endpoint():
    prune_expired()
    with stats_lock:
        stats["pool_size"] = len(token_pool)
        return jsonify(stats)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "pool_size": len(token_pool)})

if __name__ == "__main__":
    print(f"\n  🔐 CN31 Token Server")
    print(f"  Port: {API_PORT}")
    print(f"  Workers: {NUM_WORKERS}")
    print(f"  Pool target: {POOL_TARGET}")
    print(f"  Token expiry: {TOKEN_EXPIRY_SECONDS}s (14 min)")
    print(f"")
    print(f"  Endpoints:")
    print(f"    GET /             - Dashboard")
    print(f"    GET /get-token    - Get 1 fresh token")
    print(f"    GET /stats        - Pool statistics")
    print(f"    GET /health       - Health check")
    print(f"")

    start_pool()

    pruner_thread = threading.Thread(target=pruner_loop, daemon=True)
    pruner_thread.start()

    app.run(host="0.0.0.0", port=API_PORT, debug=False, threaded=True)
