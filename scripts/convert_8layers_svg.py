import json

with open("nyaya_8_layers_agentic_architecture.excalidraw") as f:
    doc = json.load(f)

elements = doc["elements"]

min_x = min(e["x"] for e in elements) - 20
min_y = min(e["y"] for e in elements) - 20
max_x = max(e["x"] + e.get("width", 0) for e in elements) + 20
max_y = max(e["y"] + e.get("height", 0) for e in elements) + 30

width = max_x - min_x
height = max_y - min_y

svg_lines = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {width} {height}" width="100%" height="100%" style="background-color: #ffffff; font-family: \'Caveat\', \'Segoe Print\', cursive, sans-serif;">',
    '<defs>',
    '  <style>',
    "    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;600;700&amp;display=swap');",
    '    text { font-family: "Caveat", "Segoe Print", cursive, sans-serif; }',
    '  </style>',
    '</defs>'
]

for el in elements:
    el_type = el["type"]
    if el_type == "rectangle":
        rx = 10 if el.get("roundness") else 0
        dash = 'stroke-dasharray="6,4"' if el.get("strokeStyle") == "dashed" else ""
        svg_lines.append(
            f'  <rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" height="{el["height"]}" rx="{rx}" fill="{el["backgroundColor"]}" stroke="{el["strokeColor"]}" stroke-width="{el["strokeWidth"]}" {dash} />'
        )
    elif el_type == "text":
        lines = el["text"].split("\n")
        font_size = el.get("fontSize", 15)
        color = el.get("strokeColor", "#1e1e1e")
        align = el.get("textAlign", "left")
        anchor = "middle" if align == "center" else "start"
        tx = el["x"]
        ty = el["y"] + font_size
        
        svg_lines.append(f'  <text x="{tx}" y="{ty}" fill="{color}" font-size="{font_size}" text-anchor="{anchor}" font-weight="600">')
        for i, line in enumerate(lines):
            dy = f'{font_size * 1.25}px' if i > 0 else "0"
            escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            svg_lines.append(f'    <tspan x="{tx}" dy="{dy}">{escaped}</tspan>')
        svg_lines.append('  </text>')

svg_lines.append('</svg>')

svg_content = "\n".join(svg_lines)
with open("web/public/nyaya_8_layers_agentic_architecture.svg", "w") as f:
    f.write(svg_content)

with open("/Users/devanshsharma/.gemini/antigravity-ide/brain/023eacf8-9d62-42ed-9bf1-f56c13891ff8/nyaya_8_layers_agentic_architecture.svg", "w") as f:
    f.write(svg_content)

print(f"Exported nyaya_8_layers_agentic_architecture.svg successfully (w={width}, h={height})")
