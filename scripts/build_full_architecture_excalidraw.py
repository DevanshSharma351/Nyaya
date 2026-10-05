import json
import uuid
import random

elements = []

def add_rect(x, y, w, h, stroke="#1e1e1e", bg="transparent", stroke_w=1, style="solid", stroke_style="solid", roughness=1):
    el_id = "rect_" + str(uuid.uuid4())[:8]
    el = {
        "id": el_id,
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": bg,
        "fillStyle": style,
        "strokeWidth": stroke_w,
        "strokeStyle": stroke_style,
        "roughness": roughness,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": random.randint(10000, 999999),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1728000000000,
        "link": None,
        "locked": False
    }
    elements.append(el)
    return el_id

def add_text(x, y, text, font_size=16, stroke="#1e1e1e", align="center", font_family=1):
    el_id = "text_" + str(uuid.uuid4())[:8]
    lines = text.split("\n")
    line_h = font_size * 1.3
    h = len(lines) * line_h
    w = max(len(l) for l in lines) * (font_size * 0.58)
    
    el = {
        "id": el_id,
        "type": "text",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": random.randint(10000, 999999),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1728000000000,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": font_size,
        "fontFamily": font_family,
        "textAlign": align,
        "verticalAlign": "top",
        "baseline": font_size,
        "containerId": None,
        "originalText": text,
        "lineHeight": 1.25
    }
    elements.append(el)
    return el_id

def add_arrow(x1, y1, x2, y2, stroke="#1e1e1e", stroke_w=1, stroke_style="solid"):
    el_id = "arrow_" + str(uuid.uuid4())[:8]
    dx = x2 - x1
    dy = y2 - y1
    el = {
        "id": el_id,
        "type": "arrow",
        "x": x1,
        "y": y1,
        "width": abs(dx),
        "height": abs(dy),
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": stroke_w,
        "strokeStyle": stroke_style,
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 2},
        "seed": random.randint(10000, 999999),
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1728000000000,
        "link": None,
        "locked": False,
        "points": [[0, 0], [dx, dy]],
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": "arrow"
    }
    elements.append(el)
    return el_id

# Header
add_text(480, 25, "Nyaya — Full Architecture", font_size=28, stroke="#1e1e1e", align="center")
add_text(350, 65, "Deterministic EARS · Adversarial Compliance Grounding · 4 Durable Human Gates · PostgreSQL", font_size=14, stroke="#495057", align="center")

# TIER 1: CLIENT (Blue)
add_rect(40, 100, 1220, 140, stroke="#1971c2", bg="#e7f5ff", stroke_w=2)
add_text(55, 110, "CLIENT — no untracked prompts · durable session keys · Next.js 16", font_size=15, stroke="#1864ab", align="left")

client_pills = [
    ("Browser\nNext.js 16 · React 19\nModuleShell · Cursor", 55),
    ("Brief Ingestion\nstakeholder prose\nraw text / PDF upload", 255),
    ("Requirements\nEARS obligations\ndefects & linters", 455),
    ("Workflow & Gates\n5-Stage StateGraph\n4 durable checkpoints", 655),
    ("Compliance\nRBI-MD-KYC search\nverbatim quotes", 855),
    ("Artefacts & SDLC\nAHP & TOPSIS SDLC\nSRS user stories", 1055),
]
for text, px in client_pills:
    add_rect(px, 140, 185, 85, stroke="#339af0", bg="#ffffff", stroke_w=1)
    add_text(px + 10, 150, text, font_size=13, stroke="#1c7ed6", align="left")

# Down arrow from Client to Orchestrator
add_arrow(650, 240, 650, 275, stroke="#1971c2", stroke_w=2)
add_text(660, 250, "POST /api/workflow/run", font_size=12, stroke="#1864ab", align="left")

# TIER 2: LANGGRAPH SUPERVISOR (Purple)
add_rect(40, 280, 1220, 175, stroke="#7048e8", bg="#f3f0ff", stroke_w=2)
add_text(55, 290, "LANGGRAPH SUPERVISOR — explicit stategraph · durable checkpoints · human interrupt gates", font_size=15, stroke="#5f3dc4", align="left")

stages = [
    ("1 Ingest & Extract\nEARS rewrite\nmodel proposes", 55, "#845ef7", "#ffffff"),
    ("2 Quality Linters\nEARS · lexicon\nquantities · repair", 225, "#845ef7", "#ffffff"),
    ("Gate 1: Baseline\nhuman clearance\nelevated risk flag", 395, "#e03131", "#ffe3e3"),
    ("3 Compliance\ndense + BM25 search\nDeBERTa NLI entail", 565, "#845ef7", "#ffffff"),
    ("Gate 2: Interp\ncompliance sign-off\nTier 2 review bands", 735, "#e03131", "#ffe3e3"),
    ("4 Coverage & MCDA\nYAML rule packs (IN)\nTOPSIS SDLC ranking", 905, "#845ef7", "#ffffff"),
    ("Gate 3 & 4 + Persist\ngap waiver & SDLC\nnode_persist to DB", 1075, "#2f9e44", "#d3f9d8"),
]

for i, (text, sx, stroke_c, bg_c) in enumerate(stages):
    add_rect(sx, 325, 145, 115, stroke=stroke_c, bg=bg_c, stroke_w=1.5)
    add_text(sx + 8, 335, text, font_size=12, stroke=stroke_c if "Gate" in text else "#3b5bdb", align="left")
    if i < len(stages) - 1:
        add_arrow(sx + 145, 380, sx + 170, 380, stroke="#7048e8", stroke_w=1.5)

# Down arrows from supervisor to agents
add_arrow(310, 455, 310, 485, stroke="#f08c00", stroke_w=2)
add_arrow(950, 455, 950, 485, stroke="#0c8599", stroke_w=2)

# TIER 3 LEFT: EXTRACTION & REPAIR ENGINE (Orange)
add_rect(40, 485, 595, 230, stroke="#f08c00", bg="#fff9db", stroke_w=2)
add_text(55, 495, "EXTRACTION & REPAIR ENGINE — bounded to 2 attempts", font_size=15, stroke="#d9480f", align="left")

extract_detail = (
    "Deterministic Quality Linters (offline, zero-cost):\n"
    " • ears.analyse: event/state/ubiquitous arity & compound splitting\n"
    " • lexicon.scan: weak-word lexicon (rapidly, robust, seamless, etc.)\n"
    " • quantities: flags numbers not in source text (anti-hallucination)\n"
    " • provenance: checks quoted_source appears verbatim in input text\n\n"
    "Bounded Repair Loop:\n"
    " • feeds back line-level defect & remedy to model; max 2 rounds\n"
    " • safe degraded fallback: preserves defects rather than inventing"
)
add_text(55, 525, extract_detail, font_size=12.5, stroke="#212529", align="left")

# TIER 3 LEFT BOTTOM: MCDA SDLC DECISION ENGINE (Yellow)
add_rect(40, 730, 595, 215, stroke="#f59f00", bg="#fff3bf", stroke_w=2)
add_text(55, 740, "MCDA SDLC DECISION ENGINE — AHP & TOPSIS", font_size=15, stroke="#d9480f", align="left")

mcda_detail = (
    "AHP (Analytic Hierarchy Process):\n"
    " • pairwise comparison matrix for team, governance, criticality\n"
    " • Consistency Ratio (CR < 0.1): validates mathematical rigor\n\n"
    "TOPSIS Multi-Criteria Decision Analysis:\n"
    " • ranks Waterfall, Spiral, V-Model, Agile against ideal solution\n"
    " • close-call detection: flags when top-2 models within 3% margin\n"
    " • derived factors: volatility, concurrency, security, team size"
)
add_text(55, 770, mcda_detail, font_size=12.5, stroke="#212529", align="left")

# TIER 3 RIGHT TOP: ADVERSARIAL COMPLIANCE GROUNDING (Cyan)
add_rect(660, 485, 600, 275, stroke="#0c8599", bg="#e6fcf5", stroke_w=2)
add_text(675, 495, "ADVERSARIAL COMPLIANCE GROUNDING — 3-point verification", font_size=15, stroke="#087f5b", align="left")

comp_detail = (
    "Hybrid Retrieval Engine:\n"
    " • dense BGE-small-en (512d) + BM25 keyword + cross-encoder rerank\n\n"
    "Deterministic 3-Point Grounding Check:\n"
    " 1. Clause exists in versioned DB (no hallucinated citations)\n"
    " 2. Quoted text matches clause substring verbatim\n"
    " 3. DeBERTa-v3-small-mnli evaluates semantic entailment\n\n"
    "Confidence Fusion & Tier Partitioning:\n"
    " • score = f(retrieval, NLI, quote) in [0, 1]\n"
    " • Tier 1: auto-confirmed (statutory obligation satisfied)\n"
    " • Tier 2: needs review -> routed to Gate 2 with reasoning\n"
    " • Regulatory Judge Agent: second opinion on review band (advisory)"
)
add_text(675, 525, comp_detail, font_size=12.5, stroke="#212529", align="left")

# TIER 3 RIGHT BOTTOM: COMPLIANCE COVERAGE ENGINE (Green)
add_rect(660, 775, 600, 170, stroke="#2b8a3e", bg="#ebfbee", stroke_w=2)
add_text(675, 785, "COMPLIANCE COVERAGE ENGINE — YAML Rule DSL", font_size=15, stroke="#2b8a3e", align="left")

coverage_detail = (
    "Declarative Regulatory Rule Packs (YAML):\n"
    " • evaluates requirement facts against regulations (e.g. ekyc-in.yaml)\n"
    " • checks statutory obligations: data retention, encryption, audit logs\n\n"
    "Blocking Gap Identification & Gate 3:\n"
    " • flags uncovered mandatory controls before system build\n"
    " • Human Gate 3 requires compliance officer sign-off or gap waiver"
)
add_text(675, 815, coverage_detail, font_size=12.5, stroke="#212529", align="left")

# TIER 4: PERSISTENCE & DATA STORES (Slate Gray)
add_rect(40, 960, 1220, 135, stroke="#495057", bg="#f8f9fa", stroke_w=2)
add_text(55, 970, "STORAGE & OBSERVABILITY — PostgreSQL 16 · MinIO · Token Ledger", font_size=15, stroke="#343a40", align="left")

store_boxes = [
    ("PostgreSQL 16 (Relational & Vector)\nprojects · requirements · defects\ncompliance_evidence · audit_events\npgvector embeddings", 55),
    ("MinIO S3 (Object Storage)\nraw source briefs · uploaded PDFs\nexported SRS markdown & reports", 455),
    ("Audit & Token Ledger\nper-agent prompt/completion tokens\nestimated USD cost · decision logs\nimmutable approval audit trail", 855),
]
for text, px in store_boxes:
    add_rect(px, 995, 370, 85, stroke="#adb5bd", bg="#ffffff", stroke_w=1)
    add_text(px + 10, 1005, text, font_size=12, stroke="#495057", align="left")

# TIER 5: ARCHITECTURAL INVARIANTS (Dashed footer)
add_rect(40, 1110, 1220, 60, stroke="#868e96", bg="#ffffff", stroke_w=1.5, stroke_style="dashed")
add_text(55, 1120, "Architecture Invariants: A state graph, not an autonomous swarm. In regulated compliance, agent-to-agent negotiation is a liability.\nEvery transition is checkpointed, every citation is verified against versioned text, and no run proceeds past a human gate without authorized clearance.", font_size=12, stroke="#495057", align="left")

excalidraw_doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {
        "viewBackgroundColor": "#ffffff",
        "gridSize": 20
    },
    "files": {}
}

with open("nyaya_full_architecture.excalidraw", "w") as f:
    json.dump(excalidraw_doc, f, indent=2)

print(f"Generated nyaya_full_architecture.excalidraw with {len(elements)} elements")
