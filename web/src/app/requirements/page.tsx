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
import { useJob } from "@/components/chrome/Jobs";
import { Badge, Button, Empty, Failure } from "@/components/ui";
import { api, type Clarification, type ExtractResult } from "@/lib/api";

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
  // The job lives above this page, so an extraction started here survives a
  // navigation away and is still here on return - running or finished.
  const { job, run: runJob } = useJob<ExtractResult>("requirements");
  const result = job.result ?? null;
  const error = job.error ?? null;
  const busy = job.state === "running";

  // Seeded from the job when one exists, so returning to the module restores
  // the text that was actually submitted rather than the placeholder.
  const [text, setText] = useState(job.input ?? SEED);

  // Answers to the questions the last extraction raised. Held here and sent
  // back on the next run, where the API folds them into the source text - so an
  // answered question becomes stated input and is checked exactly like the rest
  // of the brief. An answer passed as a side channel would let a real,
  // human-supplied number look identical to an invented one, which is the whole
  // failure this module exists to catch.
  const [answers, setAnswers] = useState<Record<string, string>>({});

  async function run(withAnswers = false) {
    const clarifications: Clarification[] = withAnswers
      ? Object.entries(answers)
          .filter(([, answer]) => answer.trim())
          .map(([question, answer]) => ({ question, answer: answer.trim() }))
      : [];

    await runJob(
      text,
      () => api.extract(text, clarifications),
      (extracted) => {
        const defects = extracted.requirements.reduce(
          (total, requirement) => total + requirement.defects.length,
          0,
        );
        return {
          label: `${extracted.requirements.length} requirements`,
          detail: defects > 0 ? `${defects} defects flagged` : "no defects detected",
        };
      },
      // Extraction runs on a local model and takes long enough that a still
      // page is indistinguishable from a broken one.
      { label: "Extracting requirements", detail: "40-100s" },
    );
    // Answers folded into the brief are consumed; keeping them would silently
    // re-apply them to a brief the reader may since have rewritten.
    if (clarifications.length > 0) setAnswers({});
  }

  return (
    <ModuleShell
      pathname="/requirements"
      eyebrow="Requirements"
      title="Stakeholder prose into testable obligations"
      lede="Rewritten into EARS form, with compounds split so each obligation can be approved and traced separately."
      scene={<RequirementLayer requirements={result?.requirements ?? null} />}
      sceneCaption="Scroll the page and the field assembles. It starts scattered, which is what stakeholder language is, and resolves into one column per extracted requirement — a column is as tall as the requirement has acceptance criteria, its shade is the risk level, and the red share is how much of it is defective. Before extraction runs there is nothing to assemble into, so it stays scattered."
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
            <Button onClick={() => run(false)} disabled={busy || !text.trim()}>
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
            {/* A degraded run must not look like a clean one. */}
            {result.notes?.length > 0 && (
              <div
                className="glass mb-5 p-4"
                style={{ borderLeft: "2px solid var(--review)" }}
              >
                {result.notes.map((note) => (
                  <p key={note} className="caption m-0">
                    {note}
                  </p>
                ))}
              </div>
            )}

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
              <div className="glass mt-4 p-5 lg:p-6">
                <div className="headline mb-2" style={{ color: "var(--review)" }}>
                  Open questions — {result.unclear.length}
                </div>
                <p className="caption mb-4" style={{ maxWidth: 620 }}>
                  Raised rather than answered. Inventing a missing value produces a
                  requirement that reads as precise and was never agreed — which is
                  worse than the vagueness it replaced, because it passes every
                  check. Answer any of these and the extraction runs again with
                  your answers folded into the brief, where the same quantity and
                  provenance checks apply to them.
                </p>

                <div className="flex flex-col gap-4">
                  {result.unclear.map((question) => (
                    <div key={question}>
                      <label
                        className="body mb-1.5 block"
                        style={{ fontWeight: 500 }}
                        htmlFor={`answer-${question.slice(0, 24)}`}
                      >
                        {question}
                      </label>
                      <input
                        id={`answer-${question.slice(0, 24)}`}
                        value={answers[question] ?? ""}
                        onChange={(event) =>
                          setAnswers((current) => ({
                            ...current,
                            [question]: event.target.value,
                          }))
                        }
                        placeholder="your answer, in your own words…"
                        className="body w-full"
                        style={{
                          background: "var(--bg-inset)",
                          border: "1px solid var(--hairline)",
                          borderRadius: 10,
                          padding: "9px 13px",
                          color: "var(--text)",
                          outline: "none",
                        }}
                      />
                    </div>
                  ))}
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <Button
                    onClick={() => run(true)}
                    disabled={
                      busy || !Object.values(answers).some((a) => a.trim())
                    }
                  >
                    Re-extract with these answers
                  </Button>
                  <span className="caption">
                    unanswered questions are left open rather than guessed
                  </span>
                </div>
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
