import json
import uuid
import random

def create_element(elem_type, x, y, width, height, text=None, bg_color="transparent", stroke_color="#1e1e1e", stroke_width=1, fill_style="solid", font_size=16, font_family=1, text_align="center", roundness=True, stroke_style="solid"):
    elem_id = str(uuid.uuid4())[:8]
    seed = random.randint(10000, 999999)
    base = {
        "id": elem_id,
        "type": elem_type,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": stroke_color,
        "backgroundColor": bg_color,
        "fillStyle": fill_style,
        "strokeWidth": stroke_width,
        "strokeStyle": stroke_style,
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3} if roundness else None,
        "seed": seed,
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1728000000000,
        "link": None,
        "locked": False
    }
    if elem_type == "text":
        base.update({
            "text": text,
            "fontSize": font_size,
            "fontFamily": font_family,
            "textAlign": text_align,
            "verticalAlign": "middle",
            "baseline": font_size,
            "containerId": None,
            "originalText": text,
            "lineHeight": 1.25
        })
    return base

print("Builder helper syntax OK")
