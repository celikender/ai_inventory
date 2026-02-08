import os
import time
import random
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


def _is_retryable_error(exc: Exception) -> bool:
    # Best-effort detection across SDK versions.
    msg = str(exc).lower()

    # Rate limit / quota
    if "429" in msg or "rate" in msg and "limit" in msg or "resource exhausted" in msg:
        return True

    # Common transient/network/server issues
    transient = [
        "timeout",
        "timed out",
        "temporarily unavailable",
        "unavailable",
        "deadline exceeded",
        "connection reset",
        "connection aborted",
        "connection error",
        "network",
        "500",
        "502",
        "503",
        "504",
        "internal error",
        "server error",
    ]
    return any(t in msg for t in transient)


def gemini_analyze_image(
    prompt: str,
    image_path: str,
    model: str,
    *,
    max_retries: int = 5,
    base_delay_s: float = 0.8,
    max_delay_s: float = 8.0,
):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in .env")

    client = genai.Client(api_key=api_key)

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                        ],
                    )
                ],
                # Optional tuning (safe defaults)
                config=types.GenerateContentConfig(
                    temperature=0.2,
                ),
            )

            if getattr(resp, "text", None):
                return resp.text

            texts = []
            for c in (getattr(resp, "candidates", []) or []):
                content = getattr(c, "content", None)
                for p in (getattr(content, "parts", []) or []):
                    t = getattr(p, "text", None)
                    if t:
                        texts.append(t)

            return "\n".join(texts).strip()

        except Exception as e:
            last_exc = e
            if attempt >= max_retries or not _is_retryable_error(e):
                raise

            # exponential backoff with jitter
            delay = min(max_delay_s, base_delay_s * (2 ** attempt))
            delay = delay * (0.7 + 0.6 * random.random())  # jitter 0.7x–1.3x
            time.sleep(delay)

    # Should never reach here, but keep for completeness
    raise last_exc if last_exc else RuntimeError("Gemini request failed unexpectedly")
