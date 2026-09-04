"use client";

import { motion } from "framer-motion";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api, type Graph, type Health } from "@/lib/api";
import { Badge } from "./ui";

// The graph pulls in three.js; loading it lazily keeps it off the critical path
// so the page is readable before the scene is ready.
const KnowledgeGraph = dynamic(() => import("./KnowledgeGraph"), {
  ssr: false,
  loading: () => <div className="h-full w-full" />,
});

export default function Hero() {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [g, h] = await Promise.allSettled([
        api.knowledgeGraph(),
        api.health(),
      ]);
      if (cancelled) return;
      setGraph(g.status === "fulfilled" ? g.value : null);
      setHealth(h.status === "fulfilled" ? h.value : null);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="relative min-h-[92vh] overflow-hidden">
      {/* Offset right, so the scene occupies the half of the frame the scrim
          leaves clear rather than competing with the headline. */}
      <div className="absolute inset-y-0 right-0 z-0 w-full lg:w-[62%]">
        {graph && <KnowledgeGraph graph={graph} />}
      </div>

      {/* Scrim: the type must stay readable over a moving scene, and lowering
          the scene's contrast is cheaper than fighting it with text shadows.
          Horizontal rather than radial - a radial scrim centred on the copy
          also darkens the middle of the frame, which is where the scene is. */}
      <div
        className="pointer-events-none absolute inset-0 z-10"
        style={{
          background:
            "linear-gradient(100deg, rgba(10,10,15,0.96) 0%, rgba(10,10,15,0.9) 34%, rgba(10,10,15,0.5) 56%, transparent 78%)",
        }}
      />

      <div className="relative z-20 mx-auto flex min-h-[92vh] max-w-7xl flex-col justify-center px-6 py-24 lg:px-10">
        <motion.div
          initial={{ opacity: 0, y: 26 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="max-w-2xl"
        >
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <Badge tone="var(--accent)">न्याय · NYAYA</Badge>
            {health && (
              <Badge tone={health.status === "ok" ? "var(--confirmed)" : "var(--review)"}>
                {health.status === "ok" ? "all systems reachable" : "degraded"}
              </Badge>
            )}
            {health && <Badge>{health.corpus_clauses} clauses indexed</Badge>}
          </div>

          <h1 className="display m-0">
            Requirements that
            <br />
            <span
              style={{
                background:
                  "linear-gradient(120deg, #0a84ff 0%, #bf5af2 52%, #30d158 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              cite their authority.
            </span>
          </h1>

          <p
            className="mt-7 max-w-xl"
            style={{
              fontSize: "1.1875rem",
              lineHeight: 1.5,
              letterSpacing: "-0.012em",
              color: "var(--text-secondary)",
            }}
          >
            Agentic requirements engineering for regulated financial software.
            Every requirement is traced to the clause that obliges it — and that
            citation is <em style={{ color: "var(--text)", fontStyle: "normal" }}>checked,
            not trusted</em>: it must resolve to a real clause, its quotation
            must appear in that clause, and two independent models must agree it
            creates the obligation.
          </p>

          <div className="mt-10 flex flex-wrap gap-8">
            {[
              ["1.000", "precision on the auto-accept tier", "var(--confirmed)"],
              ["0", "false confirmations measured", "var(--confirmed)"],
              ["0.143", "expected calibration error", "var(--accent)"],
            ].map(([value, label, tone], i) => (
              <div
                key={label}
                className="rise"
                style={{ animationDelay: `${0.35 + i * 0.09}s` }}
              >
                <div
                  style={{
                    color: tone,
                    fontSize: "1.75rem",
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
        </motion.div>
      </div>

      <motion.div
        className="absolute bottom-8 left-1/2 z-20 -translate-x-1/2"
        animate={{ y: [0, 9, 0] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      >
        <div className="caption">scroll</div>
      </motion.div>
    </section>
  );
}
