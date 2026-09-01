def extract_json_array(text: str) -> str:
    """Extract the first balanced JSON array from a model response."""
    if not text:
        return ""

    value = text.strip()
    start = value.find("[")
    if start == -1:
        return ""

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(value)):
        char = value[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return value[start : index + 1]

    return ""
