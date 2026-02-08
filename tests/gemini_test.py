from ai.gemini_client import gemini_analyze_image

prompt = """
Return ONLY valid JSON.
Detect each bin_code and product_name from the image.
Format: [{"bin_code":"A1","product_name":"Bolts","qty":12}]
If qty unknown, use null.
"""

print(gemini_analyze_image(prompt, "/home/ec/ai_inventory/storage/photos/3/1/test.jpg"))
