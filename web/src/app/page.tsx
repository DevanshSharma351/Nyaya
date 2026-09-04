"use client";

/**
 * The landing module.
 *
 * Its job is orientation, not persuasion: what this is, what it refuses to do,
 * and where to go next. Everything that used to be stacked on this page now
 * lives behind its own route, which is the change that makes the application
 * navigable - a reader arrives with one question and should reach the module
 * that answers it in one click, not by scrolling past five others.
 */

import Link from "next/link";
import dynamic from "next/dynamic";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { MODULES } from "@/components/chrome/modules";
import { api, type Health } from "@/lib/api";

const HeroLayer = dynamic(() => import("@/components/scenes/HeroLayer"), {
  ssr: false,
});

// Figures, not states. They are set in ink rather than colour because
// colouring a measurement makes it look like a verdict.
const CLAIMS: [string, string][] = [
  ["1.000", "precision on the auto-accept tier"],
  ["0", "false confirmations measured"],
  ["0.143", "expected calibration error"],
];

export default function Landing() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => !cancelled && setHealth(h))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <HeroLayer />

      <main className="content-layer pb-36 pl-0 md:pl-[236px]">
        <div className="mx-auto max-w-5xl px-6 lg:px-12">
          {/* The hero is deliberately tall. The scene resolves from scattered
              prose into three ordered tiers as the reader scrolls through it,
              and that needs travel to happen in. */}
          <section className="flex min-h-[92vh] flex-col justify-center py-24">
            <div className="rise">
              <div className="eyebrow mb-5">न्याय · Nyaya</div>
              <h1 className="display m-0 max-w-3xl">
                Requirements that
                <br />
                cite their authority.
              </h1>

              <p
                className="mt-7 max-w-xl"
                style={{
                  fontSize: "1.125rem",
                  lineHeight: 1.5,
                  letterSpacing: "-0.012em",
                  color: "var(--text-secondary)",
                }}
              >
                Every requirement is traced to the clause that obliges it — and
                that citation is{" "}
                <em style={{ color: "var(--text)", fontStyle: "normal" }}>
                  checked, not trusted
                </em>
                . It must resolve to a real clause, its quotation must appear in
                that clause, and two independent models must agree the clause
                creates the obligation.
              </p>

              <div className="mt-10 flex flex-wrap gap-x-10 gap-y-6">
                {CLAIMS.map(([value, label], i) => (
                  <div
                    key={label}
                    className="rise"
                    style={{ animationDelay: `${0.4 + i * 0.09}s` }}
                  >
                    <div
                      style={{
                        fontSize: "1.625rem",
                        fontWeight: 600,
                        letterSpacing: "-0.03em",
                      }}
                    >
                      {value}
                    </div>
                    <div className="caption" style={{ maxWidth: 170 }}>
                      {label}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-12 flex flex-wrap items-center gap-4">
                <Link
                  href="/retrieval"
                  className="body"
                  style={{
                    background: "var(--accent)",
                    color: "var(--accent-ink)",
                    borderRadius: 10,
                    padding: "10px 18px",
                    fontWeight: 550,
                    fontSize: "0.875rem",
                    textDecoration: "none",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  Start with a question
                </Link>
                <Link
                  href="/corpus"
                  className="body"
                  style={{
                    color: "var(--text-secondary)",
                    textDecoration: "none",
                  }}
                >
                  or read the corpus first →
                </Link>
              </div>
            </div>
          </section>

          {/* Three sentences on how to use it. A first-time reader needs to
              know the order of operations before they need any of the detail,
              and putting the detail here instead is how landing pages become
              things nobody finishes. */}
          <section className="py-20">
            <h2 className="title m-0 max-w-2xl">
              Six modules, in the order the work happens.
            </h2>
            <p className="body mt-4 max-w-2xl" style={{ color: "var(--text-secondary)" }}>
              Read the regulation, ask what governs your case, turn the answer
              into testable requirements, find what nothing covers, choose how to
              build it, and see what breaks when the regulator amends the source.
              Each is a separate screen, and each states its own limits.
            </p>

            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              {MODULES.map((module, i) => (
                <motion.div
                  key={module.href}
                  className="rise"
                  style={{ animationDelay: `${i * 0.05}s` }}
                  whileHover={{ y: -3 }}
                  whileTap={{ scale: 0.99 }}
                  transition={{ type: "spring", stiffness: 420, damping: 30 }}
                >
                  <Link
                    href={module.href}
                    className="glass block h-full p-6"
                    style={{ textDecoration: "none", color: "inherit" }}
                  >
                    <div className="flex items-baseline gap-3">
                      <span
                        className="mono"
                        style={{ color: "var(--text-tertiary)", fontSize: "0.6875rem" }}
                      >
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="headline">{module.name}</span>
                    </div>
                    <p
                      className="body mt-2 mb-0"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {module.question}
                    </p>
                  </Link>
                </motion.div>
              ))}
            </div>
          </section>

          <footer className="mt-10 border-t pt-8 hairline">
            <p className="caption m-0 max-w-3xl">
              न्याय — the school of Indian logic concerned with what counts as
              admissible evidence for a claim. Figures on this site are measured
              on a 49-pair labelled set with a single annotator, and the
              thresholds are fitted on the same set. They are optimistic until a
              held-out set exists, and are reported that way everywhere they
              appear.
            </p>
            {health && (
              <p className="caption mt-3 m-0">
                Corpus: {health.corpus_clauses} clauses indexed.
              </p>
            )}
          </footer>
        </div>
      </main>
    </>
  );
}
