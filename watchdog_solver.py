import os
import sys

# Load .env file at the absolute start of the script
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass

load_env()

import time
import subprocess
import argparse
from datetime import datetime

def log_watchdog(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WATCHDOG] {msg}", flush=True)

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Watchdog solver wrapper for mlbb_async_pydun.py")
    parser.add_argument("--storage", choices=["1", "2", "3"], default="2", help="Storage Mode: 1=Redis, 2=MongoDB, 3=File")
    parser.add_argument("--session-mode", choices=["1", "2"], default="1", help="Session Mode: 1=Persistent, 2=Fresh")
    parser.add_argument("--timeout", type=int, default=180, help="Activity timeout in seconds before restarting the solver (default: 180)")
    args = parser.parse_args()

    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mlbb_async_pydun.py")
    cmd = [sys.executable, script_path, "--storage", args.storage, "--session-mode", args.session_mode]

    run_count = 0

    while True:
        run_count += 1
        log_watchdog(f"Starting solver instance #{run_count}...")
        log_watchdog(f"Command: {' '.join(cmd)}")

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        # Run process with stdout/stderr piped
        # We run in a way that allows us to read stdout line by line with a timeout
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env
        )

        last_activity = time.time()

        try:
            # We will read from stdout in a non-blocking or timed way.
            # On Windows, select on pipes is not supported, so we read line-by-line in a loop.
            # To handle timeout without blocking forever on readline, we can use a separate thread
            # to read lines and put them into a queue, or we can check the process state.
            # Using a queue thread is extremely robust across platforms.
            import queue
            import threading

            out_queue = queue.Queue()

            def reader_thread(proc, q):
                for line in proc.stdout:
                    q.put(line)
                proc.stdout.close()

            t = threading.Thread(target=reader_thread, args=(process, out_queue), daemon=True)
            t.start()

            while True:
                # Check if process exited
                ret_code = process.poll()
                if ret_code is not None:
                    log_watchdog(f"Solver process exited with code {ret_code}.")
                    break

                try:
                    # Wait for a line with a small timeout to keep checking process state
                    line = out_queue.get(timeout=1.0)
                    print(line.rstrip('\n'), flush=True)
                    if "/min]" in line:
                        last_activity = time.time()
                except queue.Empty:
                    # Check if we exceeded the inactivity timeout
                    if time.time() - last_activity > args.timeout:
                        log_watchdog(f"Inactivity timeout ({args.timeout}s) exceeded. Restarting solver...")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            log_watchdog("Process did not terminate. Killing it...")
                            process.kill()
                        break

        except KeyboardInterrupt:
            log_watchdog("Watchdog received KeyboardInterrupt. Terminating solver process...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            log_watchdog("Exiting.")
            sys.exit(0)
        except Exception as e:
            log_watchdog(f"Error in watchdog loop: {e}")
            process.kill()

        log_watchdog("Waiting 5 seconds before restarting...")
        time.sleep(5)

if __name__ == "__main__":
    main()
