svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 820" width="100%" height="100%" style="background-color: #0b0c10; font-family: 'Inter', system-ui, sans-serif;">
  <defs>
    <linearGradient id="grad-client" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="grad-agent" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2e1065" />
      <stop offset="100%" stop-color="#172554" />
    </linearGradient>
    <linearGradient id="grad-storage" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#064e3b" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="6" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
  </defs>

  <!-- Title -->
  <text x="640" y="45" fill="#f8fafc" font-size="26" font-weight="700" text-anchor="middle" letter-spacing="-0.02em">
    Nyaya — Agent Workflow &amp; Layered Architecture
  </text>
  <text x="640" y="72" fill="#94a3b8" font-size="14" text-anchor="middle">
    Multi-Platform Governance Pipeline · 4 Specialized Agent Internal Layer Stacks
  </text>

  <!-- PLATFORM 1: CLIENT TIER (Top) -->
  <rect x="40" y="100" width="1200" height="150" rx="16" fill="url(#grad-client)" stroke="#0284c7" stroke-width="2" />
  <rect x="60" y="115" width="220" height="28" rx="6" fill="#0369a1" />
  <text x="170" y="134" fill="#ffffff" font-size="13" font-weight="700" text-anchor="middle">CLIENT &amp; GOVERNANCE TIER</text>

  <g transform="translate(60, 160)">
    <rect x="0" y="0" width="250" height="70" rx="10" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5" />
    <text x="20" y="28" fill="#38bdf8" font-size="14" font-weight="700">Next.js 16 Web Dashboard</text>
    <text x="20" y="50" fill="#cbd5e1" font-size="12">ModuleShell · Cursor · DynamicIsland</text>
  </g>

  <g transform="translate(340, 160)">
    <rect x="0" y="0" width="250" height="70" rx="10" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5" />
    <text x="20" y="28" fill="#38bdf8" font-size="14" font-weight="700">Prose &amp; Brief Ingestion</text>
    <text x="20" y="50" fill="#cbd5e1" font-size="12">Raw requirements · PDF uploads</text>
  </g>

  <g transform="translate(620, 160)">
    <rect x="0" y="0" width="280" height="70" rx="10" fill="#1e293b" stroke="#f43f5e" stroke-width="1.5" />
    <text x="20" y="28" fill="#f43f5e" font-size="14" font-weight="700">4 Human Approval Gates</text>
    <text x="20" y="50" fill="#cbd5e1" font-size="12">Baseline · Interpretation · Gap · SDLC</text>
  </g>

  <g transform="translate(930, 160)">
    <rect x="0" y="0" width="285" height="70" rx="10" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5" />
    <text x="20" y="28" fill="#38bdf8" font-size="14" font-weight="700">Artefacts &amp; Observability</text>
    <text x="20" y="50" fill="#cbd5e1" font-size="12">SRS User Stories · Token &amp; Cost Ledger</text>
  </g>

  <!-- Connectors from Tier 1 to Tier 2 -->
  <line x1="640" y1="250" x2="640" y2="285" stroke="#38bdf8" stroke-width="3" stroke-dasharray="6,4" />

  <!-- PLATFORM 2: 4 SPECIALIZED AGENTS DECOMPOSED (Middle) -->
  <rect x="40" y="285" width="1200" height="340" rx="16" fill="url(#grad-agent)" stroke="#8b5cf6" stroke-width="2" />
  <rect x="60" y="300" width="310" height="28" rx="6" fill="#7c3aed" />
  <text x="215" y="319" fill="#ffffff" font-size="13" font-weight="700" text-anchor="middle">SPECIALIZED AGENT INTERNAL LAYERS</text>

  <!-- AGENT 1: EXTRACTION AGENT (5 Layers) -->
  <g transform="translate(60, 345)">
    <rect x="0" y="0" width="270" height="260" rx="12" fill="#181824" stroke="#f59f00" stroke-width="1.5" />
    <text x="15" y="26" fill="#f59f00" font-size="15" font-weight="700">Extraction Agent</text>
    <rect x="180" y="12" width="75" height="18" rx="4" fill="#78350f" />
    <text x="217" y="25" fill="#fde68a" font-size="10" font-weight="700" text-anchor="middle">5 LAYERS</text>

    <rect x="12" y="42" width="246" height="34" rx="6" fill="#1e1e2d" stroke="#f59f00" stroke-width="1" />
    <text x="22" y="63" fill="#f8fafc" font-size="11" font-weight="600">L1: Scope &amp; Context Ingestion</text>

    <rect x="12" y="82" width="246" height="34" rx="6" fill="#1e1e2d" stroke="#f59f00" stroke-width="1" />
    <text x="22" y="103" fill="#f8fafc" font-size="11" font-weight="600">L2: EARS Grammar Transformation</text>

    <rect x="12" y="122" width="246" height="34" rx="6" fill="#1e1e2d" stroke="#f59f00" stroke-width="1" />
    <text x="22" y="143" fill="#f8fafc" font-size="11" font-weight="600">L3: Deterministic Quality Linters</text>

    <rect x="12" y="162" width="246" height="34" rx="6" fill="#1e1e2d" stroke="#f43f5e" stroke-width="1" />
    <text x="22" y="183" fill="#fda4af" font-size="11" font-weight="600">L4: Bounded Repair Loop (Max 2)</text>

    <rect x="12" y="202" width="246" height="34" rx="6" fill="#1e1e2d" stroke="#10b981" stroke-width="1" />
    <text x="22" y="223" fill="#6ee7b7" font-size="11" font-weight="600">L5: Baseline Gate 1 &amp; Safe Fallback</text>
  </g>

  <!-- AGENT 2: COMPLIANCE AGENT (6 Layers) -->
  <g transform="translate(355, 345)">
    <rect x="0" y="0" width="275" height="260" rx="12" fill="#181824" stroke="#06b6d4" stroke-width="1.5" />
    <text x="15" y="26" fill="#06b6d4" font-size="15" font-weight="700">Compliance Agent</text>
    <rect x="185" y="12" width="75" height="18" rx="4" fill="#164e63" />
    <text x="222" y="25" fill="#a5f3fc" font-size="10" font-weight="700" text-anchor="middle">6 LAYERS</text>

    <rect x="12" y="42" width="251" height="29" rx="5" fill="#1e1e2d" stroke="#06b6d4" stroke-width="1" />
    <text x="20" y="61" fill="#f8fafc" font-size="11" font-weight="600">L1: Hybrid Search (BGE + BM25)</text>

    <rect x="12" y="76" width="251" height="29" rx="5" fill="#1e1e2d" stroke="#06b6d4" stroke-width="1" />
    <text x="20" y="95" fill="#f8fafc" font-size="11" font-weight="600">L2: Rule Engine Control Seeding</text>

    <rect x="12" y="110" width="251" height="29" rx="5" fill="#1e1e2d" stroke="#06b6d4" stroke-width="1" />
    <text x="20" y="129" fill="#f8fafc" font-size="11" font-weight="600">L3: Verbatim Citation Proposal</text>

    <rect x="12" y="144" width="251" height="29" rx="5" fill="#1e1e2d" stroke="#f43f5e" stroke-width="1" />
    <text x="20" y="163" fill="#fda4af" font-size="11" font-weight="600">L4: Deterministic 3-Point Check</text>

    <rect x="12" y="178" width="251" height="29" rx="5" fill="#1e1e2d" stroke="#06b6d4" stroke-width="1" />
    <text x="20" y="197" fill="#f8fafc" font-size="11" font-weight="600">L5: Mathematical Confidence Fusion</text>

    <rect x="12" y="212" width="251" height="34" rx="5" fill="#1e1e2d" stroke="#a855f7" stroke-width="1" />
    <text x="20" y="233" fill="#d8b4fe" font-size="11" font-weight="600">L6: Tier Partition &amp; Judge Opinion</text>
  </g>

  <!-- AGENT 3: COVERAGE ENGINE (4 Layers) -->
  <g transform="translate(655, 345)">
    <rect x="0" y="0" width="265" height="260" rx="12" fill="#181824" stroke="#10b981" stroke-width="1.5" />
    <text x="15" y="26" fill="#10b981" font-size="15" font-weight="700">Coverage Engine</text>
    <rect x="175" y="12" width="75" height="18" rx="4" fill="#064e3b" />
    <text x="212" y="25" fill="#a7f3d0" font-size="10" font-weight="700" text-anchor="middle">4 LAYERS</text>

    <rect x="12" y="42" width="241" height="42" rx="6" fill="#1e1e2d" stroke="#10b981" stroke-width="1" />
    <text x="20" y="67" fill="#f8fafc" font-size="11" font-weight="600">L1: Requirement Facts Extraction</text>

    <rect x="12" y="94" width="241" height="42" rx="6" fill="#1e1e2d" stroke="#10b981" stroke-width="1" />
    <text x="20" y="119" fill="#f8fafc" font-size="11" font-weight="600">L2: Regulatory Rule Pack Scoping</text>

    <rect x="12" y="146" width="241" height="42" rx="6" fill="#1e1e2d" stroke="#10b981" stroke-width="1" />
    <text x="20" y="171" fill="#f8fafc" font-size="11" font-weight="600">L3: Deterministic Rule DSL Engine</text>

    <rect x="12" y="198" width="241" height="42" rx="6" fill="#1e1e2d" stroke="#f43f5e" stroke-width="1" />
    <text x="20" y="223" fill="#fda4af" font-size="11" font-weight="600">L4: Blocking Gaps &amp; Gate 3 Waiver</text>
  </g>

  <!-- AGENT 4: MCDA SDLC ENGINE (4 Layers) -->
  <g transform="translate(945, 345)">
    <rect x="0" y="0" width="270" height="260" rx="12" fill="#181824" stroke="#a855f7" stroke-width="1.5" />
    <text x="15" y="26" fill="#a855f7" font-size="15" font-weight="700">MCDA SDLC Engine</text>
    <rect x="180" y="12" width="75" height="18" rx="4" fill="#581c87" />
    <text x="217" y="25" fill="#f3e8ff" font-size="10" font-weight="700" text-anchor="middle">4 LAYERS</text>

    <rect x="12" y="42" width="246" height="42" rx="6" fill="#1e1e2d" stroke="#a855f7" stroke-width="1" />
    <text x="20" y="67" fill="#f8fafc" font-size="11" font-weight="600">L1: Project Factor Derivation</text>

    <rect x="12" y="94" width="246" height="42" rx="6" fill="#1e1e2d" stroke="#a855f7" stroke-width="1" />
    <text x="20" y="119" fill="#f8fafc" font-size="11" font-weight="600">L2: AHP Criteria Weighting (CR&lt;0.1)</text>

    <rect x="12" y="146" width="246" height="42" rx="6" fill="#1e1e2d" stroke="#a855f7" stroke-width="1" />
    <text x="20" y="171" fill="#f8fafc" font-size="11" font-weight="600">L3: TOPSIS Multi-Criteria Ranking</text>

    <rect x="12" y="198" width="246" height="42" rx="6" fill="#1e1e2d" stroke="#10b981" stroke-width="1" />
    <text x="20" y="223" fill="#6ee7b7" font-size="11" font-weight="600">L4: Close-Call Flag &amp; Gate 4 Sign-off</text>
  </g>

  <!-- Connectors from Tier 2 to Tier 3 -->
  <line x1="640" y1="625" x2="640" y2="655" stroke="#10b981" stroke-width="3" stroke-dasharray="6,4" />

  <!-- PLATFORM 3: PERSISTENCE & STORAGE TIER (Bottom) -->
  <rect x="40" y="655" width="1200" height="135" rx="16" fill="url(#grad-storage)" stroke="#10b981" stroke-width="2" />
  <rect x="60" y="670" width="260" height="28" rx="6" fill="#047857" />
  <text x="190" y="689" fill="#ffffff" font-size="13" font-weight="700" text-anchor="middle">STORAGE &amp; VERIFICATION SERVICES</text>

  <g transform="translate(60, 710)">
    <rect x="0" y="0" width="270" height="65" rx="10" fill="#1e293b" stroke="#10b981" stroke-width="1.5" />
    <text x="20" y="26" fill="#10b981" font-size="14" font-weight="700">PostgreSQL 16 (Relational)</text>
    <text x="20" y="47" fill="#cbd5e1" font-size="12">Projects · Requirements · Evidence · Run</text>
  </g>

  <g transform="translate(355, 710)">
    <rect x="0" y="0" width="275" height="65" rx="10" fill="#1e293b" stroke="#06b6d4" stroke-width="1.5" />
    <text x="20" y="26" fill="#06b6d4" font-size="14" font-weight="700">MinIO S3 (Object Storage)</text>
    <text x="20" y="47" fill="#cbd5e1" font-size="12">Raw Briefs · Regulatory PDFs · Artefacts</text>
  </g>

  <g transform="translate(655, 710)">
    <rect x="0" y="0" width="265" height="65" rx="10" fill="#1e293b" stroke="#a855f7" stroke-width="1.5" />
    <text x="20" y="26" fill="#a855f7" font-size="14" font-weight="700">Audit &amp; Token Ledger</text>
    <text x="20" y="47" fill="#cbd5e1" font-size="12">Immutable Gate Logs · LLM Cost (USD)</text>
  </g>

  <g transform="translate(945, 710)">
    <rect x="0" y="0" width="270" height="65" rx="10" fill="#1e293b" stroke="#f59f00" stroke-width="1.5" />
    <text x="20" y="26" fill="#f59f00" font-size="14" font-weight="700">Hybrid Vector &amp; NLI</text>
    <text x="20" y="47" fill="#cbd5e1" font-size="12">BGE Embeddings · DeBERTa Cross-Encoder</text>
  </g>
</svg>'''

with open("web/public/nyaya_agent_layers.svg", "w") as f:
    f.write(svg)

with open("/Users/devanshsharma/.gemini/antigravity-ide/brain/023eacf8-9d62-42ed-9bf1-f56c13891ff8/nyaya_agent_layers.svg", "w") as f:
    f.write(svg)

print("Exported nyaya_agent_layers.svg successfully")
