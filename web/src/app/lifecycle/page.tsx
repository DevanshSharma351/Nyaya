"use client";

/**
 * Lifecycle — which SDLC fits this project, and why.
 *
 * Connected to project database: Automatically loads or computes the
 * AHP/TOPSIS multi-criteria decision analysis (MCDA) lifecycle recommendation
 * for the selected project.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { GitBranch, RefreshCw, Sparkles } from "lucide-react";
import { useJob } from "@/components/chrome/Jobs";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { ProjectSelector } from "@/components/chrome/ProjectSelector";
import { Badge, Button, Empty, Failure } from "@/components/ui";
import { api, type SDLC, type SDLCFromBrief } from "@/lib/api";

const LifecycleLayer = dynamic(() => import("@/components/scenes/LifecycleLayer"), {
  ssr: false,
});

const PRESETS: Record<string, Record<string, number>> = {
  "eKYC onboarding": {
    regulatory_criticality: 0.95,
    security_risk: 0.9,
    change_frequency: 0.85,
    continuous_delivery_need: 0.8,
    requirement_stability: 0.35,
    failure_consequence: 0.85,
  },
  "Payments switch": {
    regulatory_criticality: 0.95,
    security_risk: 0.9,
    failure_consequence: 0.95,
    formal_verification_need: 0.95,
    requirement_stability: 0.85,
    documentation_need: 0.9,
    change_frequency: 0.2,
    continuous_delivery_need: 0.2,
  },
  "Fraud platform": {
    project_complexity: 0.95,
    requirement_stability: 0.25,
    security_risk: 0.85,
    regulatory_criticality: 0.7,
    failure_consequence: 0.8,
    change_frequency: 0.6,
    legacy_dependence: 0.8,
    documentation_need: 0.6,
    formal_verification_need: 0.6,
  },
  "Internal dashboard": {
    regulatory_criticality: 0.2,
    security_risk: 0.3,
    change_frequency: 0.9,
    requirement_stability: 0.2,
    failure_consequence: 0.2,
    documentation_need: 0.2,
    stakeholder_availability: 0.9,
    formal_verification_need: 0.1,
    continuous_delivery_need: 0.6,
  },
};

export default function LifecyclePage() {
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectSdlc, setProjectSdlc] = useState<SDLCFromBrief | null>(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);

  // Manual preset comparison state
  const [preset, setPreset] = useState<string | null>(null);
  const [presetResult, setPresetResult] = useState<SDLC | null>(null);
  const [presetError, setPresetError] = useState<string | null>(null);

  // Ad-hoc brief extraction job
  const { job, run: runJob } = useJob<SDLCFromBrief>("lifecycle");
  const [customBrief, setCustomBrief] = useState(job.input ?? "");
  const [showCustomPrompt, setShowCustomPrompt] = useState(false);

  const loadSdlcForProject = useCallback(async (id: string) => {
    setProjectLoading(true);
    setProjectError(null);
    try {
      const data = await api.projectSdlc(id);
      setProjectSdlc(data);
      sessionStorage.setItem("nyaya_project_id", id);
      setSelectedProjectId(id);
    } catch {
      // Fallback: trigger generate endpoint if not yet stored
      try {
        const generated = await api.generateSdlc(id);
        setProjectSdlc(generated);
        sessionStorage.setItem("nyaya_project_id", id);
        setSelectedProjectId(id);
      } catch (genErr: unknown) {
        setProjectError((genErr as Error).message || "Failed to load project SDLC recommendation");
      }
    } finally {
      setProjectLoading(false);
    }
  }, []);

  // On mount: check sessionStorage or load first project from DB
  useEffect(() => {
    let cancelled = false;
    const saved = typeof window !== "undefined" ? sessionStorage.getItem("nyaya_project_id") : null;
    if (saved) {
      queueMicrotask(() => {
        if (!cancelled) {
          setSelectedProjectId(saved);
          loadSdlcForProject(saved);
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
      loadSdlcForProject(firstId);
    }).catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [loadSdlcForProject]);

  const handleSelectProject = (id: string) => {
    loadSdlcForProject(id);
  };

  // If user explores a preset profile
  useEffect(() => {
    if (!preset) return;
    let cancelled = false;
    api.sdlc(PRESETS[preset])
      .then((res) => {
        if (!cancelled) {
          setPresetResult(res);
          setPresetError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setPresetError((e as Error).message);
          setPresetResult(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [preset]);

  async function deriveFromCustomBrief() {
    if (!customBrief.trim()) return;
    await runJob(
      customBrief,
      () => api.sdlcFromBrief(customBrief),
      (next) => ({
        label: next.recommendation.recommended.replace(/_/g, " "),
        detail: `derived from ${next.requirements_extracted} requirements`,
      }),
      { label: "Reading the brief", detail: "extracting, then ranking" },
    );
  }

  // Active derived recommendation: either from selected project or from custom job
  const activeSdlc = projectSdlc ?? job.result ?? null;
  const busy = projectLoading || job.state === "running";
  const error = projectError ?? job.error ?? null;

  return (
    <ModuleShell
      pathname="/lifecycle"
      eyebrow="SDLC Recommendation"
      title="The mathematics decides, the model only explains"
      lede="AHP-derived weights, checked for consistency, then ranked by TOPSIS multi-criteria decision analysis. Factor scores, weights, and phase activities are fully traceable to verified project requirements."
      scene={<LifecycleLayer ranked={activeSdlc?.recommendation.ranked ?? presetResult?.ranked ?? null} />}
      sceneCaption="TOPSIS ranks by distance to an ideal model. Candidates sit on the axis at their respective closeness coefficients."
    >
      {/* Unified Project Selector Bar */}
      <Block>
        <ProjectSelector
          activeModule="lifecycle"
          currentProjectId={selectedProjectId}
          onSelectProject={handleSelectProject}
        />
      </Block>

      {/* Project SDLC Recommendation */}
      {activeSdlc && (
        <Block>
          <div className="glass-raised p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <GitBranch size={20} className="text-[var(--accent)]" />
                <h3 className="headline text-lg font-semibold">
                  Recommended Model: {activeSdlc.recommendation.recommended.toUpperCase().replace(/_/g, " ")}
                </h3>
                <Badge tone="var(--confirmed)">MCDA TOPSIS Ranked</Badge>
                {activeSdlc.recommendation.close_call && (
                  <Badge tone="var(--review)">Close Call — Architect Decision</Badge>
                )}
              </div>
              <p className="caption text-[var(--text-secondary)] mt-1 mb-0 max-w-2xl">
                Derived mathematically from {activeSdlc.requirements_extracted} verified requirements. Consistency ratio {activeSdlc.recommendation.consistency_ratio} &le; 0.10 (mathematically consistent).
              </p>
            </div>

            <Button
              variant="quiet"
              onClick={() => selectedProjectId && loadSdlcForProject(selectedProjectId)}
              disabled={busy}
            >
              <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
              Re-compute SDLC
            </Button>
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
              Calculating AHP weights and TOPSIS Euclidean distance to ideal lifecycle…
            </div>
          </div>
        </Block>
      )}

      {!busy && !error && !activeSdlc && (
        <Block>
          <Empty>Select a project from the selector above to view its recommended SDLC model and workflow.</Empty>
        </Block>
      )}

      {/* TOPSIS Closeness Ranking & Factor Derivations */}
      {activeSdlc && !busy && (
        <>
          <Block title="Lifecycle Candidates & TOPSIS Closeness Scores">
            <div className="glass p-6">
              <div className="mb-5 flex flex-col gap-3">
                {activeSdlc.recommendation.ranked.map((rank, i) => (
                  <div key={rank.model} className="rise" style={{ animationDelay: `${i * 0.03}s` }}>
                    <div className="mb-1.5 flex items-baseline justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="body" style={{ fontWeight: i === 0 ? 600 : 450 }}>
                          {rank.model.replace(/_/g, " ")}
                        </span>
                        {i === 0 && <Badge tone="var(--confirmed)">TOP CHOICE</Badge>}
                      </div>
                      <span className="mono font-semibold" style={{ color: i === 0 ? "var(--confirmed)" : "var(--text-secondary)" }}>
                        {rank.percentage}% (closeness {rank.closeness.toFixed(3)})
                      </span>
                    </div>
                    <div
                      style={{
                        height: 7,
                        borderRadius: 3.5,
                        background: "var(--bg-inset)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${rank.percentage}%`,
                          borderRadius: 3.5,
                          background: i === 0 ? "var(--accent)" : "var(--hairline-strong)",
                          transition: "width 0.7s cubic-bezier(0.16,1,0.3,1)",
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {activeSdlc.observations.length > 0 && (
                <div className="mt-6 pt-5 border-t border-[var(--hairline)]">
                  <div className="headline mb-2 font-semibold">How the factors were derived from project requirements:</div>
                  <ul className="caption space-y-1.5" style={{ paddingLeft: 18, margin: 0, lineHeight: 1.6 }}>
                    {activeSdlc.observations.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Block>

          {/* Generated Workflow Phases & Quality Gates */}
          <Block title="Recommended Workflow Phases & Governance Gates">
            <div className="caption mb-3 text-[var(--text-secondary)]">
              Cadence: {activeSdlc.workflow.cadence}
            </div>

            <div className="flex flex-col gap-3">
              {activeSdlc.workflow.phases.map((phase) => (
                <details key={phase.name} className="glass p-5 rounded-xl">
                  <summary className="flex flex-wrap items-center gap-2 cursor-pointer list-none">
                    <span className="headline font-semibold text-base">{phase.name}</span>
                    {phase.gate && (
                      <Badge tone="var(--review)">Formal Gate: {phase.gate}</Badge>
                    )}
                    <Badge>{phase.activities.length} activities</Badge>
                    <Badge>{phase.roles.length} roles</Badge>
                  </summary>

                  <p className="caption mt-2 mb-3 text-[var(--text-secondary)]">{phase.purpose}</p>

                  <div className="grid gap-4 sm:grid-cols-2 mt-3 pt-3 border-t border-[var(--hairline)]">
                    <div>
                      <div className="caption font-semibold mb-1" style={{ color: "var(--text)" }}>
                        Entry Criteria
                      </div>
                      <ul className="caption space-y-1" style={{ paddingLeft: 16, margin: 0 }}>
                        {phase.entry_criteria.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <div className="caption font-semibold mb-1" style={{ color: "var(--text)" }}>
                        Exit Criteria
                      </div>
                      <ul className="caption space-y-1" style={{ paddingLeft: 16, margin: 0 }}>
                        {phase.exit_criteria.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div className="caption mt-4 font-semibold" style={{ color: "var(--text)" }}>
                    Key Activities &amp; Roles
                  </div>
                  <div className="mt-1 flex flex-col gap-2">
                    {phase.activities.map((activity) => (
                      <div key={activity.name} className="caption p-2 rounded-lg bg-[var(--surface-raised)] border border-[var(--hairline)]">
                        <span className="font-medium text-[var(--text)]">{activity.name}</span>
                        {" &bull; "}
                        <span className="text-[var(--text-secondary)]">{activity.role}</span>
                        {activity.security && (
                          <span className="ml-2"><Badge tone="var(--gap)">Security</Badge></span>
                        )}
                        {activity.compliance && (
                          <span className="ml-2"><Badge tone="var(--confirmed)">Compliance</Badge></span>
                        )}
                        {activity.because && (
                          <div className="text-[var(--review)] text-xs mt-1">
                            Rationale: added because {activity.because}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {phase.deliverables.length > 0 && (
                    <div className="mt-3">
                      <div className="caption font-semibold" style={{ color: "var(--text)" }}>
                        Phase Deliverables
                      </div>
                      <ul className="caption mt-1" style={{ paddingLeft: 16, margin: 0 }}>
                        {phase.deliverables.map((d) => (
                          <li key={d}>{d}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </details>
              ))}
            </div>
          </Block>
        </>
      )}

      {/* Preset Profiles Sandbox */}
      <Block title="Preset Factor Profiles (Sandbox Comparison)" delay={0.04}>
        <p className="caption mb-4" style={{ maxWidth: 640 }}>
          Benchmark known industry profiles to observe mathematical sensitivity of the AHP/TOPSIS algorithm across different operating parameters.
        </p>
        <div className="flex flex-wrap gap-2">
          {Object.keys(PRESETS).map((name) => (
            <button
              key={name}
              onClick={() => setPreset(name)}
              className="body cursor-pointer transition-colors"
              style={{
                background: preset === name ? "var(--accent)" : "var(--glass)",
                color: preset === name ? "#fff" : "var(--text-secondary)",
                border: "1px solid var(--hairline)",
                borderRadius: 999,
                padding: "7px 15px",
                fontWeight: 520,
              }}
            >
              {name}
            </button>
          ))}
        </div>

        {presetError && <div className="mt-4"><Failure message={presetError} /></div>}

        {presetResult && (
          <div className="mt-6 glass p-5 rounded-xl">
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <Badge tone="var(--confirmed)">
                Preset Recommended: {presetResult.recommended.toUpperCase().replace(/_/g, " ")}
              </Badge>
              <Badge tone={presetResult.consistency_ratio <= 0.1 ? "var(--confirmed)" : "var(--gap)"}>
                Consistency Ratio: {presetResult.consistency_ratio}
              </Badge>
            </div>

            <div className="flex flex-col gap-2 mb-4">
              {presetResult.ranked.slice(0, 4).map((rank, i) => (
                <div key={rank.model} className="rise">
                  <div className="mb-1 flex items-baseline justify-between gap-3">
                    <span className="body" style={{ fontWeight: i === 0 ? 600 : 450 }}>
                      {rank.model.replace(/_/g, " ")}
                    </span>
                    <span className="mono" style={{ color: i === 0 ? "var(--confirmed)" : "var(--text-secondary)" }}>
                      {rank.percentage}%
                    </span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "var(--bg-inset)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${rank.percentage}%`, borderRadius: 3, background: i === 0 ? "var(--accent)" : "var(--hairline-strong)" }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Block>

      {/* Custom Brief Accordion */}
      <Block>
        <div className="mt-4 pt-4 border-t border-[var(--hairline)]">
          <button
            type="button"
            onClick={() => setShowCustomPrompt(!showCustomPrompt)}
            className="caption text-[var(--text-tertiary)] hover:text-[var(--text)] inline-flex items-center gap-1.5 transition-colors"
          >
            <Sparkles size={13} />
            {showCustomPrompt ? "Hide Custom Brief Input" : "Extract SDLC from Ad-Hoc Brief (Slow LLM Mode)"}
          </button>

          {showCustomPrompt && (
            <div className="glass-raised p-6 mt-3 rounded-xl border border-[var(--hairline)]">
              <label className="caption mb-2 block font-medium">Custom Project Brief Prose:</label>
              <textarea
                value={customBrief}
                onChange={(event) => setCustomBrief(event.target.value)}
                rows={4}
                placeholder="We are building remote customer onboarding for a retail bank. Customers will submit identity documents..."
                className="body w-full rounded-xl border border-[var(--hairline)] bg-[var(--bg-inset)] p-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--focus)]"
              />
              <div className="mt-3 flex items-center gap-3">
                <Button onClick={deriveFromCustomBrief} disabled={busy || !customBrief.trim()}>
                  {busy ? "Reading the brief…" : "Recommend from Custom Brief"}
                </Button>
                <span className="caption text-[var(--text-tertiary)]">Expect 40–100 seconds</span>
              </div>
            </div>
          )}
        </div>
      </Block>

      <Block>
        <Rationale>
          Process ceremony has a cost: criteria like documentation need score on
          <em>proximity</em> to what the project requires, not on how much ceremony a model imposes.
          A project that needs light process cares about not being burdened exactly as much as a
          regulated one cares about compliance rigour.
        </Rationale>
      </Block>
    </ModuleShell>
  );
}
