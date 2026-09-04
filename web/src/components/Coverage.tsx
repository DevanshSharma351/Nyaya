"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type Coverage as CoverageType } from "@/lib/api";
import { Badge, Empty, Failure, Panel, Ring, SectionHeading } from "./ui";

const SEED = [
  "The system shall screen the customer against the designated-persons list before activation.",
  "The system shall retain customer identification records for five years from cessation.",
  "The system shall verify the customer identity using officially valid documents.",
  "The system shall encrypt customer information transmitted over public networks.",
].join("\n");

export default function Coverage() {
  const [text, setText] = useState(SEED);
  const [report, setReport] = useState<CoverageType | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(value: string) {
    try {
      const reports = await api.coverage(value);
      setReport(reports[0] ?? null);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
      setReport(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function seed() {
      try {
        const reports = await api.coverage(SEED);
        if (!cancelled) setReport(reports[0] ?? null);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }
    seed();
    return () => {
      cancelled = true;
    };
  }, []);

  const gaps = report?.controls.filter((c) => c.is_gap) ?? [];
  const covered = report?.controls.filter((c) => !c.is_gap) ?? [];

  return (
    <Panel className="p-8 lg:p-10" delay={0.05}>
      <SectionHeading
        eyebrow="Compliance coverage"
        title="Which mandatory controls nothing covers"
        lede="A gap is the actionable output; a list of satisfied controls is only reassurance. Every control here cites the clause that establishes it — one without a citation is rejected before the pack loads."
      />

      <div className="grid gap-8 lg:grid-cols-[auto_1fr]">
        <div className="flex flex-col items-center gap-4">
          <Ring
            value={report?.coverage_ratio ?? 0}
            tone={
              (report?.coverage_ratio ?? 0) > 0.7
                ? "var(--confirmed)"
                : (report?.coverage_ratio ?? 0) > 0.4
                  ? "var(--review)"
                  : "var(--gap)"
            }
            label="covered"
            size={124}
          />
          {report && (
            <div className="text-center">
              <div className="caption">{report.pack}</div>
              <div className="mono mt-1" style={{ color: "var(--gap)" }}>
                {report.blocking_gaps.length} blocking
              </div>
            </div>
          )}
        </div>

        <div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onBlur={() => run(text)}
            rows={4}
            className="body mb-5 w-full"
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

          {error && <Failure message={error} />}
          {!error && !report && <Empty>Assessing…</Empty>}

          {report && (
            <div className="grid gap-2 sm:grid-cols-2">
              {[...gaps, ...covered].map((control, i) => (
                <motion.div
                  key={control.control_id}
                  initial={{ opacity: 0, y: 10 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: Math.min(i * 0.02, 0.4) }}
                  className="glass p-3"
                  style={{
                    borderLeft: `2px solid ${
                      control.is_gap
                        ? control.severity === "blocker"
                          ? "var(--gap)"
                          : "var(--review)"
                        : "var(--confirmed)"
                    }`,
                  }}
                >
                  <div className="mono mb-1" style={{ color: "var(--text)" }}>
                    {control.control_id}
                  </div>
                  <div className="caption" style={{ lineHeight: 1.4 }}>
                    {control.title}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <Badge
                      tone={
                        control.is_gap
                          ? control.severity === "blocker"
                            ? "var(--gap)"
                            : "var(--review)"
                          : "var(--confirmed)"
                      }
                    >
                      {control.is_gap ? `gap · ${control.severity}` : "covered"}
                    </Badge>
                    {control.citations.slice(0, 1).map((c) => (
                      <Badge key={c} tone="var(--clause)">
                        {c}
                      </Badge>
                    ))}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
