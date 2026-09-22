"use client";

/**
 * Lifecycle — which SDLC fits this project, and why.
 *
 * The recommendation is arithmetic, not opinion: AHP-derived weights checked
 * for consistency, then TOPSIS. The model's only job is to put the result into
 * sentences. An architect who cannot re-derive a recommendation cannot
 * challenge it, so the weights, the consistency ratio and the closeness
 * coefficients are all on the page.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { useJob } from "@/components/chrome/Jobs";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
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

const BRIEF =
  "We are building remote customer onboarding for a retail bank. Customers " +
  "will submit identity documents from their phone and complete a liveness " +
  "check. Everything must be screened against the sanctions list before the " +
  "account can be used, and we have to keep the evidence for audit. The " +
  "product team wants to ship changes weekly and the rules keep moving.";

export default function LifecyclePage() {
  const [preset, setPreset] = useState("eKYC onboarding");
  const [result, setResult] = useState<SDLC | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The brief path. Separate state, because a derived recommendation and a
  // hand-set one are different claims and should not overwrite each other
  // silently - the reader needs to know which of the two they are looking at.
  const { job, run: runJob } = useJob<SDLCFromBrief>("lifecycle");
  const derived = job.result ?? null;
  const derivingError = job.error ?? null;
  const deriving = job.state === "running";
  const [brief, setBrief] = useState(job.input ?? BRIEF);

  async function deriveFromBrief() {
    await runJob(
      brief,
      () => api.sdlcFromBrief(brief),
      (next) => ({
        label: next.recommendation.recommended.replace(/_/g, " "),
        detail: `derived from ${next.requirements_extracted} requirements`,
      }),
      { label: "Reading the brief", detail: "extracting, then ranking" },
    );
  }

  useEffect(() => {
    let cancelled = false;
    // Guarded so a rapid preset change cannot let a slower earlier response
    // overwrite a newer one, which would show a ranking for the wrong project.
    api
      .sdlc(PRESETS[preset])
      .then((next) => {
        if (cancelled) return;
        setResult(next);
        setError(null);
      })
      .catch((e) => {
        if (cancelled) return;
        setError((e as Error).message);
        setResult(null);
      });
    return () => {
      cancelled = true;
    };
  }, [preset]);

  return (
    <ModuleShell
      pathname="/lifecycle"
      eyebrow="Lifecycle"
      title="The mathematics decides, the model only explains"
      lede="AHP-derived weights, checked for consistency, then ranked by TOPSIS. The factor scores, the weights and the arithmetic are all inspectable — a recommendation an architect cannot re-derive is one they cannot challenge."
      scene={<LifecycleLayer ranked={result?.ranked ?? null} />}
      sceneCaption="The decision itself. TOPSIS ranks by distance to a synthetic ideal, so it can be drawn without inventing anything: the solid node at the top is that ideal — best on every criterion at once, which no real lifecycle achieves — the faint one at the bottom is its opposite, and each candidate sits on the axis between them at its own closeness coefficient. When two candidates sit at the same height the recommendation is a coin toss, and the picture says so faster than the engine's close-call flag."
    >
      {/*
        The brief comes first, and the presets second, because that is the
        order of trust. A factor vector set by hand is a conclusion dressed as
        an input - whoever moves the sliders has already chosen the answer. A
        vector derived from the requirements actually extracted from a brief is
        traceable to evidence like everything else here.
      */}
      <Block title="Describe the project">
        <div className="glass-raised p-6 lg:p-8">
          <textarea
            value={brief}
            onChange={(event) => setBrief(event.target.value)}
            rows={5}
            aria-label="Project brief"
            className="body w-full"
            style={{
              background: "var(--bg-inset)",
              border: "1px solid var(--hairline)",
              borderRadius: 12,
              padding: "12px 15px",
              color: "var(--text)",
              outline: "none",
              resize: "vertical",
            }}
          />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={deriveFromBrief} disabled={deriving || !brief.trim()}>
              {deriving ? "Reading the brief…" : "Recommend a lifecycle"}
            </Button>
            <span className="caption">
              extracts requirements first, then derives the factors — 40–100 seconds
            </span>
          </div>

          {derivingError && (
            <div className="mt-4">
              <Failure message={derivingError} />
            </div>
          )}

          {derived && !deriving && (
            <div className="mt-6" style={{ borderTop: "1px solid var(--hairline)", paddingTop: 20 }}>
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <Badge tone="var(--confirmed)">
                  recommended · {derived.recommendation.recommended.replace(/_/g, " ")}
                </Badge>
                <Badge>{derived.requirements_extracted} requirements extracted</Badge>
                {derived.recommendation.close_call && (
                  <Badge tone="var(--review)">close call — human decision</Badge>
                )}
              </div>

              <div className="mb-5 flex flex-col gap-2.5">
                {derived.recommendation.ranked.slice(0, 4).map((rank, i) => (
                  <div key={rank.model}>
                    <div className="mb-1.5 flex items-baseline justify-between gap-3">
                      <span className="body" style={{ fontWeight: i === 0 ? 600 : 450 }}>
                        {rank.model.replace(/_/g, " ")}
                      </span>
                      <span className="mono" style={{ color: "var(--text-secondary)" }}>
                        {rank.percentage}%
                      </span>
                    </div>
                    <div
                      style={{
                        height: 6,
                        borderRadius: 3,
                        background: "var(--bg-inset)",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          height: "100%",
                          width: `${rank.percentage}%`,
                          borderRadius: 3,
                          background: i === 0 ? "var(--text)" : "var(--hairline-strong)",
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="headline mb-2">How the factors were derived</div>
              <ul
                className="caption"
                style={{ paddingLeft: 18, margin: 0, lineHeight: 1.7 }}
              >
                {derived.observations.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>

              {/*
                The workflow is the half of "SDLC identification" a label does
                not deliver. Shown immediately under the ranking because the
                ranking is the decision and this is what the decision means in
                practice.
              */}
              <div className="mt-6" style={{ borderTop: "1px solid var(--hairline)", paddingTop: 20 }}>
                <div className="headline mb-1">The workflow this produces</div>
                <p className="caption mb-4" style={{ maxWidth: 640 }}>
                  {derived.workflow.cadence}
                </p>

                {derived.workflow.notes.map((note) => (
                  <p
                    key={note}
                    className="caption mb-2"
                    style={{ color: "var(--review)" }}
                  >
                    {note}
                  </p>
                ))}

                <div className="mt-4 flex flex-col gap-3">
                  {derived.workflow.phases.map((phase) => (
                    <details key={phase.name} className="glass p-4">
                      <summary
                        className="flex flex-wrap items-center gap-2"
                        style={{ cursor: "pointer", listStyle: "none" }}
                      >
                        <span className="headline">{phase.name}</span>
                        {phase.gate && (
                          <Badge tone="var(--review)">gate · {phase.gate}</Badge>
                        )}
                        <Badge>{phase.activities.length} activities</Badge>
                        <Badge>{phase.roles.length} roles</Badge>
                      </summary>

                      <p className="caption mt-2 mb-3">{phase.purpose}</p>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <div className="caption" style={{ color: "var(--text)" }}>
                            Entry criteria
                          </div>
                          <ul className="caption" style={{ paddingLeft: 16, margin: 0 }}>
                            {phase.entry_criteria.map((c) => (
                              <li key={c}>{c}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <div className="caption" style={{ color: "var(--text)" }}>
                            Exit criteria
                          </div>
                          <ul className="caption" style={{ paddingLeft: 16, margin: 0 }}>
                            {phase.exit_criteria.map((c) => (
                              <li key={c}>{c}</li>
                            ))}
                          </ul>
                        </div>
                      </div>

                      <div className="caption mt-3" style={{ color: "var(--text)" }}>
                        Activities
                      </div>
                      <div className="mt-1 flex flex-col gap-1.5">
                        {phase.activities.map((activity) => (
                          <div key={activity.name} className="caption">
                            <span style={{ color: "var(--text)" }}>{activity.name}</span>
                            {" — "}
                            {activity.role}
                            {activity.security && (
                              <span style={{ color: "var(--gap)" }}> · security</span>
                            )}
                            {activity.compliance && (
                              <span style={{ color: "var(--confirmed)" }}> · compliance</span>
                            )}
                            {/* Anything the skeleton did not contain says why it
                                is there, so no line is unchallengeable. */}
                            {activity.because && (
                              <div style={{ color: "var(--review)", paddingLeft: 12 }}>
                                added because {activity.because}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      {phase.deliverables.length > 0 && (
                        <>
                          <div className="caption mt-3" style={{ color: "var(--text)" }}>
                            Deliverables
                          </div>
                          <ul className="caption" style={{ paddingLeft: 16, margin: 0 }}>
                            {phase.deliverables.map((d) => (
                              <li key={d}>{d}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </details>
                  ))}
                </div>

                <div className="caption mt-4" style={{ color: "var(--text)" }}>
                  Traceability requirements
                </div>
                <ul className="caption" style={{ paddingLeft: 16, margin: 0 }}>
                  {derived.workflow.traceability.map((line) => (
                    <li key={line} style={{ marginBottom: 3 }}>
                      {line}
                    </li>
                  ))}
                </ul>
              </div>

              {derived.unclear.length > 0 && (
                <div className="mt-5">
                  <div className="headline mb-1" style={{ color: "var(--review)" }}>
                    Questions the brief left open
                  </div>
                  <p className="caption mb-2">
                    These push requirement stability down and change frequency up,
                    which is part of why the ranking came out as it did. Answering
                    them on the Requirements module and re-running will move the
                    recommendation.
                  </p>
                  <ul className="caption" style={{ paddingLeft: 18, margin: 0 }}>
                    {derived.unclear.map((question) => (
                      <li key={question} style={{ marginBottom: 4 }}>
                        {question}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </Block>

      <Block title="Or compare against a known profile" delay={0.04}>
        <p className="caption mb-4" style={{ maxWidth: 640 }}>
          Four hand-set factor profiles, useful for seeing how the ranking
          responds to a change in one dimension. Set by hand, so they demonstrate
          the arithmetic rather than evidencing a recommendation.
        </p>
        <div className="flex flex-wrap gap-2">
          {Object.keys(PRESETS).map((name) => (
            <button
              key={name}
              onClick={() => setPreset(name)}
              className="body"
              style={{
                background: preset === name ? "var(--accent)" : "var(--glass)",
                color: preset === name ? "#fff" : "var(--text-secondary)",
                border: "1px solid var(--hairline)",
                borderRadius: 999,
                padding: "7px 15px",
                cursor: "pointer",
                fontWeight: 520,
              }}
            >
              {name}
            </button>
          ))}
        </div>
      </Block>

      {error && <Failure message={error} />}
      {!error && !result && <Empty>Ranking…</Empty>}

      {result && (
        <>
          <Block>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="var(--confirmed)">
                recommended · {result.recommended.replace(/_/g, " ")}
              </Badge>
              <Badge
                tone={result.consistency_ratio <= 0.1 ? "var(--confirmed)" : "var(--gap)"}
              >
                consistency ratio {result.consistency_ratio}
              </Badge>
              {result.close_call && (
                <Badge tone="var(--review)">close call — human decision</Badge>
              )}
            </div>
          </Block>

          <Block title="Ranking">
            <div className="flex flex-col gap-2.5">
              {result.ranked.map((rank, i) => (
                <div
                  key={rank.model}
                  className="rise"
                  style={{ animationDelay: `${i * 0.05}s` }}
                >
                  <div className="mb-1.5 flex items-baseline justify-between gap-3">
                    <span className="body" style={{ fontWeight: i === 0 ? 600 : 450 }}>
                      {rank.model.replace(/_/g, " ")}
                    </span>
                    <span
                      className="mono"
                      style={{
                        color: i === 0 ? "var(--confirmed)" : "var(--text-secondary)",
                      }}
                    >
                      {rank.percentage}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 6,
                      borderRadius: 3,
                      background: "var(--bg-inset)",
                      overflow: "hidden",
                    }}
                  >
                    {/* Drawn at its width. A bar that grows on scroll is a
                        figure the reader has to wait for, and it does not grow
                        at all if the animation never runs. */}
                    <div
                      style={{
                        height: "100%",
                        width: `${rank.percentage}%`,
                        borderRadius: 3,
                        background: i === 0 ? "var(--text)" : "var(--hairline-strong)",
                        transition: "width 0.7s cubic-bezier(0.16,1,0.3,1)",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Block>

          <Block title="Why">
            {result.notes.length > 0 && (
              <div className="mb-4 flex flex-col gap-2">
                {result.notes.map((note) => (
                  <div key={note} className="caption" style={{ color: "var(--review)" }}>
                    {note}
                  </div>
                ))}
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              {result.explanation.map((line) => (
                <div key={line} className="caption">
                  {line}
                </div>
              ))}
            </div>

            <Rationale>
              Two corrections shaped this engine, both found by putting a
              low-risk exploratory project through it and getting a DevSecOps
              hybrid back. First, process ceremony has a cost: criteria like
              documentation need must score on <em>proximity</em> to what the
              project needs, not on how much of it a model provides. Second, and
              less obvious, those match criteria must not be weighted by the
              factor value — a project that needs light process cares about not
              being burdened exactly as much as a regulated one cares about
              rigour. The seven lifecycle profiles are the part of this module
              least validated: they encode published guidance and my reading of
              it, and they have not been reviewed by practising architects.
            </Rationale>
          </Block>
        </>
      )}
    </ModuleShell>
  );
}
