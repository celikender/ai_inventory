# Edge AI Inventory Monitor

[![Tests](https://github.com/celikender/ai_inventory/actions/workflows/tests.yml/badge.svg)](https://github.com/celikender/ai_inventory/actions/workflows/tests.yml)

A Linux edge application that uses a camera, OpenCV motion detection, and Gemini vision to monitor labeled inventory bins automatically.

The system was built around custom green-bordered bins designed and 3D-printed by **Ender Celik**. Their high-contrast identifiers, such as `A-01` and `B-02`, provide consistent visual references for the vision model.

> **Status:** Working engineering prototype. AI results are decision support and should be reviewed before they drive purchasing or production decisions.

## How it works

1. Install the application on a Linux device with a connected camera.
2. Create a project and shelf, then run **Setup Analyze**.
3. Gemini reads the visible bin identifiers and proposes the product assigned to each bin. Initial quantity remains unknown until an inventory scan.
4. OpenCV monitors the camera feed for motion and waits for the scene to become stable.
5. The application sends the stable image to Gemini using only the initialized bin codes.
6. Gemini estimates visible quantities and identifies the observed product in each bin.
7. The backend validates the response, updates SQLite, reports the change from the previous scan, and warns when a product may be in the wrong bin.

## Main features

- Motion-triggered inventory scans with stability checks, cooldowns, and scan locks
- Automatic bin initialization from visible labels
- Quantity estimation and scan-to-scan inventory movement
- Product-mismatch warnings
- Local FastAPI operator interface and dashboard
- SQLite storage with no required cloud database

## Technology

Python, FastAPI, OpenCV, NumPy, SQLite, Google Gemini, HTML, CSS, and JavaScript.

## Run locally

Requirements: Python 3.11+, Linux, a compatible camera, and a Gemini API key.

```bash
git clone https://github.com/celikender/ai_inventory.git
cd ai_inventory

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Add GEMINI_API_KEY=your_actual_key to .env

./run.sh
```

Open <http://localhost:8000/ui> for the operator interface or <http://localhost:8000/ui/dash> for the dashboard.

The Gemini key is loaded server-side from `.env`; it is not stored in the frontend or committed to GitHub.

## Project provenance

- **Developer and hardware designer:** Ender Celik
- **Evidence:** public Git commit history and automated GitHub Actions test results
- **Machine-readable authorship:** [`CITATION.cff`](CITATION.cff)
- **Security:** runtime credentials are loaded from an ignored `.env` file
## Test

```bash
python -m unittest discover -s tests
```

## Planned additions

- Publish the custom bin STL file for 3D printing
- Add photographs and screenshots from a complete working run
- Store full movement history and generate daily inventory summaries

## Author

Designed and developed by **Ender Celik** as an end-to-end industrial edge AI project combining custom hardware, computer vision, backend software, and manufacturing inventory workflows.

[vMaint](https://vmaint.com) | [GitHub](https://github.com/celikender)
