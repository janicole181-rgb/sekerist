# Yidun Fast Solver with Token Web Server

This folder contains the original fast Yidun solver together with a web
dashboard and token API. The web workers use `mlbb_async_pydun.py` directly,
including its ONNX model and pure-Python `dun163_py` backend.

It is specifically optimized for CPU deployments, such as **E2B Sandboxes**, Termux, or lightweight VMs where RAM and CPU performance are limited.

## 📁 Files Included

- **`yidun-yolov8n-cpu-int8.onnx`**: Highly optimized INT8-quantized YOLOv8n model (3.54 MB).
- **`class_mapping.json`**: Mapping table containing all 584 Yidun CAPTCHA object classes.
- **`api_image_solver_onnx.py`**: Pure-ONNX solver implementation for Type 11 (color click) CAPTCHAs.
- **`improved_question_parser.py`**: Question preprocessor and parsing logic.
- **`question_parser.py`**: Underlying standard question parser logic.
- **`net.onnx`**: Pure-ONNX Type 7 CAPTCHA (hybrid flags / SIFT) detection model.
- **`net_meta.json`**: Model anchors and class configurations for Type 7 solver.
- **`mlbb_async_pydun.py`**: Complete asynchronous bypasser pipeline running pure-Python JS cryptography logic and pure-ONNX solvers.
- **`dun163_py/`**: Pure-Python byte-for-byte replica port of Yidun JS cryptography logic.
- **`server.py`**: Flask dashboard and web API connected to the fast async solver.
- **`config.json`**: System and credentials configuration file.
- **`requirements.txt`**: Tailored lightweight dependencies for CPU/Headless environments.
- **`test_yolov8n_int8.py`**: A lightweight sanity check script to verify the model loads and initializes perfectly on CPU.

## ⚙️ Installation

Install the lightweight, CPU-specific dependencies using:

```bash
pip install -r requirements.txt
```

> [!NOTE]
> We use `opencv-python-headless` instead of `opencv-python` to avoid GUI/X11 display errors on servers and headless docker/E2B environments.

## Web server

Install dependencies and start the combined service:

```bash
pip install -r requirements.txt
python server.py
```

`entrypoint.sh` runs the same command. The server listens on `PORT` when
provided, or port `8080` locally.

Endpoints:

- `GET /` — web dashboard
- `GET /get-token` — remove and return one fresh token
- `GET /stats` — pool and generation statistics
- `GET /health` — health check

The web server defaults to the fast solver's 30 async workers and a 100-token
pool. Tune them with environment variables:

```bash
PORT=8080 NUM_WORKERS=30 POOL_TARGET=100 python server.py
```

## 🚀 How to Run the standalone solver

1. Navigate to this directory:
   ```bash
   cd yidun_int8_yolov8n
   ```

2. Make sure your credentials and configurations are correctly configured in `config.json`.

3. Run the validation/test script to confirm the model loads successfully:
   ```bash
   python test_yolov8n_int8.py
   ```

4. Launch the asynchronous bypasser:
   ```bash
   python mlbb_async_pydun.py
   ```
