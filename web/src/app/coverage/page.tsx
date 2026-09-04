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
import { useTaskReporter } from "@/components/chrome/StatusIsland";
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
  const [text, setText] = useState(SEED);
  const [report, setReport] = useState<Coverage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const reportTask = useTaskReporter();

  async function run(value: string) {
    setBusy(true);
    reportTask({ state: "running", label: "Assessing against the control pack" });
    try {
      const reports = await api.coverage(value);
      const first = reports[0] ?? null;
      setReport(first);
      setError(null);
      reportTask(
        first
          ? {
              state: "done",
              label: `${first.blocking_gaps.length} blocking gaps`,
              detail: `${Math.round(first.coverage_ratio * 100)}% of ${first.pack} covered`,
            }
          : { state: "done", label: "No applicable pack", detail: "nothing to assess" },
      );
    } catch (e) {
      setError((e as Error).message);
      setReport(null);
      reportTask({ state: "failed", label: "Assessment failed", detail: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    api
      .coverage(SEED)
      .then((reports) => !cancelled && setReport(reports[0] ?? null))
      .catch((e) => !cancelled && setError((e as Error).message));
    return () => {
      cancelled = true;
    };
  }, []);

  const gaps = report?.controls.filter((c) => c.is_gap) ?? [];
  const covered = report?.controls.filter((c) => !c.is_gap) ?? [];

  return (
    <ModuleShell
      pathname="/coverage"
      eyebrow="Coverage"
      title="Which mandatory controls nothing covers"
      lede="Every control in the pack cites the clause that establishes it — one without a citation is rejected before the pack loads."
      scene={<CoverageLayer controls={report?.controls ?? null} />}
      sceneCaption="The pack as a surface. A covered control is a solid tile standing proud of it; a gap is an open ring below it, red for a blocker and amber for a major. A coverage ratio invites you to feel good about a large number, but the number is not the finding — whether the gaps cluster in one area of the pack or scatter across it is the difference between one piece of work and twelve, and that is visible here and invisible in a percentage."
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
