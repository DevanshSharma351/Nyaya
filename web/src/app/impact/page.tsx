"use client";

/**
 * Impact — the regulator amended it, what is now wrong?
 *
 * This is the module that justifies the citation discipline in all the others.
 * Requirements that merely reference "KYC rules" cannot be re-checked when the
 * rules change; requirements pinned to a clause key can. The walk compares two
 * versions of a source, then reports every requirement whose authority moved
 * under it.
 *
 * Two severities, and the distinction matters. A stale requirement cites a
 * clause whose text changed - it may still be right, and a human has to read
 * it. An orphaned one cites a clause that no longer exists, and is wrong now.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { useJob } from "@/components/chrome/Jobs";
import { Badge, Button, Empty, Failure } from "@/components/ui";
import { api, type Impact, type SourceDocument } from "@/lib/api";

const ImpactLayer = dynamic(() => import("@/components/scenes/ImpactLayer"), {
  ssr: false,
});

const SEVERITY_TONE: Record<string, string> = {
  orphaned: "var(--gap)",
  stale: "var(--review)",
};

export default function ImpactPage() {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [code, setCode] = useState("RBI-MD-KYC");
  const [from, setFrom] = useState("1");
  const [to, setTo] = useState("2");
  const { job, run: runJob } = useJob<Impact>("impact");
  const impact = job.result ?? null;
  const error = job.error ?? null;
  const busy = job.state === "running";

  useEffect(() => {
    let cancelled = false;
    api
      .documents()
      .then((d) => !cancelled && setDocuments(d))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // Only sources that actually hold two versions can be compared. The selector
  // used to list every source, so choosing one with a single version returned a
  // 404 the reader had done nothing to cause - an interface offering an action
  // it knows will fail.
  const comparable = documents.filter((d) => d.versions.length > 1);
  const selected = comparable.find((d) => d.short_code === code);
  const availableVersions = selected?.versions ?? [];

  const run = useCallback(async () => {
    await runJob(
      `${code} v${from} to v${to}`,
      () => api.impact(code, from, to),
      (result) => ({
        label: `${result.affected.length} affected`,
        detail: `${result.changed_clauses.length} amended, ${result.removed_clauses.length} removed`,
      }),
      { label: "Walking the amendment" },
    );
  }, [code, from, to, runJob]);

  // The default scenario is loaded once on mount. It deliberately does not
  // re-run when the fields change: typing "12" on the way to "12.1" would fire
  // a 404 for the intermediate value and paint an error the reader never
  // caused. Analysing is an explicit action.
  // Seeded once, and only when the module has no job.
  const untouched = job.state === "idle";
  useEffect(() => {
    if (!untouched) return;
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [untouched]);

  const field = {
    background: "var(--glass)",
    border: "1px solid var(--hairline)",
    borderRadius: 12,
    padding: "10px 14px",
    color: "var(--text)",
    outline: "none",
  } as const;

  return (
    <ModuleShell
      pathname="/impact"
      eyebrow="Impact"
      title="The regulator amended it — what is now wrong?"
      lede="Two versions of a source are compared, and every requirement whose authority moved underneath it is reported."
      scene={<ImpactLayer impact={impact} />}
      sceneCaption="The clauses that changed sit at the centre; the requirements that cited them are on the ring — amber where the clause was amended and the requirement may now be stale, red where it was removed and the requirement is orphaned. The travelling pulses are the only continuous animation in this interface, and they earn it: a static edge says the dependency exists, a pulse says it carries."
    >
      <Block>
        <div className="glass-raised specular p-6 lg:p-8">
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto]">
            <label className="flex flex-col gap-1.5">
              <span className="caption">Source</span>
              <select
                value={code}
                onChange={(event) => {
                  const next = event.target.value;
                  setCode(next);
                  // Move the version fields to a pair that exists for the newly
                  // chosen source, rather than carrying over one that does not.
                  const versions =
                    comparable.find((d) => d.short_code === next)?.versions ?? [];
                  if (versions.length > 1) {
                    setFrom(versions[versions.length - 2]);
                    setTo(versions[versions.length - 1]);
                  }
                }}
                className="body"
                style={field}
              >
                {comparable.length === 0 && <option value={code}>{code}</option>}
                {comparable.map((document) => (
                  <option key={document.short_code} value={document.short_code}>
                    {document.short_code} · {document.versions.length} versions
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="caption">From version</span>
              <select
                value={from}
                onChange={(event) => setFrom(event.target.value)}
                className="body"
                style={field}
              >
                {(availableVersions.length ? availableVersions : [from]).map((v) => (
                  <option key={v} value={v}>
                    v{v}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="caption">To version</span>
              <select
                value={to}
                onChange={(event) => setTo(event.target.value)}
                className="body"
                style={field}
              >
                {(availableVersions.length ? availableVersions : [to]).map((v) => (
                  <option key={v} value={v}>
                    v{v}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-end">
              <Button onClick={run} disabled={busy}>
                {busy ? "Walking…" : "Analyse"}
              </Button>
            </div>
          </div>
        </div>
      </Block>

      {error && (
        <Block>
          <Failure message={error} />
          <p className="caption mt-3">
            Amendment analysis needs both the superseded text and the text that
            replaced it, because the comparison is what produces the finding. Only
            sources holding more than one version are offered above; seed another
            with <span className="mono">make seed</span>.
          </p>
        </Block>
      )}

      {comparable.length === 0 && documents.length > 0 && !error && (
        <Block>
          <div className="glass p-6">
            <div className="headline mb-2">Nothing to compare yet</div>
            <p className="caption m-0" style={{ maxWidth: 640 }}>
              Every source in the corpus holds a single version, so there is no
              amendment to analyse. <span className="mono">make seed</span> ingests
              one: three edits to the Master Direction that between them amend a
              clause, change a quantity inside a clause, and remove a clause
              outright — the three cases this walk distinguishes.
            </p>
          </div>
        </Block>
      )}

      {impact && (
        <>
          <Block>
            <div className="glass p-6">
              <p className="body m-0">{impact.summary}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge tone="var(--review)">
                  {impact.changed_clauses.length} amended
                </Badge>
                <Badge tone="var(--gap)">
                  {impact.removed_clauses.length} removed
                </Badge>
                <Badge tone="var(--accent)">{impact.added_clauses.length} added</Badge>
              </div>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {[
                  ...impact.changed_clauses.map((k) => [k, "var(--review)"] as const),
                  ...impact.removed_clauses.map((k) => [k, "var(--gap)"] as const),
                  ...impact.added_clauses.map((k) => [k, "var(--accent)"] as const),
                ].map(([key, colour]) => (
                  <Badge key={key} tone={colour}>
                    {key}
                  </Badge>
                ))}
              </div>
            </div>
          </Block>

          <Block title={`Affected requirements — ${impact.affected.length}`}>
            {impact.affected.length === 0 && (
              <Empty>
                No requirement in the database cited any of the clauses that
                changed. That is a real result, not an empty state — nothing
                needs re-approval.
              </Empty>
            )}
            {impact.affected.map((affected, i) => (
              <article
                key={`${affected.ref}-${affected.citation_key}`}
                className="rise glass mb-3 p-5"
                style={{
                  borderLeft: `2px solid ${SEVERITY_TONE[affected.severity] ?? "var(--review)"}`,
                  animationDelay: `${Math.min(i * 0.04, 0.35)}s`,
                }}
              >
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="mono">{affected.ref}</span>
                  <Badge tone={SEVERITY_TONE[affected.severity] ?? "var(--review)"}>
                    {affected.severity}
                  </Badge>
                  <Badge tone="var(--clause)">{affected.citation_key}</Badge>
                </div>
                <p className="body m-0">{affected.statement}</p>
                <p className="caption mt-2 mb-0">{affected.detail}</p>
              </article>
            ))}
          </Block>
        </>
      )}

      <Block>
        <Rationale>
          The comparison normalises whitespace and line wrapping before
          diffing. Without that, re-ingesting identical text with a different
          line width reports every clause as amended, and a change report that
          cries wolf is one nobody reads. Clause identity is the citation key,
          not position, so inserting a clause in the middle of a document does
          not shift the identity of everything after it. What this does not do
          is judge whether an amendment actually invalidates a requirement — it
          reports that the authority moved and routes it to a human. Deciding
          that automatically is exactly the kind of confident wrong answer this
          system is built to avoid.
        </Rationale>
      </Block>
    </ModuleShell>
  );
}
