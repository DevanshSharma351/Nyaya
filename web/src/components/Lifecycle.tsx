"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type SDLC } from "@/lib/api";
import { Badge, Empty, Failure, Panel, SectionHeading } from "./ui";

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

export default function Lifecycle() {
  const [preset, setPreset] = useState("eKYC onboarding");
  const [result, setResult] = useState<SDLC | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Guarded so a rapid preset change cannot let a slower earlier response
    // overwrite a newer one - which would show a ranking for the wrong project.
    async function load() {
      try {
        const next = await api.sdlc(PRESETS[preset]);
        if (!cancelled) {
          setResult(next);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError((e as Error).message);
          setResult(null);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [preset]);

  return (
    <Panel className="p-8 lg:p-10" delay={0.1}>
      <SectionHeading
        eyebrow="Lifecycle selection"
        title="The mathematics decides, the model only explains"
        lede="AHP-derived weights, checked for consistency, ranked by TOPSIS. A recommendation an architect cannot re-derive is one they cannot challenge — so the factor scores, weights and arithmetic are all inspectable."
      />

      <div className="mb-7 flex flex-wrap gap-2">
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

      {error && <Failure message={error} />}
      {!error && !result && <Empty>Ranking…</Empty>}

      {result && (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <Badge tone="var(--confirmed)">
              recommended · {result.recommended.replace(/_/g, " ")}
            </Badge>
            <Badge
              tone={
                result.consistency_ratio <= 0.1 ? "var(--confirmed)" : "var(--gap)"
              }
            >
              consistency ratio {result.consistency_ratio}
            </Badge>
            {result.close_call && (
              <Badge tone="var(--review)">close call — human decision</Badge>
            )}
          </div>

          <div className="flex flex-col gap-2.5">
            {result.ranked.map((rank, i) => (
              <motion.div
                key={rank.model}
                initial={{ opacity: 0, x: -14 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
              >
                <div className="mb-1.5 flex items-baseline justify-between gap-3">
                  <span className="body" style={{ fontWeight: i === 0 ? 600 : 450 }}>
                    {rank.model.replace(/_/g, " ")}
                  </span>
                  <span
                    className="mono"
                    style={{ color: i === 0 ? "var(--confirmed)" : "var(--text-secondary)" }}
                  >
                    {rank.percentage}%
                  </span>
                </div>
                <div
                  style={{
                    height: 6,
                    borderRadius: 3,
                    background: "rgba(255,255,255,0.07)",
                    overflow: "hidden",
                  }}
                >
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: `${rank.percentage}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.75, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
                    style={{
                      height: "100%",
                      borderRadius: 3,
                      background:
                        i === 0
                          ? "linear-gradient(90deg, #0a84ff, #30d158)"
                          : "rgba(255,255,255,0.24)",
                    }}
                  />
                </div>
              </motion.div>
            ))}
          </div>

          {result.notes.length > 0 && (
            <div className="mt-6 flex flex-col gap-2">
              {result.notes.map((note) => (
                <div key={note} className="caption" style={{ color: "var(--review)" }}>
                  {note}
                </div>
              ))}
            </div>
          )}

          <div className="mt-6 flex flex-col gap-1.5">
            {result.explanation.map((line) => (
              <div key={line} className="caption">
                {line}
              </div>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
