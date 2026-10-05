import json

with open("nyaya_full_architecture.excalidraw") as f:
    doc = json.load(f)

elements = doc["elements"]

# Calculate canvas bounds
min_x = min(e["x"] for e in elements) - 20
min_y = min(e["y"] for e in elements) - 20
max_x = max(e["x"] + e.get("width", 0) for e in elements) + 20
max_y = max(e["y"] + e.get("height", 0) for e in elements) + 40

width = max_x - min_x
height = max_y - min_y

svg_lines = [
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {width} {height}" width="100%" height="100%" style="background-color: #ffffff; font-family: \'Caveat\', \'Segoe Print\', cursive, sans-serif;">',
    '<defs>',
    '  <style>',
    "    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;600;700&amp;display=swap');",
    '    text { font-family: "Caveat", "Segoe Print", cursive, sans-serif; }',
    '  </style>',
    '  <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
    '    <polygon points="0 0, 10 3.5, 0 7" fill="#1e1e1e" />',
    '  </marker>',
    '  <marker id="arrowhead-blue" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
    '    <polygon points="0 0, 10 3.5, 0 7" fill="#1971c2" />',
    '  </marker>',
    '  <marker id="arrowhead-purple" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
    '    <polygon points="0 0, 10 3.5, 0 7" fill="#7048e8" />',
    '  </marker>',
    '  <marker id="arrowhead-orange" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
    '    <polygon points="0 0, 10 3.5, 0 7" fill="#f08c00" />',
    '  </marker>',
    '  <marker id="arrowhead-cyan" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">',
    '    <polygon points="0 0, 10 3.5, 0 7" fill="#0c8599" />',
    '  </marker>',
    '</defs>'
]

for el in elements:
    el_type = el["type"]
    if el_type == "rectangle":
        rx = 12 if el.get("roundness") else 0
        dash = 'stroke-dasharray="6,4"' if el.get("strokeStyle") == "dashed" else ""
        svg_lines.append(
            f'  <rect x="{el["x"]}" y="{el["y"]}" width="{el["width"]}" height="{el["height"]}" rx="{rx}" fill="{el["backgroundColor"]}" stroke="{el["strokeColor"]}" stroke-width="{el["strokeWidth"]}" {dash} />'
        )
    elif el_type == "text":
        lines = el["text"].split("\n")
        font_size = el.get("fontSize", 16)
        color = el.get("strokeColor", "#1e1e1e")
        align = el.get("textAlign", "left")
        anchor = "middle" if align == "center" else "start"
        tx = el["x"]
        ty = el["y"] + font_size
        
        svg_lines.append(f'  <text x="{tx}" y="{ty}" fill="{color}" font-size="{font_size}" text-anchor="{anchor}" font-weight="600">')
        for i, line in enumerate(lines):
            dy = f'{font_size * 1.3}px' if i > 0 else "0"
            escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            svg_lines.append(f'    <tspan x="{tx}" dy="{dy}">{escaped}</tspan>')
        svg_lines.append('  </text>')
    elif el_type == "arrow":
        x1 = el["x"]
        y1 = el["y"]
        dx, dy = el["points"][1]
        x2 = x1 + dx
        y2 = y1 + dy
        stroke = el.get("strokeColor", "#1e1e1e")
        marker = "arrowhead"
        if "#1971c2" in stroke:
            marker = "arrowhead-blue"
        elif "#7048e8" in stroke:
            marker = "arrowhead-purple"
        elif "#f08c00" in stroke:
            marker = "arrowhead-orange"
        elif "#0c8599" in stroke:
            marker = "arrowhead-cyan"
            
        svg_lines.append(
            f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{el["strokeWidth"]}" marker-end="url(#{marker})" />'
        )

svg_lines.append('</svg>')

svg_content = "\n".join(svg_lines)
with open("web/public/nyaya_architecture_excalidraw.svg", "w") as f:
    f.write(svg_content)

with open("/Users/devanshsharma/.gemini/antigravity-ide/brain/023eacf8-9d62-42ed-9bf1-f56c13891ff8/nyaya_architecture_excalidraw.svg", "w") as f:
    f.write(svg_content)

print(f"Exported SVG successfully (width={width}, height={height})")
