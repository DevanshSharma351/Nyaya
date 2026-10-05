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

def add_text(x, y, text, font_size=15, stroke="#1e1e1e", align="left", font_family=1):
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

def add_arrow(x1, y1, x2, y2, stroke="#1e1e1e", stroke_w=1):
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
        "strokeStyle": "solid",
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
add_text(420, 20, "Nyaya — The 8-Layer Architecture of Agentic AI", font_size=28, stroke="#1e1e1e", align="center")
add_text(320, 60, "Concrete Mapping of the Nyaya Codebase to the Industry 8-Layer Agentic AI Stack", font_size=14, stroke="#495057", align="center")

# Stack layout: 8 horizontal layers from Layer 8 down to Layer 1
y_start = 95
box_w = 1260

layers_def = [
    {
        "num": "8",
        "name": "Ops & Governance Layer",
        "stroke": "#d9480f",
        "bg": "#fff4e6",
        "pills": [
            ("Human-in-the-Loop Gates\n4 durable checkpoints: baseline, interpretation, gap, sdlc", "#e03131", "#ffe3e3"),
            ("Cost & Token Observability\nProjectUsage ledger, in/out tokens, exact USD cost tracking", "#d9480f", "#ffffff"),
            ("Trust & Provenance Enforcement\nVerbatim quote validation, unsupported quantities flagged", "#e8590c", "#ffffff"),
            ("Data Privacy & Policy Rules\nYAML policy pack enforcement (e.g. 5-year KYC retention)", "#d9480f", "#ffffff")
        ]
    },
    {
        "num": "7",
        "name": "Application Layer",
        "stroke": "#1971c2",
        "bg": "#e7f5ff",
        "pills": [
            ("Next.js 16 Web Dashboard\nModuleShell, Three.js canvas, Dynamic Island, Cursor", "#1971c2", "#ffffff"),
            ("Requirements Module (/requirements)\nEARS obligation editor, testability scoring, defect viewer", "#1971c2", "#ffffff"),
            ("Workflow Engine UI (/workflow)\n5-stage StateGraph visual pipeline, 4 gate review dialogs", "#1864ab", "#ffffff"),
            ("Downstream SRS Generator\nUser stories, use cases, risks, traceability matrix", "#1971c2", "#ffffff")
        ]
    },
    {
        "num": "6",
        "name": "Memory & Personalization Layer",
        "stroke": "#f59f00",
        "bg": "#fff9db",
        "pills": [
            ("Working Memory (WM)\nWorkflowState (in-flight requirements, unclear questions)", "#f59f00", "#ffffff"),
            ("Long-Term Memory (LM)\nPostgreSQL tables (projects, requirements, defects, evidence)", "#e67700", "#ffffff"),
            ("State Checkpointer\nLangGraph durable snapshots; resumes across server restarts", "#d9480f", "#ffe8cc"),
            ("Client Session Store\nJobsProvider in layout.tsx + sessionStorage persistence", "#f59f00", "#ffffff")
        ]
    },
    {
        "num": "5",
        "name": "Cognition & Reasoning Layer",
        "stroke": "#0c8599",
        "bg": "#e6fcf5",
        "pills": [
            ("Extraction Agent (EARS)\nEvent/state/ubiquitous parsing, single-obligation isolation", "#0c8599", "#ffffff"),
            ("Deterministic Quality Linters\nears.analyse, lexicon.scan, unsupported_quantities, provenance", "#099268", "#ffffff"),
            ("Self-Correction Repair Loop\n2-attempt targeted feedback with line spans and remedies", "#e03131", "#ffe3e3"),
            ("Adversarial Compliance Grounder\n3-point citation proof + DeBERTa NLI + Regulatory Judge", "#0c8599", "#ffffff"),
            ("MCDA SDLC Decision Reasoner\nAHP pairwise matrix (CR < 0.1) + TOPSIS model ranking", "#7048e8", "#f3f0ff")
        ]
    },
    {
        "num": "4",
        "name": "Tooling & Enrichment Layer",
        "stroke": "#e67700",
        "bg": "#fff3bf",
        "pills": [
            ("Hybrid Vector Search (RAG)\nBAAI/bge-small-en-v1.5 (512d) + BM25 keyword matching", "#e67700", "#ffffff"),
            ("Cross-Encoder Reranker\nms-marco-MiniLM-L-6-v2 contextual clause reranking", "#d9480f", "#ffffff"),
            ("NLI Verification Tool\nDeBERTa-v3-small-mnli semantic entailment classifier", "#0c8599", "#e6fcf5"),
            ("Declarative Rule Engine DSL\nYAML compliance evaluator (rules/compliance/ekyc-in.yaml)", "#2b8a3e", "#ebfbee"),
            ("MCDA Mathematical Engines\nAHP eigenvalue consistency solver & TOPSIS Euclidean ranker", "#7048e8", "#f3f0ff")
        ]
    },
    {
        "num": "3",
        "name": "Protocol Layer",
        "stroke": "#7048e8",
        "bg": "#f3f0ff",
        "pills": [
            ("Strict Pydantic JSON Schemas\nExtractionOutput, RepairOutput, ComplianceOutput, Coverage", "#7048e8", "#ffffff"),
            ("Human-to-Agent Interrupt Protocol\nLangGraph interrupt() payload serialization & resume dispatch", "#e03131", "#ffe3e3"),
            ("Model Abstraction Interface\ncomplete_structured(), complete_text(), EmbeddingProvider", "#7048e8", "#ffffff"),
            ("FastAPI OpenAPI 3.1 Gateway\nTyped REST endpoints, JSON-RPC, SSE event stream", "#5f3dc4", "#ffffff")
        ]
    },
    {
        "num": "2",
        "name": "Agent Internet Layer (Multi-Agent Mesh)",
        "stroke": "#845ef7",
        "bg": "#ede9fe",
        "pills": [
            ("LangGraph StateGraph Supervisor\nDeterministic DAG execution order; no liability swarm", "#7048e8", "#ffffff"),
            ("Agent Mesh State Routing\n_continue_or_halt conditional branching across 8 nodes", "#5f3dc4", "#ffffff"),
            ("Agent Action Handlers\nnode_extract, node_map_compliance, node_assess_coverage, etc.", "#845ef7", "#ffffff"),
            ("Thread Execution Context\nthread_id session scoping with isolated state execution", "#7048e8", "#ffffff")
        ]
    },
    {
        "num": "1",
        "name": "Infrastructure Layer",
        "stroke": "#343a40",
        "bg": "#f1f3f5",
        "pills": [
            ("Local & Cloud LLM Runtimes\nLocal Ollama (Qwen 2.5 3B/7B), Anthropic/Gemini/Groq fallbacks", "#343a40", "#ffffff"),
            ("PostgreSQL 16 with pgvector\nRelational schema + 512-dim HNSW cosine vector index", "#1864ab", "#e7f5ff"),
            ("MinIO S3 Object Storage\nRaw stakeholder briefs, uploaded PDFs, SRS exports", "#c92a2a", "#ffe3e3"),
            ("FastAPI ASGI Server & Docker\nUvicorn async event loop, Docker Compose container stack", "#343a40", "#ffffff")
        ]
    }
]

cur_y = y_start
for layer in layers_def:
    layer_num = layer["num"]
    name = layer["name"]
    stroke = layer["stroke"]
    bg = layer["bg"]
    pills = layer["pills"]
    
    # Layer container box
    h = 95
    add_rect(40, cur_y, box_w, h, stroke=stroke, bg=bg, stroke_w=2)
    
    # Left layer badge
    add_rect(55, cur_y + 12, 185, 28, stroke=stroke, bg=stroke, stroke_w=1)
    add_text(147, cur_y + 17, f"LAYER {layer_num}: {name.split()[0]}", font_size=12, stroke="#ffffff", align="center")
    add_text(250, cur_y + 17, name, font_size=15, stroke=stroke, align="left")
    
    # Pills layout inside layer
    pill_w = int((box_w - 50) / len(pills)) - 10
    start_x = 55
    for (pill_text, pill_stroke, pill_bg) in pills:
        add_rect(start_x, cur_y + 45, pill_w, 42, stroke=pill_stroke, bg=pill_bg, stroke_w=1)
        lines = pill_text.split("\n")
        title = lines[0]
        desc = lines[1] if len(lines) > 1 else ""
        add_text(start_x + 6, cur_y + 48, title, font_size=11.5, stroke=pill_stroke, align="left")
        if desc:
            add_text(start_x + 6, cur_y + 65, desc[:45], font_size=9.5, stroke="#495057", align="left")
        start_x += pill_w + 10
        
    cur_y += h + 12

# Bottom architecture summary footer
add_rect(40, cur_y + 5, box_w, 55, stroke="#495057", bg="#ffffff", stroke_w=1.5, stroke_style="dashed")
add_text(55, cur_y + 15, "Architecture Invariant: Nyaya implements all 8 layers of Agentic AI. A StateGraph (Layer 2) orchestrates specialized cognition (Layer 5) with\ntooling (Layer 4), memory (Layer 6), and protocols (Layer 3), bounded by 4 human-in-the-loop governance gates and audit ledgers (Layer 8).", font_size=12, stroke="#343a40", align="left")

doc = {
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

with open("nyaya_8_layers_agentic_architecture.excalidraw", "w") as f:
    json.dump(doc, f, indent=2)

with open("web/public/nyaya_8_layers_agentic_architecture.excalidraw", "w") as f:
    json.dump(doc, f, indent=2)

with open("/Users/devanshsharma/.gemini/antigravity-ide/brain/023eacf8-9d62-42ed-9bf1-f56c13891ff8/nyaya_8_layers_agentic_architecture.excalidraw", "w") as f:
    json.dump(doc, f, indent=2)

print(f"Generated nyaya_8_layers_agentic_architecture.excalidraw with {len(elements)} elements")
