SETUP_PROMPT = """
Return ONLY valid JSON. No markdown. No extra text.

Output format (JSON array):
[
  {"bin_code":"A-01","product_name":"Battery","description":"Panasonic 9V battery","qty":null}
]

Rules:
- Do NOT return bounding boxes.
- qty must always be null.
- Return an entry for EVERY visible bin_code.
- If product cannot be read, set product_name and description to null (still include the bin_code).
"""
SCAN_PROMPT_TEMPLATE = """
Return ONLY valid JSON (no markdown, no ```).

Known bins (do not invent new ones):
{known_bins_json}

Task:
For each known bin_code:
- If bin is empty, qty must be 0 and observed_product must be null.
- If items exist, qty must be an integer >= 1.
- observed_product should be a short name you see (example: "9V battery") or null if unsure.

Output format (JSON array):
[
  {{ "bin_code":"A-01", "qty":2, "observed_product":"9V battery" }},
  {{ "bin_code":"A-02", "qty":0, "observed_product":null }}
]

Rules:
- Only use bin_codes from known_bins_json.
- Do not return bounding boxes.
"""
