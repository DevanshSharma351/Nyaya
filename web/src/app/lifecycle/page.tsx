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
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { Badge, Empty, Failure } from "@/components/ui";
import { api, type SDLC } from "@/lib/api";

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
  const [preset, setPreset] = useState("eKYC onboarding");
  const [result, setResult] = useState<SDLC | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      <Block>
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
