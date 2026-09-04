"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, type Clause } from "@/lib/api";
import { Badge, Button, Empty, Failure, Panel, SectionHeading, spring } from "./ui";

const EXAMPLES = [
  "check every new customer against the sanctions list before their account goes live",
  "how long do we keep proof of identity checks after someone closes their account",
  "the selfie step needs to prove the person is actually there, not a photo",
  "can we open an account for someone who will not say who really owns the company",
];

export default function Retrieval() {
  const [query, setQuery] = useState(EXAMPLES[0]);
  const [results, setResults] = useState<Clause[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(q: string) {
    setBusy(true);
    setError(null);
    try {
      setResults(await api.search(q, 6));
    } catch (e) {
      setError((e as Error).message);
      setResults(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel className="p-8 lg:p-10">
      <SectionHeading
        eyebrow="Retrieval"
        title="Ask in plain language, get the governing clause"
        lede="Queries are written the way stakeholders speak, sharing almost no vocabulary with the regulation. Dense retrieval finds the clause; a cross-encoder reorders the shortlist."
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run(query)}
          placeholder="Describe the obligation in your own words…"
          className="body flex-1"
          style={{
            background: "var(--glass)",
            border: "1px solid var(--hairline)",
            borderRadius: 12,
            padding: "12px 15px",
            color: "var(--text)",
            outline: "none",
          }}
        />
        <Button onClick={() => run(query)} disabled={busy || !query.trim()}>
          {busy ? "Searching…" : "Search"}
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {EXAMPLES.map((e) => (
          <button
            key={e}
            onClick={() => {
              setQuery(e);
              run(e);
            }}
            className="caption"
            style={{
              background: "var(--glass)",
              border: "1px solid var(--hairline)",
              borderRadius: 999,
              padding: "5px 12px",
              cursor: "pointer",
              color: "var(--text-secondary)",
              textAlign: "left",
            }}
          >
            {e.length > 54 ? `${e.slice(0, 54)}…` : e}
          </button>
        ))}
      </div>

      <div className="mt-7">
        {error && <Failure message={error} />}
        {!error && results === null && (
          <Empty>Run a search to see which clauses govern it.</Empty>
        )}
        <AnimatePresence mode="popLayout">
          {results?.map((clause, i) => (
            <motion.article
              key={clause.citation_key}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ ...spring, delay: i * 0.045 }}
              className="glass mb-3 p-5"
            >
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="mono" style={{ color: "var(--clause)" }}>
                  {clause.citation_key}
                </span>
                <Badge>{clause.jurisdiction}</Badge>
                {clause.relevance !== null && (
                  <Badge
                    tone={
                      clause.relevance > 0.7
                        ? "var(--confirmed)"
                        : clause.relevance > 0.3
                          ? "var(--review)"
                          : "var(--text-tertiary)"
                    }
                  >
                    relevance {clause.relevance.toFixed(3)}
                  </Badge>
                )}
              </div>
              {clause.heading && (
                <div className="headline mb-1">{clause.heading}</div>
              )}
              <p className="body m-0" style={{ color: "var(--text-secondary)" }}>
                {clause.text}
              </p>
            </motion.article>
          ))}
        </AnimatePresence>
        {results?.length === 0 && <Empty>No clause in the corpus matched.</Empty>}
      </div>
    </Panel>
  );
}
