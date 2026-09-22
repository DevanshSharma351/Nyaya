"use client";

/**
 * Retrieval — which clause governs this?
 *
 * The queries offered here are written the way a stakeholder speaks, sharing
 * almost no vocabulary with the regulation, because that is the case that
 * matters. Anyone can find a clause by quoting it.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { Block, ModuleShell, Rationale } from "@/components/chrome/ModuleShell";
import { useJob } from "@/components/chrome/Jobs";
import ClauseResult from "@/components/ClauseResult";
import { Button, Empty, Failure } from "@/components/ui";
import { api, type Clause } from "@/lib/api";

const RetrievalLayer = dynamic(() => import("@/components/scenes/RetrievalLayer"), {
  ssr: false,
});

const EXAMPLES = [
  "check every new customer against the sanctions list before their account goes live",
  "how long do we keep proof of identity checks after someone closes their account",
  "the selfie step needs to prove the person is actually there, not a photo",
  "can we open an account for someone who will not say who really owns the company",
];

export default function RetrievalPage() {
  const { job, run: runJob } = useJob<Clause[]>("retrieval");
  const results = job.result ?? null;
  const error = job.error ?? null;
  const busy = job.state === "running";

  const [query, setQuery] = useState(job.input ?? EXAMPLES[0]);
  const [corpusSize, setCorpusSize] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => !cancelled && setCorpusSize(h.corpus_clauses))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  // The first example runs on arrival. Retrieval is fast enough for that - it
  // is a vector lookup and a rerank, not a language model - and a module that
  // opens with an empty panel and an empty result list gives a reader nothing
  // to judge. Landing on a worked example is also how the scene becomes
  // legible: with no results there are no columns in it.
  // The first example runs on arrival, but only when the module has no job
  // already. Seeding unconditionally would discard the reader's own search
  // every time they navigated back to this page.
  const untouched = job.state === "idle";
  useEffect(() => {
    if (!untouched) return;
    void run(EXAMPLES[0]);
    // Deliberately keyed on nothing else: this is a one-shot seed, and
    // depending on `run` would re-fire it whenever the query text changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [untouched]);

  async function run(value: string) {
    await runJob(
      value,
      () => api.search(value, 6),
      (found) => {
        const best = found[0]?.relevance;
        return {
          label: `${found.length} clauses`,
          detail:
            found.length === 0
              ? "nothing matched"
              : `top ${found[0].citation_key}${best != null ? ` - ${best.toFixed(3)}` : ""}`,
        };
      },
      { label: "Searching the corpus" },
    );
  }

  return (
    <ModuleShell
      pathname="/retrieval"
      eyebrow="Retrieval"
      title="Ask in plain language, get the governing clause"
      lede="Dense retrieval over the corpus finds candidates; a cross-encoder reorders the shortlist."
      scene={<RetrievalLayer clauses={results} busy={busy} corpusSize={corpusSize} />}
      sceneCaption="The faint field is the corpus — one point per indexed clause, so the size of the haystack is the number the API reports, not a metaphor. The bars are the results, ordered by rank left to right, with height set by the reranker's score. Rank and score disagree more often than people expect: a shortlist can be correctly ordered and still contain nothing worth reading, and a row of six low bars says so at a glance."
    >
      <Block>
        <div className="glass-raised specular p-6 lg:p-8">
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && run(query)}
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
            {EXAMPLES.map((example) => (
              <button
                key={example}
                onClick={() => {
                  setQuery(example);
                  run(example);
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
                {example.length > 54 ? `${example.slice(0, 54)}…` : example}
              </button>
            ))}
          </div>
        </div>
      </Block>

      <Block>
        {error && <Failure message={error} />}
        {!error && results === null && (
          <Empty>Run a search to see which clauses govern it.</Empty>
        )}
        {results?.map((clause, i) => (
          <ClauseResult
            key={clause.citation_key}
            clause={clause}
            rank={i + 1}
            delay={i * 0.045}
          />
        ))}
        {results?.length === 0 && <Empty>No clause in the corpus matched.</Empty>}

        <Rationale>
          <p className="m-0">
            Candidates are reranked with their enclosing clauses attached. Scoring
            a bare sub-clause asks the model to judge a fragment — “screening shall
            be performed prior to activation” never says what is being screened
            against, because that is in the parent — and the reranker responded by
            preferring the general parent clause over the specific sub-clause that
            actually governs. Attaching context moved MRR from 0.723 to 0.819 and
            recall@10 from 0.779 to 0.824 on the labelled set.
          </p>
          <p className="mt-3 mb-0">
            Lexical fusion is switched off, by measurement rather than preference.
            The first implementation conjoined every query term, so a fifteen-word
            question demanded one clause containing all nine stemmed terms and
            returned nothing; rewritten as a disjunction it reached MRR 0.249,
            still below dense retrieval alone. Fusing a weaker signal in made the
            ranking worse.
          </p>
          <p className="mt-3 mb-0">
            The scores themselves are weak evidence taken alone — the bands above
            are fitted on the same 34-query set they are reported on, with a
            single annotator, so treat them as optimistic. Rank is the stronger
            signal and is why it leads.
          </p>
        </Rationale>
      </Block>
    </ModuleShell>
  );
}
