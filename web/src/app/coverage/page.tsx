"use client";

/**
 * Coverage — which mandatory controls nothing covers.
 *
 * The gap list is the output. A list of satisfied controls is reassurance, and
 * reassurance is not what anyone opens a compliance tool for, so the gaps are
 * ordered first and the ratio is deliberately not the headline.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { useJob } from "@/components/chrome/Jobs";
import { Badge, Button, Empty, Failure, Ring } from "@/components/ui";
import { api, type Coverage } from "@/lib/api";

const CoverageLayer = dynamic(() => import("@/components/scenes/CoverageLayer"), {
  ssr: false,
});

const SEED = [
  "The system shall screen the customer against the designated-persons list before activation.",
  "The system shall retain customer identification records for five years from cessation.",
  "The system shall verify the customer identity using officially valid documents.",
  "The system shall encrypt customer information transmitted over public networks.",
].join("\n");

function tone(control: { is_gap: boolean; severity: string }) {
  if (!control.is_gap) return "var(--confirmed)";
  return control.severity === "blocker" ? "var(--gap)" : "var(--review)";
}

export default function CoveragePage() {
  const { job, run: runJob } = useJob<Coverage | null>("coverage");
  const report = job.result ?? null;
  const error = job.error ?? null;
  const busy = job.state === "running";
  const [text, setText] = useState(job.input ?? SEED);

  async function run(value: string) {
    await runJob(
      value,
      async () => (await api.coverage(value))[0] ?? null,
      (first) =>
        first
          ? {
              label: `${first.blocking_gaps.length} blocking gaps`,
              detail: `${Math.round(first.coverage_ratio * 100)}% of ${first.pack} covered`,
            }
          : { label: "No applicable pack", detail: "nothing to assess" },
      { label: "Assessing against the control pack" },
    );
  }

  // Seeded once, and only when the module has no job - otherwise returning
  // here would discard whatever the reader had assessed.
  const untouched = job.state === "idle";
  useEffect(() => {
    if (!untouched) return;
    void run(SEED);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [untouched]);

  const gaps = report?.controls.filter((c) => c.is_gap) ?? [];
  const covered = report?.controls.filter((c) => !c.is_gap) ?? [];

  return (
    <ModuleShell
      pathname="/coverage"
      eyebrow="Coverage"
      title="Which mandatory controls nothing covers"
      lede="Every control in the pack cites the clause that establishes it — one without a citation is rejected before the pack loads."
      scene={<CoverageLayer controls={report?.controls ?? null} />}
      sceneCaption="Your requirements are the column on the left; the control pack is the grid on the right. A line means a requirement satisfies a control. A control is a gap for exactly one reason — nothing points at it — so the gaps are the rings with no thread reaching them, red for a blocker and amber for a major. The ratio below tells you how many; this tells you why, and shows whether the unreached controls cluster in one area of the pack or scatter across it. That is the difference between one piece of work and twelve."
    >
      <Block>
        <div className="glass-raised specular p-6 lg:p-8">
          <label className="caption mb-2 block">
            Requirements to assess, one per line
          </label>
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={4}
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
          <div className="mt-4 flex flex-wrap items-center gap-5">
            <Button onClick={() => run(text)} disabled={busy || !text.trim()}>
              {busy ? "Assessing…" : "Assess coverage"}
            </Button>
            {report && (
              <div className="flex items-center gap-5">
                <Ring
                  value={report.coverage_ratio}
                  size={78}
                  tone={
                    report.coverage_ratio > 0.7
                      ? "var(--confirmed)"
                      : report.coverage_ratio > 0.4
                        ? "var(--review)"
                        : "var(--gap)"
                  }
                />
                <div>
                  <div className="mono" style={{ color: "var(--gap)" }}>
                    {report.blocking_gaps.length} blocking
                  </div>
                  <div className="caption">
                    {report.pack} · v{report.pack_version}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </Block>

      {error && <Failure message={error} />}
      {!error && !report && <Empty>Assessing…</Empty>}

      {gaps.length > 0 && (
        <Block title={`Gaps — ${gaps.length}`}>
          <div className="grid gap-2 sm:grid-cols-2">
            {gaps.map((control, i) => (
              <div
                key={control.control_id}
                className="rise glass p-4"
                style={{
                  borderLeft: `2px solid ${tone(control)}`,
                  animationDelay: `${Math.min(i * 0.02, 0.4)}s`,
                }}
              >
                <div className="mono mb-1" style={{ color: "var(--text)" }}>
                  {control.control_id}
                </div>
                <div className="caption" style={{ lineHeight: 1.4 }}>
                  {control.title}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone={tone(control)}>{control.severity}</Badge>
                  {control.citations.slice(0, 1).map((citation) => (
                    <Badge key={citation} tone="var(--clause)">
                      {citation}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Block>
      )}

      {covered.length > 0 && (
        <Block title={`Covered — ${covered.length}`}>
          <div className="grid gap-2 sm:grid-cols-2">
            {covered.map((control) => (
              <div
                key={control.control_id}
                className="glass p-4"
                style={{ borderLeft: "2px solid var(--confirmed)", opacity: 0.72 }}
              >
                <div className="mono mb-1">{control.control_id}</div>
                <div className="caption" style={{ lineHeight: 1.4 }}>
                  {control.title}
                </div>
              </div>
            ))}
          </div>
        </Block>
      )}

      <Block>
        <Rationale>
          A control is only a gap when nothing in the submitted requirements
          satisfies its condition — the pack separates <span className="mono">
          applies_when</span> from <span className="mono">satisfied_when</span> so
          a control that does not apply is not counted as covered either. Twelve
          of the twenty-one are blockers. The mapping that decides satisfaction
          is the same two-signal agreement gate used for citations, and it
          returns <span className="mono">needs_review</span> far more often than
          it returns a decision, which is the intended behaviour: an
          automatically cleared control that was not really covered is the most
          expensive output this system could produce.
        </Rationale>
      </Block>
    </ModuleShell>
  );
}
