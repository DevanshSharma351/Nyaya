"use client";

/**
 * How the system actually works, drawn.
 *
 * The honest shape of this project is not a swarm of agents conferring with
 * each other. It is a fixed graph with language models at four specific points
 * and non-model machinery checking every one of them, with a human gate after
 * each stage. Drawing it as a mesh of chatting agents would look more
 * impressive and would misrepresent it - and the difference matters, because
 * the reason to trust an output here is precisely that a model did not get the
 * last word on it.
 *
 * So the diagram has three lanes, and they are the argument:
 *
 *   proposes   - where a model generates something. Always fallible.
 *   verifies   - deterministic checks and retrieval that can contradict it.
 *   decides    - the human gate that has to pass before the stage advances.
 *
 * Read down a column and you get the answer to "why should I believe this?".
 *
 * Laid out with CSS grid rather than SVG so the text is real text: it reflows
 * on a narrow screen, it is selectable, and it is readable by a screen reader
 * in the order the pipeline actually runs.
 */

import { Fragment } from "react";
import Link from "next/link";
import { MODULES } from "./chrome/modules";

type Stage = {
  name: string;
  href: string;
  proposes: string;
  verifies: string[];
  gate: string;
};

const STAGES: Stage[] = [
  {
    name: "Extract",
    href: "/requirements",
    proposes: "A model rewrites stakeholder prose into EARS-form requirements",
    verifies: [
      "EARS conformance check",
      "ambiguity lexicon",
      "every quantity matched against the source",
    ],
    gate: "Baseline approved",
  },
  {
    name: "Map",
    href: "/retrieval",
    proposes: "A model cites the clause it believes creates each obligation",
    verifies: [
      "citation must resolve to a real clause",
      "quotation must appear in that clause",
      "entailment and reranker must agree",
    ],
    gate: "Interpretation approved",
  },
  {
    name: "Cover",
    href: "/coverage",
    proposes: "Requirements are matched against the control pack",
    verifies: [
      "every control cites its own authority",
      "applies-when separated from satisfied-when",
      "unclear matches routed to review, not decided",
    ],
    gate: "Gaps accepted",
  },
  {
    name: "Choose",
    href: "/lifecycle",
    proposes: "Factors are derived from what the extraction actually found",
    verifies: [
      "AHP weights, consistency ratio checked",
      "TOPSIS ranking, no model involved",
      "close calls declared rather than broken",
    ],
    gate: "Lifecycle approved",
  },
];

const LANES = [
  ["proposes", "A model generates. Fallible by construction."],
  ["verifies", "Deterministic checks that can contradict it."],
  ["decides", "A person, before the stage advances."],
] as const;

type LaneName = (typeof LANES)[number][0];

const LANES_TEMPLATE = "200px repeat(4, minmax(0, 1fr))";

/** The verifying lane carries the argument, so it is the only one given weight. */
function laneStyle(lane: LaneName) {
  return {
    background: lane === "verifies" ? "var(--bg-inset)" : "var(--surface)",
    borderColor: lane === "decides" ? "var(--hairline-strong)" : "var(--hairline)",
  };
}

function LaneContent({ lane, stage }: { lane: LaneName; stage: Stage }) {
  if (lane === "proposes") {
    return (
      <p className="caption m-0" style={{ color: "var(--text-secondary)" }}>
        {stage.proposes}
      </p>
    );
  }
  if (lane === "verifies") {
    return (
      <ul className="caption" style={{ margin: 0, paddingLeft: 16, lineHeight: 1.6 }}>
        {stage.verifies.map((check) => (
          <li key={check}>{check}</li>
        ))}
      </ul>
    );
  }
  return (
    <div className="caption" style={{ color: "var(--text)" }}>
      {stage.gate}
    </div>
  );
}

function Lane({ label, hint }: { label: string; hint: string }) {
  return (
    <div className="pt-1">
      <div className="mono" style={{ color: "var(--text)", fontWeight: 550 }}>
        {label}
      </div>
      <div className="caption mt-1" style={{ maxWidth: 190 }}>
        {hint}
      </div>
    </div>
  );
}

export default function Architecture() {
  return (
    <div>
      <div className="mb-8 max-w-2xl">
        <h2 className="title m-0">Four stages, and nothing a model says goes unchecked.</h2>
        <p className="body mt-4" style={{ color: "var(--text-secondary)" }}>
          Language models do three things here: rewrite prose into testable form,
          propose which clause creates an obligation, and put a result into
          sentences. Every one of those is then checked by something that is not a
          language model, and every stage ends at a person who can refuse it.
        </p>
      </div>

      {/*
        Two layouts, not one responsive grid.

        The first attempt used `auto-fit, minmax(180px, 1fr)` for the lane label
        plus four stages. With five items that wraps: the fourth stage dropped
        to a second row and its cards ended up under the lane label, reading as
        though "Choose" belonged to a different lane entirely. An explicit
        five-column template cannot do that, and the narrow case is a genuinely
        different arrangement rather than a squeezed version of the wide one.
      */}
      <div className="hidden lg:grid" style={{ gridTemplateColumns: LANES_TEMPLATE, gap: 20 }}>
        <div />
        {STAGES.map((stage) => (
          <Link
            key={stage.name}
            href={stage.href}
            className="headline pb-1"
            style={{ textDecoration: "none", color: "var(--text)" }}
          >
            {stage.name} →
          </Link>
        ))}

        {LANES.map(([lane, hint]) => (
          <Fragment key={lane}>
            <Lane label={lane} hint={hint} />
            {STAGES.map((stage) => (
              <div key={stage.name} className="glass p-4" style={laneStyle(lane)}>
                <LaneContent lane={lane} stage={stage} />
              </div>
            ))}
          </Fragment>
        ))}
      </div>

      {/* Narrow: one card per stage, each carrying all three lanes. Reading a
          stage top to bottom is the same argument as reading a column. */}
      <div className="flex flex-col gap-4 lg:hidden">
        {STAGES.map((stage) => (
          <div key={stage.name} className="glass p-5">
            <Link
              href={stage.href}
              className="headline"
              style={{ textDecoration: "none", color: "var(--text)" }}
            >
              {stage.name} →
            </Link>
            {LANES.map(([lane]) => (
              <div key={lane} className="mt-3">
                <div className="mono mb-1" style={{ color: "var(--text-tertiary)" }}>
                  {lane}
                </div>
                <LaneContent lane={lane} stage={stage} />
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="mt-6 flex flex-wrap gap-x-8 gap-y-3">
        <p className="caption m-0" style={{ maxWidth: 340 }}>
          <span style={{ color: "var(--text)" }}>Durable gates.</span> The graph
          suspends at each one and resumes from a checkpoint. A refusal stops the
          run — a gate whose rejection changes nothing is not a gate.
        </p>
        <p className="caption m-0" style={{ maxWidth: 340 }}>
          <span style={{ color: "var(--text)" }}>Hash-chained ledger.</span> Every
          decision, approval and model attribution is appended and linked to the
          previous entry, so an altered record does not verify.
        </p>
        <p className="caption m-0" style={{ maxWidth: 340 }}>
          <span style={{ color: "var(--text)" }}>An LLM judge exists.</span> It was
          measured against the entailment check, lost, and was demoted to advisory.
          Its opinions are labelled as unverified and decide nothing.
        </p>
      </div>

      <p className="caption mt-8" style={{ color: "var(--text-tertiary)" }}>
        Each stage is a module: {MODULES.map((m) => m.name).join(" · ")}
      </p>
    </div>
  );
}
