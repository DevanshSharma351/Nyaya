"use client";

/**
 * Coverage — which mandatory statutory controls nothing covers.
 *
 * Connected to project database: Automatically loads coverage evaluation
 * for the selected project's requirements against statutory packs (e.g. RBI eKYC, GDPR).
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { ProjectSelector } from "@/components/chrome/ProjectSelector";
import { useJob } from "@/components/chrome/Jobs";
import { Badge, Button, Empty, Failure, Ring } from "@/components/ui";
import { api, type Coverage } from "@/lib/api";

const CoverageLayer = dynamic(() => import("@/components/scenes/CoverageLayer"), {
  ssr: false,
});

function tone(control: { is_gap: boolean; severity: string }) {
  if (!control.is_gap) return "var(--confirmed)";
  return control.severity === "blocker" ? "var(--gap)" : "var(--review)";
}

export default function CoveragePage() {
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectReport, setProjectReport] = useState<Coverage | null>(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [showCustomPrompt, setShowCustomPrompt] = useState(false);
  const [customMode, setCustomMode] = useState(false);
  const projectRequest = useRef(0);

  // Ad-hoc job runner
  const { job, run: runJob } = useJob<Coverage | null>("coverage");
  const [customText, setCustomText] = useState(job.input ?? "");

  const loadCoverageForProject = useCallback(async (id: string) => {
    const request = ++projectRequest.current;
    setCustomMode(false);
    setSelectedProjectId(id);
    setProjectReport(null);
    setProjectLoading(true);
    setProjectError(null);
    try {
      const reports = await api.generateCoverage(id);
      if (request !== projectRequest.current) return;
      const first = reports[0] ?? null;
      setProjectReport(first);
      sessionStorage.setItem("nyaya_project_id", id);
    } catch (err: unknown) {
      if (request === projectRequest.current) setProjectError((err as Error).message || "Failed to generate coverage for project");
    } finally {
      if (request === projectRequest.current) setProjectLoading(false);
    }
  }, []);

  // On mount: check sessionStorage or first project
  useEffect(() => {
    let cancelled = false;
    const saved = typeof window !== "undefined" ? sessionStorage.getItem("nyaya_project_id") : null;
    if (saved) {
      queueMicrotask(() => {
        if (!cancelled) {
          setSelectedProjectId(saved);
          loadCoverageForProject(saved);
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
      loadCoverageForProject(firstId);
    }).catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [loadCoverageForProject]);

  const handleSelectProject = (id: string) => {
    loadCoverageForProject(id);
  };

  async function runCustom() {
    if (!customText.trim()) return;
    projectRequest.current += 1;
    setProjectLoading(false);
    setCustomMode(true);
    await runJob(
      customText,
      async () => (await api.coverage(customText))[0] ?? null,
      (first) =>
        first
          ? {
              label: `${first.blocking_gaps.length} blocking gaps`,
              detail: `${Math.round(first.coverage_ratio * 100)}% of ${first.pack} matched`,
            }
          : { label: "No applicable pack", detail: "nothing to assess" },
      { label: "Assessing against the control pack" },
    );
  }

  const report = customMode ? job.result ?? null : projectReport;
  const busy = customMode ? job.state === "running" : projectLoading;
  const error = customMode ? job.error ?? null : projectError;

  const gaps = report?.controls.filter((c) => c.is_gap) ?? [];
  const covered = report?.controls.filter((c) => !c.is_gap) ?? [];

  return (
    <ModuleShell
      pathname="/coverage"
      eyebrow="Compliance Coverage"
      title="Statutory Control Pack Coverage"
      lede="See which controls match the project’s requirements and which need attention. Citation verification happens in Workflow."
      scene={<CoverageLayer controls={report?.controls ?? null} />}
      sceneCaption="Your requirements are the column on the left; the control pack is the grid on the right. Red nodes represent blocking gaps; amber represents major gaps; green indicates satisfied controls."
    >
      {/* Unified Project Selector Bar */}
      <Block>
        <ProjectSelector
          activeModule="coverage"
          currentProjectId={selectedProjectId}
          onSelectProject={handleSelectProject}
        />
      </Block>

      {/* Coverage Status Summary */}
      {report && (
        <Block>
          <div className="glass-raised p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="flex items-center gap-6">
              <Ring
                value={report.coverage_ratio}
                size={84}
                tone={
                  report.coverage_ratio > 0.7
                    ? "var(--confirmed)"
                    : report.coverage_ratio > 0.4
                      ? "var(--review)"
                      : "var(--gap)"
                }
              />
              <div>
                <div className="flex items-center gap-2">
                  <ShieldCheck size={18} className="text-[var(--accent)]" />
                  <span className="headline text-lg font-semibold">{report.pack}</span>
                  <Badge tone="var(--clause)">v{report.pack_version}</Badge>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-3">
                  {customMode && <span className="caption">Custom text assessment</span>}
                  <span className="mono font-bold" style={{ color: "var(--gap)" }}>
                    {report.blocking_gaps.length} Blocking Gaps
                  </span>
                  <span className="caption text-[var(--text-secondary)]">&bull;</span>
                  <span className="mono font-medium text-[var(--confirmed)]">
                    {covered.length} of {report.controls.length} controls matched
                  </span>
                  <span className="caption text-[var(--text-secondary)]">&bull;</span>
                  <span className="caption text-[var(--text-secondary)]">
                    {Math.round(report.coverage_ratio * 100)}% control pack coverage
                  </span>
                </div>
              </div>
            </div>

            <Button
              variant="quiet"
              onClick={() => selectedProjectId && loadCoverageForProject(selectedProjectId)}
              disabled={busy || !selectedProjectId}
            >
              <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
              {customMode ? "Show selected project" : "Re-assess Coverage"}
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
              Evaluating requirements against statutory control pack…
            </div>
          </div>
        </Block>
      )}

      {!busy && !error && !report && (
        <Block>
          <Empty>{selectedProjectId || customMode ? "No control pack applies to this assessment." : "Select a project to assess control pack coverage."}</Empty>
        </Block>
      )}

      {/* Gaps List */}
      {gaps.length > 0 && (
        <Block title={`Compliance Gaps (${gaps.length})`}>
          <div className="grid gap-3 sm:grid-cols-2">
            {gaps.map((control, i) => (
              <div
                key={control.control_id}
                className="rise glass p-4"
                style={{
                  borderLeft: `3px solid ${tone(control)}`,
                  animationDelay: `${Math.min(i * 0.02, 0.4)}s`,
                }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="mono font-semibold" style={{ color: "var(--text)" }}>
                    {control.control_id}
                  </span>
                  <Badge tone={tone(control)}>{control.severity.toUpperCase()}</Badge>
                </div>
                <div className="caption font-medium mb-2" style={{ lineHeight: 1.4 }}>
                  {control.title}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {control.citations.map((citation) => (
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

      {/* Covered Controls List */}
      {covered.length > 0 && (
        <Block title={`Matched Controls (${covered.length})`}>
          <div className="grid gap-3 sm:grid-cols-2">
            {covered.map((control) => (
              <div
                key={control.control_id}
                className="glass p-4"
                style={{ borderLeft: "3px solid var(--confirmed)", opacity: 0.85 }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="mono font-semibold text-[var(--confirmed)]">{control.control_id}</span>
                  <Badge tone="var(--confirmed)">RULE MATCH</Badge>
                </div>
                <div className="caption" style={{ lineHeight: 1.4 }}>
                  {control.title}
                </div>
                {control.citations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {control.citations.map((citation) => (
                      <Badge key={citation} tone="var(--clause)">
                        {citation}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Block>
      )}

      {/* Rationale */}
      <Block>
        <Rationale>
          A control is only a gap when nothing in the submitted requirements
          satisfies its condition — the pack separates <span className="mono">
          applies_when</span> from <span className="mono">satisfied_when</span> so
          a control that does not apply is not counted as covered either.
          Each match is a preliminary rule result. Review the supporting citations in Workflow.
        </Rationale>
      </Block>

      {/* Ad-hoc Custom Input Accordion */}
      <Block>
        <div className="mt-4 pt-4 border-t border-[var(--hairline)]">
          <button
            type="button"
            onClick={() => setShowCustomPrompt(!showCustomPrompt)}
            className="caption text-[var(--text-tertiary)] hover:text-[var(--text)] inline-flex items-center gap-1.5 transition-colors"
          >
            <Sparkles size={13} />
            {showCustomPrompt ? "Hide Custom Text Evaluator" : "Evaluate Ad-Hoc Text (Custom Input Mode)"}
          </button>

          {showCustomPrompt && (
            <div className="glass-raised p-6 mt-3 rounded-xl border border-[var(--hairline)]">
              <label className="caption mb-2 block font-medium">Requirements to assess (one per line):</label>
              <textarea
                value={customText}
                onChange={(event) => setCustomText(event.target.value)}
                rows={4}
                placeholder="The system shall screen the customer against the designated-persons list before activation.&#10;The system shall retain customer identification records for five years from cessation."
                className="body w-full rounded-xl border border-[var(--hairline)] bg-[var(--bg-inset)] p-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--focus)]"
              />
              <div className="mt-3 flex items-center gap-3">
                <Button onClick={runCustom} disabled={busy || !customText.trim()}>
                  {busy ? "Assessing…" : "Assess Custom Text"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Block>
    </ModuleShell>
  );
}
