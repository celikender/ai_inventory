from ai.config import load_ai_config
from ai.gemini_client import gemini_analyze_image

cfg = load_ai_config()
model = cfg["gemini"]["model"]

prompt = """
Return ONLY valid JSON.
Detect each bin_code and product_name from the image.
Format: [{"bin_code":"A1","product_name":"Bolts","qty":12}]
If qty unknown, use null.
"""
image_path = "/home/ec/ai_inventory/storage/photos/3/1/test.jpg"


print(gemini_analyze_image(prompt, image_path, model=model))
