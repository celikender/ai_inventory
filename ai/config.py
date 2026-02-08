from pathlib import Path
import yaml

def load_ai_config(path: str = "ai/config.yaml") -> dict:
    root = Path(__file__).resolve().parents[1]  # ~/ai_inventory
    cfg_path = (root / path).resolve()
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
