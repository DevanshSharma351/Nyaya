"use client";

/**
 * Requirements — stakeholder prose into testable obligations.
 *
 * The interesting failure in this module is not a missed requirement, it is an
 * invented one. Pressed to remove vagueness, a model will happily replace "as
 * quick as possible" with a specific threshold nobody agreed to, and the result
 * reads as precision. Every quantity is therefore checked against the source
 * text, and unsupported ones are reported as defects rather than smoothed over.
 */

import dynamic from "next/dynamic";
import { useState } from "react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { useTaskReporter } from "@/components/chrome/StatusIsland";
import { Badge, Button, Empty, Failure } from "@/components/ui";
import { api, type ExtractResult } from "@/lib/api";

const RequirementLayer = dynamic(
  () => import("@/components/scenes/RequirementLayer"),
  { ssr: false },
);

const SEED =
  "Compliance officer: for any customer we onboard remotely we have to check " +
  "them against the sanctions list before the account goes live, and keep proof " +
  "of that check for five years.";

const RISK_TONE: Record<string, string> = {
  low: "var(--text-tertiary)",
  medium: "var(--accent)",
  high: "var(--review)",
  critical: "var(--gap)",
};

export default function RequirementsPage() {
  const [text, setText] = useState(SEED);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const report = useTaskReporter();

  async function run() {
    setBusy(true);
    setError(null);
    // Extraction runs on a local model and takes long enough that a still page
    // is indistinguishable from a broken one, so the island carries the state
    // while the reader is free to scroll or leave the module.
    report({ state: "running", label: "Extracting requirements", detail: "40–100s" });
    try {
      const extracted = await api.extract(text);
      setResult(extracted);
      const defects = extracted.requirements.reduce(
        (total, requirement) => total + requirement.defects.length,
        0,
      );
      report({
        state: "done",
        label: `${extracted.requirements.length} requirements`,
        detail: defects > 0 ? `${defects} defects flagged` : "no defects detected",
      });
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
      report({ state: "failed", label: "Extraction failed", detail: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <ModuleShell
      pathname="/requirements"
      eyebrow="Requirements"
      title="Stakeholder prose into testable obligations"
      lede="Rewritten into EARS form, with compounds split so each obligation can be approved and traced separately."
      scene={<RequirementLayer requirements={result?.requirements ?? null} />}
      sceneCaption="Each requirement is drawn with as many segments as its EARS pattern has clauses — one for a ubiquitous requirement, two for an event-driven one, three for a complex one — so the parts of an obligation can be counted without reading it. The orbiting spheres are acceptance criteria; the red spikes are detected defects."
    >
      <Block>
        <div className="glass-raised specular p-6 lg:p-8">
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={3}
            className="body w-full"
            style={{
              background: "var(--glass)",
              border: "1px solid var(--hairline)",
              borderRadius: 12,
              padding: "12px 15px",
              color: "var(--text)",
              outline: "none",
              resize: "vertical",
            }}
          />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button onClick={run} disabled={busy || !text.trim()}>
              {busy ? "Extracting…" : "Extract requirements"}
            </Button>
            <span className="caption">runs a local model — expect 40–100 seconds</span>
          </div>
        </div>
      </Block>

      <Block>
        {error && <Failure message={error} />}
        {busy && (
          <div className="glass p-5">
            <div className="sheen" style={{ height: 10, borderRadius: 5 }} />
            <div className="caption mt-3">
              extracting, checking EARS conformance, scanning for ambiguity and
              unsupported quantities…
            </div>
          </div>
        )}
        {!busy && !error && !result && (
          <Empty>Extract to see the structured requirements and their defects.</Empty>
        )}

        {result && !busy && (
          <>
            <div className="mb-5 flex flex-wrap gap-2">
              <Badge tone="var(--accent)">{result.model}</Badge>
              <Badge
                tone={
                  result.testable_fraction === 1 ? "var(--confirmed)" : "var(--review)"
                }
              >
                {Math.round(result.testable_fraction * 100)}% testable
              </Badge>
              {result.repair_rounds > 0 && (
                <Badge tone="var(--review)">
                  {result.repair_rounds} repair round
                  {result.repair_rounds > 1 ? "s" : ""}
                </Badge>
              )}
            </div>

            {result.requirements.map((requirement, i) => (
              <article
                key={requirement.statement}
                className="rise glass mb-3 p-5"
                style={{ animationDelay: `${i * 0.07}s` }}
              >
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <Badge tone="var(--accent)">{requirement.ears_pattern}</Badge>
                    <Badge tone={RISK_TONE[requirement.risk_level]}>
                      {requirement.risk_level}
                    </Badge>
                    <Badge>{requirement.priority}</Badge>
                    {requirement.categories.slice(0, 3).map((category) => (
                      <Badge key={category} tone="var(--clause)">
                        {category}
                      </Badge>
                    ))}
                  </div>

                  <p className="body m-0" style={{ fontWeight: 500 }}>
                    {requirement.statement}
                  </p>

                  {requirement.acceptance_criteria.length > 0 && (
                    <ul className="caption mt-3" style={{ paddingLeft: 18, margin: 0 }}>
                      {requirement.acceptance_criteria.map((criterion) => (
                        <li key={criterion} style={{ marginBottom: 4 }}>
                          {criterion}
                        </li>
                      ))}
                    </ul>
                  )}

                  <div
                    className="caption mt-3"
                    style={{
                      borderLeft: "2px solid var(--hairline)",
                      paddingLeft: 10,
                      fontStyle: "italic",
                    }}
                  >
                    traced to: “{requirement.quoted_source}”
                  </div>

                  {requirement.defects.length > 0 && (
                    <div className="mt-3 flex flex-col gap-1.5">
                      {requirement.defects.map((defect, k) => (
                        <div
                          key={k}
                          className="caption"
                          style={{
                            color:
                              defect.severity === "major" ||
                              defect.severity === "blocker"
                                ? "var(--gap)"
                                : "var(--review)",
                          }}
                        >
                          <span className="mono">{defect.detector}</span> —{" "}
                          {defect.detail}
                        </div>
                      ))}
                    </div>
                  )}
              </article>
            ))}

            {result.unclear.length > 0 && (
              <div className="glass mt-4 p-5">
                <div className="headline mb-2" style={{ color: "var(--review)" }}>
                  Open questions
                </div>
                <p className="caption mb-3">
                  Raised rather than answered. Inventing a missing value produces
                  a requirement that reads as precise and was never agreed.
                </p>
                <ul
                  className="body"
                  style={{ paddingLeft: 18, margin: 0, color: "var(--text-secondary)" }}
                >
                  {result.unclear.map((question) => (
                    <li key={question} style={{ marginBottom: 6 }}>
                      {question}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        <Rationale>
          The quantity check exists because the repair loop caused the failure it
          was meant to prevent. Asked to remove vagueness from “as quick as
          possible”, the model produced “no more than three distinct user
          actions” — a number that appears nowhere in the source and reads as
          more precise than the vagueness it replaced. The first version of the
          detector missed exactly that case, because the unit was separated from
          the number by two modifiers. One caveat is owed: the prompt was
          hardened in the same change, so the improvement is confounded. The
          detector’s value is that it is a guarantee rather than a hope.
        </Rationale>
      </Block>
    </ModuleShell>
  );
}
