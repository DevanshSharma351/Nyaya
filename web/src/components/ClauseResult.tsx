"use client";

/**
 * One retrieval result, expandable.
 *
 * Results used to be inert: six clauses printed on the page with nothing to do
 * with them. A reader who wants to act on the top result needs the whole
 * clause, the context that made it match, and a way to reach it in the corpus -
 * all of which existed and none of which was reachable.
 *
 * The score presentation is the other half of this. The raw cross-encoder
 * number was shown as "relevance 0.077", which reads as "8% relevant" and is
 * not what it means. Measured on the 34-query labelled set, the score's
 * predictive value is real but weak, and *rank* is far stronger: the top result
 * is the governing clause 82% of the time, the second only 29%. So rank leads,
 * the score is banded by measured precision, and the raw value stays available
 * for anyone who wants it.
 */

import { useEffect, useState } from "react";
import { ChevronRight, ExternalLink } from "lucide-react";
import Link from "next/link";
import { api, type Clause } from "@/lib/api";
import { Badge } from "./ui";

/**
 * Bands fitted on the labelled set, with the precision each one carries.
 *
 * The same caveat as every other figure here applies: single annotator, and the
 * thresholds are fitted on the set they are reported on. The bands are coarse
 * on purpose, because the underlying signal does not support finer ones - the
 * [0.2, 0.5) band held four results in total.
 */
const BANDS: { min: number; label: string; precision: string; tone: string }[] = [
  { min: 0.5, label: "strong", precision: "7 in 10 were the governing clause", tone: "var(--confirmed)" },
  { min: 0.05, label: "moderate", precision: "4 in 10 were the governing clause", tone: "var(--review)" },
  { min: 0, label: "weak", precision: "under 2 in 10 were the governing clause", tone: "var(--text-tertiary)" },
];

function bandFor(relevance: number | null) {
  if (relevance === null) return null;
  return BANDS.find((b) => relevance >= b.min) ?? BANDS[BANDS.length - 1];
}

export default function ClauseResult({
  clause,
  rank,
  delay = 0,
}: {
  clause: Clause;
  rank: number;
  delay?: number;
}) {
  const [open, setOpen] = useState(rank === 1);
  const [full, setFull] = useState<Clause | null>(null);
  const band = bandFor(clause.relevance);

  // The search response carries the clause body already, but not its enclosing
  // clauses. Fetching the canonical record on expand is what makes "open the
  // full text" mean the text in the corpus rather than the snippet that
  // happened to be returned.
  useEffect(() => {
    if (!open || full) return;
    let cancelled = false;
    api
      .clause(clause.citation_key)
      .then((c) => !cancelled && setFull(c))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [open, full, clause.citation_key]);

  const body = full?.text ?? clause.text;

  return (
    <article
      className="rise glass mb-3"
      style={{ animationDelay: `${delay}s`, overflow: "hidden" }}
    >
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 p-5 text-left"
        style={{ background: "transparent", border: "none", cursor: "pointer", color: "inherit" }}
      >
        <span
          className="mono"
          style={{
            color: rank === 1 ? "var(--text)" : "var(--text-tertiary)",
            fontWeight: rank === 1 ? 600 : 450,
            minWidth: 18,
            paddingTop: 2,
          }}
        >
          {rank}
        </span>

        <span className="min-w-0 flex-1">
          <span className="mb-2 flex flex-wrap items-center gap-2">
            <span className="mono" style={{ color: "var(--text)", fontWeight: 550 }}>
              {clause.citation_key}
            </span>
            <Badge>{clause.jurisdiction}</Badge>
            {band && (
              <Badge tone={band.tone}>
                {band.label}
                {clause.relevance !== null && ` · ${clause.relevance.toFixed(3)}`}
              </Badge>
            )}
          </span>
          {clause.heading && <span className="headline block">{clause.heading}</span>}
          {!open && (
            <span
              className="caption mt-1 block"
              style={{
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {clause.text}
            </span>
          )}
        </span>

        <ChevronRight
          size={16}
          style={{
            color: "var(--text-tertiary)",
            flexShrink: 0,
            marginTop: 2,
            transform: open ? "rotate(90deg)" : "none",
            transition: "transform 0.2s cubic-bezier(0.16,1,0.3,1)",
          }}
        />
      </button>

      {open && (
        <div className="px-5 pb-5" style={{ paddingLeft: 46 }}>
          <p className="body m-0" style={{ color: "var(--text-secondary)" }}>
            {body}
          </p>

          {band && (
            <p className="caption mt-3 mb-0">
              Ranked {rank} of the shortlist. On the labelled set a {band.label} score
              meant {band.precision}; the top result was the governing clause 82% of the
              time, the second 29%.
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link
              href={`/corpus?clause=${encodeURIComponent(clause.citation_key)}`}
              className="caption inline-flex items-center gap-1.5"
              style={{ color: "var(--text)", textDecoration: "none" }}
            >
              <ExternalLink size={13} />
              open in the corpus
            </Link>
            <button
              onClick={() => navigator.clipboard?.writeText(clause.citation_key)}
              className="caption"
              style={{
                background: "transparent",
                border: "1px solid var(--hairline)",
                borderRadius: 8,
                padding: "4px 10px",
                cursor: "pointer",
                color: "var(--text-secondary)",
              }}
            >
              copy citation key
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
