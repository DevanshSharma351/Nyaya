"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, type ExtractResult } from "@/lib/api";
import { Badge, Button, Empty, Failure, Panel, SectionHeading, spring } from "./ui";

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

export default function Extraction() {
  const [text, setText] = useState(SEED);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.extract(text));
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="p-8 lg:p-10" delay={0.05}>
      <SectionHeading
        eyebrow="Extraction"
        title="Stakeholder prose into testable obligations"
        lede="Rewritten into EARS form, compounds split so each obligation can be approved and traced separately, and every quantity checked against the source — a threshold nobody stated is a fabricated requirement."
      />

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
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
        <span className="caption">
          runs a local model — expect 40–100 seconds
        </span>
      </div>

      <div className="mt-7">
        {error && <Failure message={error} />}
        {busy && (
          <div className="glass p-5">
            <div
              className="sheen"
              style={{
                height: 10,
                borderRadius: 5,
                WebkitBackgroundClip: "padding-box",
              }}
            />
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
                  result.testable_fraction === 1
                    ? "var(--confirmed)"
                    : "var(--review)"
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

            <AnimatePresence>
              {result.requirements.map((req, i) => (
                <motion.article
                  key={req.statement}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ ...spring, delay: i * 0.07 }}
                  className="glass mb-3 p-5"
                >
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <Badge tone="var(--accent)">{req.ears_pattern}</Badge>
                    <Badge tone={RISK_TONE[req.risk_level]}>{req.risk_level}</Badge>
                    <Badge>{req.priority}</Badge>
                    {req.categories.slice(0, 3).map((c) => (
                      <Badge key={c} tone="var(--clause)">
                        {c}
                      </Badge>
                    ))}
                  </div>

                  <p className="body m-0" style={{ fontWeight: 500 }}>
                    {req.statement}
                  </p>

                  {req.acceptance_criteria.length > 0 && (
                    <ul
                      className="caption mt-3"
                      style={{ paddingLeft: 18, margin: 0 }}
                    >
                      {req.acceptance_criteria.map((c) => (
                        <li key={c} style={{ marginBottom: 4 }}>
                          {c}
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
                    traced to: “{req.quoted_source}”
                  </div>

                  {req.defects.length > 0 && (
                    <div className="mt-3 flex flex-col gap-1.5">
                      {req.defects.map((d, k) => (
                        <div
                          key={k}
                          className="caption"
                          style={{
                            color:
                              d.severity === "major" || d.severity === "blocker"
                                ? "var(--gap)"
                                : "var(--review)",
                          }}
                        >
                          <span className="mono">{d.detector}</span> — {d.detail}
                        </div>
                      ))}
                    </div>
                  )}
                </motion.article>
              ))}
            </AnimatePresence>

            {result.unclear.length > 0 && (
              <div className="glass mt-4 p-5">
                <div className="headline mb-2" style={{ color: "var(--review)" }}>
                  Open questions
                </div>
                <p className="caption mb-3">
                  Raised rather than answered. Inventing a missing value produces
                  a requirement that reads as precise and was never agreed.
                </p>
                <ul className="body" style={{ paddingLeft: 18, margin: 0, color: "var(--text-secondary)" }}>
                  {result.unclear.map((q) => (
                    <li key={q} style={{ marginBottom: 6 }}>
                      {q}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}
