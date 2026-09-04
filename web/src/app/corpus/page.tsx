"use client";

/**
 * Corpus — what the regulation actually says.
 *
 * Everything downstream is an assertion about this text, so it is the first
 * module: a reader who does not trust the source has no reason to trust a
 * coverage ratio derived from it. The graph is the primary surface here rather
 * than an illustration, which is why this is the one module that hands the
 * camera to the reader instead of driving it from scroll.
 *
 * The list beside it is not a fallback for the scene - it is the accessible
 * path to the same data, and the one that supports filtering, keyboard
 * navigation and copying a citation key.
 */

import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { Badge, Empty, Failure } from "@/components/ui";
import {
  api,
  type Clause,
  type Graph,
  type GraphNode,
  type SourceDocument,
} from "@/lib/api";

const CorpusLayer = dynamic(() => import("@/components/scenes/CorpusLayer"), {
  ssr: false,
});

function CorpusModule() {
  // A retrieval result links here with the clause it wants selected. Reading it
  // from the URL rather than from local state is what makes that link work at
  // all - and what lets a reader send someone else a link to one clause.
  const requested = useSearchParams().get("clause");

  const [graph, setGraph] = useState<Graph | null>(null);
  const [documents, setDocuments] = useState<SourceDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hovered, setHovered] = useState<GraphNode | null>(null);
  const [selected, setSelected] = useState<string | null>(requested);
  const [clause, setClause] = useState<Clause | null>(null);
  const [filter, setFilter] = useState(requested ?? "");

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([api.knowledgeGraph(), api.documents()]).then(([g, d]) => {
      if (cancelled) return;
      if (g.status === "fulfilled") setGraph(g.value);
      if (d.status === "fulfilled") setDocuments(d.value);
      // Only a total failure is reported as one. A partial result still shows
      // the reader something true.
      if (g.status === "rejected" && d.status === "rejected") {
        setError((g.reason as Error).message);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // The fetched clause is kept whatever the current selection is, and the
  // render decides whether it still applies. Clearing it from an effect on
  // deselect would be a second render pass to erase something the first pass
  // could simply not have drawn - and worse, between selecting a new clause and
  // its response arriving, the panel would still be showing the previous one.
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    api
      .clause(selected)
      .then((c) => !cancelled && setClause(c))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const shown = clause && clause.citation_key === selected ? clause : null;

  const clauses = useMemo(() => {
    const all = graph?.nodes.filter((n) => n.kind === "clause") ?? [];
    if (!filter.trim()) return all;
    const needle = filter.toLowerCase();
    return all.filter(
      (n) =>
        n.label.toLowerCase().includes(needle) ||
        n.detail.toLowerCase().includes(needle),
    );
  }, [graph, filter]);

  return (
    <ModuleShell
      pathname="/corpus"
      eyebrow="Corpus"
      title="What the regulation actually says"
      lede="Three sources, split into individually addressable clauses. Every citation the system emits resolves to one of these, or it is rejected before a reader ever sees it."
      scene={graph && <CorpusLayer graph={graph} onHover={setHovered} focus={selected} />}
      sceneCaption={
        hovered ? (
          <>
            <span className="mono">{hovered.label}</span> — {hovered.detail}
          </>
        ) : (
          "The corpus as a graph: documents are pinned, clauses settle around the document they belong to and nest by depth. Drag to orbit; hover a node to read it, or select a clause below to pull it forward."
        )
      }
    >
      {error && <Failure message={error} />}

      <Block title="Sources">
        {!documents && !error && <Empty>Loading the corpus…</Empty>}
        <div className="grid gap-3 sm:grid-cols-2">
          {documents?.map((document) => (
            <div key={document.short_code} className="glass p-5">
              <div className="mono mb-1.5" style={{ color: "var(--clause)" }}>
                {document.short_code}
              </div>
              <div className="headline">{document.title}</div>
              <div className="caption mt-1">{document.issuer}</div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Badge>{document.jurisdiction}</Badge>
                <Badge>version {document.version}</Badge>
                <Badge tone="var(--accent)">{document.clauses} clauses</Badge>
                {document.effective_from && (
                  <Badge>in force {document.effective_from}</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
        <Rationale>
          The corpus is representative text written to mirror the clause
          structure, numbering and terminology of the real instruments — not a
          verbatim copy of them. That is a deliberate limit. It means the
          retrieval and citation machinery is exercised against realistic
          structure, and it means nothing here should be relied on as legal
          advice about the actual Master Direction, DPDP Act or GDPR. Versions
          supersede rather than mutate, so a citation always resolves to the text
          that was in force when it was made.
        </Rationale>
      </Block>

      <Block
        title="Clauses"
        aside={
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="filter by key or heading…"
            className="caption"
            style={{
              background: "var(--glass)",
              border: "1px solid var(--hairline)",
              borderRadius: 10,
              padding: "7px 12px",
              color: "var(--text)",
              outline: "none",
              minWidth: 220,
            }}
          />
        }
      >
        <div className="glass" style={{ maxHeight: 420, overflowY: "auto", padding: 8 }}>
          {clauses.length === 0 && <Empty>Nothing matches that filter.</Empty>}
          {clauses.map((node) => {
            const active = selected === node.label;
            return (
              <button
                key={node.id}
                onClick={() => setSelected(active ? null : node.label)}
                className="block w-full text-left"
                style={{
                  background: active ? "var(--bg-inset)" : "transparent",
                  border: "1px solid",
                  borderColor: active ? "var(--hairline)" : "transparent",
                  borderRadius: 12,
                  padding: "10px 12px",
                  cursor: "pointer",
                  color: "inherit",
                }}
              >
                <span className="mono" style={{ color: "var(--clause)" }}>
                  {node.label}
                </span>
                <span className="caption" style={{ marginLeft: 10 }}>
                  {node.detail}
                </span>
              </button>
            );
          })}
        </div>

        {shown && (
          <article className="rise glass-raised mt-4 p-6">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="mono" style={{ color: "var(--clause)" }}>
                {shown.citation_key}
              </span>
              <Badge>{shown.document_code}</Badge>
              <Badge>{shown.jurisdiction}</Badge>
            </div>
            {shown.heading && <div className="headline mb-2">{shown.heading}</div>}
            <p className="body m-0" style={{ color: "var(--text-secondary)" }}>
              {shown.text}
            </p>
          </article>
        )}
      </Block>
    </ModuleShell>
  );
}

/**
 * `useSearchParams` needs a Suspense boundary above it, or the whole route opts
 * out of static rendering. The fallback is deliberately the page's own header
 * rather than a spinner: the module's title and question do not depend on the
 * query string, so there is no reason to withhold them.
 */
export default function CorpusPage() {
  return (
    <Suspense fallback={null}>
      <CorpusModule />
    </Suspense>
  );
}
