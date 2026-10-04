"use client";

/**
 * Artefacts — what the team is actually handed.
 *
 * Everything upstream exists to make these trustworthy, and for a long time the
 * system produced none of them: it could say a great deal about a requirement
 * and hand over nothing anyone could take to a review. The brief names them
 * twice, in §1 as expected outputs and again in §12.
 *
 * They are derived rather than written. The statements are the ones that passed
 * the quality checks, the acceptance criteria are the extracted ones, and the
 * traceability matrix is the join the system has been maintaining all along. A
 * generated SRS containing requirements nobody approved would be
 * indistinguishable from one containing requirements they did.
 *
 * The traceability matrix leads, because it is the only artefact here that
 * reports on itself: a blank column is a finding, and the coverage figure is one
 * of the brief's twelve evaluation metrics.
 */

import dynamic from "next/dynamic";
import { useState } from "react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { useJob } from "@/components/chrome/Jobs";
import { Badge, Button, Empty, Failure, Ring } from "@/components/ui";
import { api, type Artefacts } from "@/lib/api";

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

type Tab = "traceability" | "stories" | "cases" | "risks";

const TABS: [Tab, string][] = [
  ["traceability", "Traceability matrix"],
  ["stories", "User stories"],
  ["cases", "Use cases"],
  ["risks", "Risk register"],
];

export default function ArtefactsPage() {
  const { job, run: runJob } = useJob<Artefacts>("artefacts");

  const result = job.result ?? null;
  const error = job.error ?? null;
  const busy = job.state === "running";

  const [text, setText] = useState(job.input ?? SEED);
  const [tab, setTab] = useState<Tab>("traceability");

  async function run() {
    await runJob(
      text,
      () => api.artefacts(text),
      (next) => ({
        label: `${next.traceability.length} requirements`,
        detail: `${Math.round(next.traceability_coverage * 100)}% fully traced`,
      }),
      { label: "Generating artefacts", detail: "40-100s" },
    );
  }

  return (
    <ModuleShell
      pathname="/artefacts"
      eyebrow="Artefacts"
      title="What the team is actually handed"
      lede="A traceability matrix, user stories with their acceptance criteria, use cases, and a risk register — derived from the approved requirements rather than written, so nothing appears in them that has not been through the checks."
      scene={<RequirementLayer requirements={null} />}
      sceneCaption="The same field as the Requirements module: scattered prose on the left of the pipeline, resolved structure on the right. These artefacts are the far end of it."
    >
      <Block>
        <div className="glass-raised p-6 lg:p-8">
          <label className="caption mb-2 block">Stakeholder input</label>
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={4}
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
            <Button onClick={run} disabled={busy || !text.trim()}>
              {busy ? "Generating…" : "Generate artefacts"}
            </Button>
            <span className="caption">runs a local model — expect 40–100 seconds</span>
          </div>
        </div>
      </Block>

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
              extracting requirements, then deriving the artefact set from them…
            </div>
          </div>
        </Block>
      )}

      {!busy && !error && !result && (
        <Block>
          <Empty>Generate to see the artefacts derived from this input.</Empty>
        </Block>
      )}

      {result && !busy && (
        <>
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
              <div style={{ maxWidth: 520 }}>
                <div className="headline">Traceability coverage</div>
                <p className="caption mt-1 mb-0">
                  The share of requirements whose chain is complete end to end —
                  source quotation, citation, control mapping and acceptance
                  criteria. One of the brief&rsquo;s twelve evaluation metrics, and
                  the only one computable from the artefacts themselves. Extraction
                  alone cannot fill the citation and control columns, so a low
                  figure here is accurate rather than a fault.
                </p>
              </div>
            </div>
          </Block>

          <Block>
            <div className="flex flex-wrap gap-2">
              {TABS.map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className="body"
                  style={{
                    background: tab === key ? "var(--accent)" : "var(--surface)",
                    color: tab === key ? "var(--accent-ink)" : "var(--text-secondary)",
                    border: "1px solid var(--hairline)",
                    borderRadius: 999,
                    padding: "7px 15px",
                    cursor: "pointer",
                    fontWeight: 520,
                    fontSize: "0.875rem",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </Block>

          {tab === "traceability" && (
            <Block>
              {result.traceability.map((row, i) => (
                <div
                  key={row.ref}
                  className="rise glass mb-3 p-5"
                  style={{
                    animationDelay: `${i * 0.04}s`,
                    borderLeft: `2px solid ${
                      row.gaps.length ? "var(--review)" : "var(--confirmed)"
                    }`,
                  }}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="mono" style={{ fontWeight: 550 }}>
                      {row.ref}
                    </span>
                    {row.citations.map((c) => (
                      <Badge key={c} tone="var(--clause)">
                        {c}
                      </Badge>
                    ))}
                    {row.controls.map((c) => (
                      <Badge key={c} tone="var(--confirmed)">
                        {c}
                      </Badge>
                    ))}
                    {row.gaps.map((g) => (
                      <Badge key={g} tone="var(--review)">
                        {g}
                      </Badge>
                    ))}
                  </div>
                  <p className="body m-0">{row.statement}</p>
                  {row.source_quote && (
                    <div
                      className="caption mt-2"
                      style={{
                        borderLeft: "2px solid var(--hairline)",
                        paddingLeft: 10,
                        fontStyle: "italic",
                      }}
                    >
                      traced to: “{row.source_quote}”
                    </div>
                  )}
                  {row.verification.length > 0 && (
                    <ul className="caption mt-2" style={{ paddingLeft: 18, margin: 0 }}>
                      {row.verification.map((v) => (
                        <li key={v}>{v}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </Block>
          )}

          {tab === "stories" && (
            <Block>
              {result.user_stories.map((story, i) => (
                <div
                  key={story.ref}
                  className="rise glass mb-3 p-5"
                  style={{ animationDelay: `${i * 0.04}s` }}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="mono" style={{ fontWeight: 550 }}>
                      {story.ref}
                    </span>
                    {story.trigger && <Badge tone="var(--accent)">event-driven</Badge>}
                  </div>
                  <p className="body m-0" style={{ fontWeight: 500 }}>
                    {story.text}
                  </p>
                  {story.trigger && (
                    <p className="caption mt-2 mb-0">Trigger: {story.trigger}</p>
                  )}
                  {story.acceptance_criteria.length > 0 && (
                    <>
                      <div className="caption mt-3" style={{ color: "var(--text)" }}>
                        Acceptance criteria
                      </div>
                      <ul className="caption" style={{ paddingLeft: 18, margin: 0 }}>
                        {story.acceptance_criteria.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              ))}
            </Block>
          )}

          {tab === "cases" && (
            <Block>
              {result.use_cases.map((useCase, i) => (
                <div
                  key={useCase.ref}
                  className="rise glass mb-3 p-5"
                  style={{ animationDelay: `${i * 0.04}s` }}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="mono" style={{ fontWeight: 550 }}>
                      {useCase.ref}
                    </span>
                    <Badge>{useCase.actor}</Badge>
                  </div>
                  <div className="headline">{useCase.name}</div>
                  <p className="caption mt-2 mb-0">
                    <strong style={{ color: "var(--text)" }}>Precondition:</strong>{" "}
                    {useCase.precondition}
                  </p>
                  <ol className="caption mt-2" style={{ paddingLeft: 18, margin: 0 }}>
                    {useCase.main_flow.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                  <p className="caption mt-2 mb-0">
                    <strong style={{ color: "var(--text)" }}>Postcondition:</strong>{" "}
                    {useCase.postcondition}
                  </p>
                  {useCase.exceptions.length > 0 && (
                    <>
                      <div className="caption mt-3" style={{ color: "var(--review)" }}>
                        Exception paths — from the detected defects
                      </div>
                      <ul className="caption" style={{ paddingLeft: 18, margin: 0 }}>
                        {useCase.exceptions.map((e) => (
                          <li key={e}>{e}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              ))}
            </Block>
          )}

          {tab === "risks" && (
            <Block>
              {result.risks.map((risk, i) => (
                <div
                  key={risk.ref}
                  className="rise glass mb-3 p-5"
                  style={{
                    animationDelay: `${i * 0.04}s`,
                    borderLeft: `2px solid ${RISK_TONE[risk.level] ?? "var(--hairline)"}`,
                  }}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="mono" style={{ fontWeight: 550 }}>
                      {risk.ref}
                    </span>
                    <Badge tone={RISK_TONE[risk.level]}>{risk.level}</Badge>
                    <Badge>{risk.category}</Badge>
                    <Badge>{risk.owner}</Badge>
                  </div>
                  <p className="body m-0">{risk.description}</p>
                  <p className="caption mt-2 mb-0">{risk.treatment}</p>
                </div>
              ))}
            </Block>
          )}

          {(result.open_issues.length > 0 || result.assumptions.length > 0) && (
            <Block title="Open issues and assumptions">
              <div className="glass p-5">
                {result.open_issues.length > 0 && (
                  <>
                    <div className="headline mb-1" style={{ color: "var(--review)" }}>
                      Open issues
                    </div>
                    <ul className="caption" style={{ paddingLeft: 18, margin: 0 }}>
                      {result.open_issues.map((issue) => (
                        <li key={issue}>{issue}</li>
                      ))}
                    </ul>
                  </>
                )}
                {result.assumptions.length > 0 && (
                  <>
                    <div className="headline mb-1 mt-4">Assumptions</div>
                    <ul className="caption" style={{ paddingLeft: 18, margin: 0 }}>
                      {result.assumptions.map((assumption) => (
                        <li key={assumption}>{assumption}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </Block>
          )}

          <Block>
            <Rationale>
              Nothing here is generated prose. Statements are the ones that passed
              the EARS, ambiguity and unsupported-quantity checks; acceptance
              criteria are the extracted ones; exception paths on a use case are
              the detected defects rather than invented failure modes. The one
              transformation that could have been generated — turning a
              requirement into a user story — is done by template, because a
              template that occasionally reads stiffly is better than a sentence
              that occasionally invents a user.
              <p className="mt-3 mb-0">
                The beneficiary in each story comes from the requirement&rsquo;s
                categories, not from its wording, and regulatory wins over
                functional when a requirement is both: the story is written for
                whoever will be asked to sign it off.
              </p>
            </Rationale>
          </Block>
        </>
      )}
    </ModuleShell>
  );
}
