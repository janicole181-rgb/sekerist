import subprocess
import time
from flask import Flask, jsonify

app = Flask(__name__)
tokens = []

@app.route('/get-token')
def get_token():
    if tokens:
        return jsonify({"token": tokens.pop(0)})
    return jsonify({"error": "No tokens"}), 404

@app.route('/stats')
def stats():
    return jsonify({"pool_size": len(tokens)})

if __name__ == "__main__":
    # Start the solver in background
    import threading
    def run_solver():
        while True:
            try:
                result = subprocess.run(
                    ["python", "mlbb_async_pydun.py"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                # Parse tokens from output and add to pool
                for line in result.stdout.split('\n'):
                    if "]" in line and len(line.strip()) > 20:
                        token = line.strip().split()[-1]
                        if len(token) > 30:
                            tokens.append(token)
                time.sleep(5)
            except:
                time.sleep(10)
    
    threading.Thread(target=run_solver, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
