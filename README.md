# Edge AI Inventory Monitor

[![Tests](https://github.com/celikender/ai_inventory/actions/workflows/tests.yml/badge.svg)](https://github.com/celikender/ai_inventory/actions/workflows/tests.yml)

A Linux edge application that uses a camera, OpenCV motion detection, and Gemini vision to monitor labeled inventory bins.

## How it works

1. Create a project and shelf, then run **Setup Analyze**.
2. Gemini reads the visible bin labels and identifies the product assigned to each bin.
3. OpenCV monitors the camera for motion and waits until the scene becomes stable.
4. The stable image is sent to Gemini using the initialized bin codes.
5. Gemini estimates visible quantities and identifies the product in each bin.
6. The backend validates the response, updates SQLite, reports changes from the previous scan, and warns about possible product mismatches.

## Main features

- USB camera integration
- OpenCV motion and stability detection
- Structured Gemini vision responses
- FastAPI backend and browser interface
- SQLite inventory storage
- Scan-to-scan quantity tracking
- Wrong-bin product warnings
- Motion cooldown and scan-lock controls

## Run locally

Requirements:

- Python 3.11+
- Linux device with a compatible camera
- Gemini API key

```bash
git clone https://github.com/celikender/ai_inventory.git
cd ai_inventory

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add your GEMINI_API_KEY to .env

./run.sh
```

Open:

- Operator interface: http://localhost:8000/ui
- Inventory dashboard: http://localhost:8000/ui/dash
- API documentation: http://localhost:8000/docs

For API development without a camera, set `CAMERA_ENABLED=false` in `.env`.

## Test

```bash
python -m unittest discover -s tests
```

## Author

Developed by [**Ender Celik**](https://github.com/celikender) as part of an industrial automation, SCADA/MES, and IIoT engineering portfolio.

The custom labeled bins used in this prototype were designed and 3D-printed by Ender Celik.

## Other projects

- [vLock Digital LOTO](https://github.com/celikender/vLock-Digital-LOTO) - an Inductive Automation Ignition Perspective project demonstrating digital LOTO tracking
- [vMaint](https://vmaint.com/) - a manufacturing operations and maintenance platform
