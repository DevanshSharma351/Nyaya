"use client";

/**
 * SRS Artefacts — Software Requirements Specification & Handover Pack.
 *
 * Everything upstream exists to make these trustworthy:
 * 1. Traceability Matrix (Requirements <-> Citations <-> Controls <-> Verification)
 * 2. User Stories with formal Acceptance Criteria
 * 3. Use Cases with Preconditions, Main Flows, and Defect-Derived Exception Paths
 * 4. Risk Register with Severity, Categories, and Actionable Mitigations
 *
 * Project-linked: Automatically loads the SRS specification for the active project
 * selected from the database or history panel.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { Copy, Check, FileText, Sparkles, RefreshCw } from "lucide-react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { ProjectSelector } from "@/components/chrome/ProjectSelector";
import { useJob } from "@/components/chrome/Jobs";
import { Badge, Button, Empty, Failure, Ring } from "@/components/ui";
import { api, type Artefacts } from "@/lib/api";

const RequirementLayer = dynamic(
  () => import("@/components/scenes/RequirementLayer"),
  { ssr: false },
);

const RISK_TONE: Record<string, string> = {
  low: "var(--text-tertiary)",
  medium: "var(--accent)",
  high: "var(--review)",
  critical: "var(--gap)",
};

type Tab = "traceability" | "stories" | "cases" | "risks";

const TABS: [Tab, string][] = [
  ["traceability", "Traceability Matrix"],
  ["stories", "User Stories"],
  ["cases", "Use Cases"],
  ["risks", "Risk Register"],
];

export default function ArtefactsPage() {
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectArtefacts, setProjectArtefacts] = useState<Artefacts | null>(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showCustomPrompt, setShowCustomPrompt] = useState(false);

  // Fallback ad-hoc job runner
  const { job, run: runJob } = useJob<Artefacts>("artefacts");
  const [customText, setCustomText] = useState(job.input ?? "");
  const [tab, setTab] = useState<Tab>("traceability");

  // Load project artefacts instantly
  const loadArtefactsForProject = useCallback(async (id: string) => {
    setProjectLoading(true);
    setProjectError(null);
    try {
      const data = await api.generateArtefacts(id);
      setProjectArtefacts(data);
      sessionStorage.setItem("nyaya_project_id", id);
      setSelectedProjectId(id);
    } catch (err: unknown) {
      setProjectError((err as Error).message || "Failed to generate SRS artefacts for project");
    } finally {
      setProjectLoading(false);
    }
  }, []);

  // On mount: check sessionStorage, or load first project from API
  useEffect(() => {
    let cancelled = false;
    const saved = typeof window !== "undefined" ? sessionStorage.getItem("nyaya_project_id") : null;
    if (saved) {
      queueMicrotask(() => {
        if (!cancelled) {
          setSelectedProjectId(saved);
          loadArtefactsForProject(saved);
        }
      });
      return () => {
        cancelled = true;
      };
    }

    api.projects().then((list) => {
      if (cancelled || list.length === 0) return;
      const firstId = list[0].id;
      setSelectedProjectId(firstId);
      loadArtefactsForProject(firstId);
    }).catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [loadArtefactsForProject]);

  const handleSelectProject = (id: string) => {
    loadArtefactsForProject(id);
  };

  // Run custom model extraction
  async function runCustom() {
    if (!customText.trim()) return;
    await runJob(
      customText,
      () => api.artefacts(customText),
      (next) => ({
        label: `${next.traceability.length} requirements`,
        detail: `${Math.round(next.traceability_coverage * 100)}% fully traced`,
      }),
      { label: "Generating custom artefacts", detail: "40-100s" },
    );
  }

  // Active result is either project-derived or custom job result
  const result: Artefacts | null = projectArtefacts ?? job.result ?? null;
  const busy = projectLoading || job.state === "running";
  const error = projectError ?? job.error ?? null;

  // Copy full SRS markdown export
  const copySrsMarkdown = () => {
    if (!result) return;
    const md = [
      `# Software Requirements Specification (SRS) Handover Pack`,
      `**Project:** ${result.project}`,
      `**Generated At:** ${new Date(result.generated_at).toLocaleString()}`,
      `**Traceability Coverage:** ${Math.round(result.traceability_coverage * 100)}%`,
      ``,
      `## 1. Traceability Matrix`,
      ...result.traceability.map(
        (r) => `- **[${r.ref}]** ${r.statement}\n  - Citations: ${r.citations.join(", ") || "None"}\n  - Controls: ${r.controls.join(", ") || "None"}\n  - Gaps: ${r.gaps.join(", ") || "None"}`
      ),
      ``,
      `## 2. User Stories & Acceptance Criteria`,
      ...result.user_stories.map(
        (s) => `### Story ${s.ref}\n**Text:** ${s.text}\n**Acceptance Criteria:**\n${s.acceptance_criteria.map((c) => `  - [ ] ${c}`).join("\n")}`
      ),
      ``,
      `## 3. Use Cases`,
      ...result.use_cases.map(
        (u) => `### Use Case ${u.ref}: ${u.name}\n**Actor:** ${u.actor}\n**Precondition:** ${u.precondition}\n**Flow:**\n${u.main_flow.map((step, idx) => `  ${idx + 1}. ${step}`).join("\n")}\n**Postcondition:** ${u.postcondition}`
      ),
      ``,
      `## 4. Risk Register`,
      ...result.risks.map(
        (rk) => `- **[${rk.ref}] [${rk.level.toUpperCase()}]** ${rk.description}\n  - Owner: ${rk.owner} | Category: ${rk.category}\n  - Treatment: ${rk.treatment}`
      ),
    ].join("\n");

    navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <ModuleShell
      pathname="/artefacts"
      eyebrow="SRS & Handover Artefacts"
      title="Software Requirements Specification (SRS)"
      lede="The formal engineering handover pack: Traceability Matrix, User Stories with Acceptance Criteria, Use Cases with Exception Flows, and Risk Register — deterministically derived from verified project requirements."
      scene={<RequirementLayer requirements={null} />}
      sceneCaption="These four artefacts represent the completed Software Requirements Specification (SRS) handover pack. Everything is cross-linked directly to statutory citations and testable criteria."
    >
      {/* Unified Project Selector Bar */}
      <Block>
        <ProjectSelector
          activeModule="artefacts"
          currentProjectId={selectedProjectId}
          onSelectProject={handleSelectProject}
        />
      </Block>

      {/* SRS Handover Pack Header with Actions */}
      {result && (
        <Block>
          <div className="glass-raised p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <FileText size={20} className="text-[var(--accent)]" />
                <h3 className="headline text-lg font-semibold">SRS Handover Pack Active</h3>
                <Badge tone="var(--confirmed)">Ready for Engineering Review</Badge>
              </div>
              <p className="caption text-[var(--text-secondary)] mt-1 mb-0 max-w-2xl">
                Generated from verified requirements. Includes {result.traceability.length} requirements, {result.user_stories.length} user stories, {result.use_cases.length} use cases, and {result.risks.length} registered risks.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="quiet"
                onClick={() => selectedProjectId && loadArtefactsForProject(selectedProjectId)}
                disabled={busy}
              >
                <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
                Re-generate
              </Button>
              <Button onClick={copySrsMarkdown}>
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "Copied SRS!" : "Copy SRS Document"}
              </Button>
            </div>
          </div>
        </Block>
      )}

      {error && (
        <Block>
          <Failure message={error} />
        </Block>
      )}

      {busy && (
        <Block>
          <div className="glass p-5">
            <div className="sheen" style={{ height: 10, borderRadius: 5 }} />
            <div className="caption mt-3">
              Deriving SRS handover pack (Traceability, Stories, Use Cases, Risk Register)…
            </div>
          </div>
        </Block>
      )}

      {!busy && !error && !result && (
        <Block>
          <Empty>Select a project from the selector above to view its Software Requirements Specification.</Empty>
        </Block>
      )}

      {result && !busy && (
        <>
          {/* Traceability Overview Banner */}
          <Block>
            <div className="glass flex flex-wrap items-center gap-6 p-6">
              <Ring
                value={result.traceability_coverage}
                size={84}
                tone={
                  result.traceability_coverage > 0.7
                    ? "var(--confirmed)"
                    : result.traceability_coverage > 0.3
                      ? "var(--review)"
                      : "var(--gap)"
                }
              />
              <div style={{ maxWidth: 540 }}>
                <div className="headline">Traceability Coverage Ratio</div>
                <p className="caption mt-1 mb-0">
                  The share of requirements with complete end-to-end traceability (Statutory Citation &rarr; Control Mapping &rarr; Specification &rarr; Verification Criteria).
                </p>
              </div>
            </div>
          </Block>

          {/* Artefact Type Tabs */}
          <Block>
            <div className="flex flex-wrap gap-2">
              {TABS.map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className="body cursor-pointer transition-all"
                  style={{
                    background: tab === key ? "var(--accent)" : "var(--surface)",
                    color: tab === key ? "var(--accent-ink)" : "var(--text-secondary)",
                    border: "1px solid var(--hairline)",
                    borderRadius: 999,
                    padding: "7px 16px",
                    fontWeight: tab === key ? 600 : 500,
                    fontSize: "0.875rem",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </Block>

          {/* TAB 1: Traceability Matrix */}
          {tab === "traceability" && (
            <Block>
              <div className="caption mb-3 text-[var(--text-secondary)]">
                Bidirectional traceability matrix showing statutory citations, security controls, and verification criteria for each requirement.
              </div>
              {result.traceability.map((row, i) => (
                <div
                  key={row.ref}
                  className="rise glass mb-3 p-5"
                  style={{
                    animationDelay: `${i * 0.04}s`,
                    borderLeft: `3px solid ${
                      row.gaps.length ? "var(--review)" : "var(--confirmed)"
                    }`,
                  }}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="mono font-semibold">
                      {row.ref}
                    </span>
                    {row.citations.map((c) => (
                      <Badge key={c} tone="var(--clause)">
                        Citation: {c}
                      </Badge>
                    ))}
                    {row.controls.map((c) => (
                      <Badge key={c} tone="var(--confirmed)">
                        Control: {c}
                      </Badge>
                    ))}
                    {row.gaps.map((g) => (
                      <Badge key={g} tone="var(--review)">
                        Gap: {g}
                      </Badge>
                    ))}
                  </div>
                  <p className="body m-0 font-medium">{row.statement}</p>
                  {row.source_quote && (
                    <div
                      className="caption mt-2"
                      style={{
                        borderLeft: "2px solid var(--hairline)",
                        paddingLeft: 10,
                        fontStyle: "italic",
                      }}
                    >
                      Source Quote: &ldquo;{row.source_quote}&rdquo;
                    </div>
                  )}
                  {row.verification.length > 0 && (
                    <div className="mt-3">
                      <span className="caption font-semibold text-[var(--text)]">Verification Acceptance Criteria:</span>
                      <ul className="caption mt-1" style={{ paddingLeft: 18, margin: 0 }}>
                        {row.verification.map((v) => (
                          <li key={v}>{v}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </Block>
          )}

          {/* TAB 2: User Stories */}
          {tab === "stories" && (
            <Block>
              <div className="caption mb-3 text-[var(--text-secondary)]">
                Formal Agile user stories with explicit acceptance criteria for engineering sprints.
              </div>
              {result.user_stories.map((story, i) => (
                <div
                  key={story.ref}
                  className="rise glass mb-3 p-5"
                  style={{ animationDelay: `${i * 0.04}s` }}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="mono font-semibold">
                      {story.ref}
                    </span>
                    {story.trigger && <Badge tone="var(--accent)">Event-Driven</Badge>}
                  </div>
                  <p className="body m-0 font-medium" style={{ fontSize: "0.95rem" }}>
                    {story.text}
                  </p>
                  {story.trigger && (
                    <p className="caption mt-2 mb-0 text-[var(--text-secondary)]">
                      <strong>Trigger Condition:</strong> {story.trigger}
                    </p>
                  )}
                  {story.acceptance_criteria.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-[var(--hairline)]">
                      <div className="caption font-semibold mb-1 text-[var(--text)]">
                        Acceptance Criteria (Checklist):
                      </div>
                      <ul className="caption space-y-1" style={{ paddingLeft: 18, margin: 0 }}>
                        {story.acceptance_criteria.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </Block>
          )}

          {/* TAB 3: Use Cases */}
          {tab === "cases" && (
            <Block>
              <div className="caption mb-3 text-[var(--text-secondary)]">
                Detailed use case specifications with primary actor, step-by-step main flow, and defect-derived exception paths.
              </div>
              {result.use_cases.map((useCase, i) => (
                <div
                  key={useCase.ref}
                  className="rise glass mb-4 p-5"
                  style={{ animationDelay: `${i * 0.04}s` }}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="mono font-semibold">
                      {useCase.ref}
                    </span>
                    <Badge tone="var(--accent)">Actor: {useCase.actor}</Badge>
                  </div>
                  <div className="headline font-bold text-base">{useCase.name}</div>
                  <div className="mt-2 text-xs">
                    <strong className="text-[var(--text)]">Precondition:</strong>{" "}
                    <span className="text-[var(--text-secondary)]">{useCase.precondition}</span>
                  </div>

                  <div className="mt-3">
                    <strong className="text-xs text-[var(--text)]">Main Scenario Flow:</strong>
                    <ol className="caption mt-1.5 space-y-1" style={{ paddingLeft: 18, margin: 0 }}>
                      {useCase.main_flow.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  </div>

                  <div className="mt-2 text-xs">
                    <strong className="text-[var(--text)]">Postcondition:</strong>{" "}
                    <span className="text-[var(--text-secondary)]">{useCase.postcondition}</span>
                  </div>

                  {useCase.exceptions.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-[var(--hairline)]">
                      <div className="caption font-semibold mb-1" style={{ color: "var(--review)" }}>
                        Exception Flows (Derived from Defect Analysis):
                      </div>
                      <ul className="caption space-y-1" style={{ paddingLeft: 18, margin: 0 }}>
                        {useCase.exceptions.map((e) => (
                          <li key={e}>{e}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </Block>
          )}

          {/* TAB 4: Risk Register */}
          {tab === "risks" && (
            <Block>
              <div className="caption mb-3 text-[var(--text-secondary)]">
                Compliance, security, and operational risk register with assigned ownership and mitigation treatments.
              </div>
              {result.risks.map((risk, i) => (
                <div
                  key={risk.ref}
                  className="rise glass mb-3 p-5"
                  style={{
                    animationDelay: `${i * 0.04}s`,
                    borderLeft: `3px solid ${RISK_TONE[risk.level] ?? "var(--hairline)"}`,
                  }}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="mono font-semibold">
                      {risk.ref}
                    </span>
                    <Badge tone={RISK_TONE[risk.level]}>{risk.level.toUpperCase()}</Badge>
                    <Badge>Category: {risk.category}</Badge>
                    <Badge>Owner: {risk.owner}</Badge>
                  </div>
                  <p className="body m-0 font-medium">{risk.description}</p>
                  <div className="caption mt-2.5 p-2 rounded-lg bg-[var(--surface-raised)] border border-[var(--hairline)]">
                    <strong className="text-[var(--text)]">Mitigation / Treatment:</strong> {risk.treatment}
                  </div>
                </div>
              ))}
            </Block>
          )}

          {/* Open Issues & Assumptions */}
          {(result.open_issues.length > 0 || result.assumptions.length > 0) && (
            <Block title="Open Issues & Architectural Assumptions">
              <div className="glass p-5">
                {result.open_issues.length > 0 && (
                  <div className="mb-4">
                    <div className="headline mb-1 font-semibold" style={{ color: "var(--review)" }}>
                      Open Issues
                    </div>
                    <ul className="caption space-y-1" style={{ paddingLeft: 18, margin: 0 }}>
                      {result.open_issues.map((issue) => (
                        <li key={issue}>{issue}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {result.assumptions.length > 0 && (
                  <div>
                    <div className="headline mb-1 font-semibold">Project Assumptions</div>
                    <ul className="caption space-y-1" style={{ paddingLeft: 18, margin: 0 }}>
                      {result.assumptions.map((assumption) => (
                        <li key={assumption}>{assumption}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </Block>
          )}

          {/* Architectural Rationale */}
          <Block>
            <Rationale>
              Nothing here is hand-waved prose. Statements are the ones that passed
              the EARS syntax, ambiguity, and unsupported-quantity checks; acceptance
              criteria are the extracted ones; exception paths on a use case are
              the detected defects rather than invented failure modes.
              <p className="mt-2 mb-0">
                The beneficiary in each story comes from the requirement&rsquo;s
                categories, not from its wording, and regulatory wins over
                functional when a requirement is both: the story is written for
                whoever will be asked to sign it off.
              </p>
            </Rationale>
          </Block>
        </>
      )}

      {/* Ad-hoc Custom Input Accordion */}
      <Block>
        <div className="mt-4 pt-4 border-t border-[var(--hairline)]">
          <button
            type="button"
            onClick={() => setShowCustomPrompt(!showCustomPrompt)}
            className="caption text-[var(--text-tertiary)] hover:text-[var(--text)] inline-flex items-center gap-1.5 transition-colors"
          >
            <Sparkles size={13} />
            {showCustomPrompt ? "Hide Custom Text Generator" : "Run Custom Text Generator (Slow LLM Mode)"}
          </button>

          {showCustomPrompt && (
            <div className="glass-raised p-6 mt-3 rounded-xl border border-[var(--hairline)]">
              <label className="caption mb-2 block font-medium">Custom Stakeholder Input Prose</label>
              <textarea
                value={customText}
                onChange={(event) => setCustomText(event.target.value)}
                rows={3}
                placeholder="Paste ad-hoc brief prose to generate standalone SRS artefacts without a project..."
                className="body w-full rounded-xl border border-[var(--hairline)] bg-[var(--bg-inset)] p-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--focus)]"
              />
              <div className="mt-3 flex items-center gap-3">
                <Button onClick={runCustom} disabled={busy || !customText.trim()}>
                  {busy ? "Generating…" : "Run Custom LLM Extraction"}
                </Button>
                <span className="caption text-[var(--text-tertiary)]">Expect 40–100 seconds</span>
              </div>
            </div>
          )}
        </div>
      </Block>
    </ModuleShell>
  );
}
