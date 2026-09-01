import argparse
from pathlib import Path

from ai.config import load_ai_config
from ai.gemini_client import gemini_analyze_image


PROMPT = """
Return ONLY valid JSON.
Detect each bin_code and product_name from the image.
Format: [{"bin_code":"A-01","product_name":"Bolts","qty":12}]
If qty is unknown, use null.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Gemini inventory image analysis.")
    parser.add_argument("image", type=Path, help="Path to a shelf or bin image")
    args = parser.parse_args()

    if not args.image.is_file():
        parser.error(f"Image does not exist: {args.image}")

    model = load_ai_config()["gemini"]["model"]
    print(gemini_analyze_image(PROMPT, str(args.image), model=model))


if __name__ == "__main__":
    main()
