"use client";

/** The corpus field and the ranked shortlist standing out of it. */

import { Rig, Stage } from "../three/stage";
import RetrievalScene from "../three/RetrievalScene";
import type { Clause } from "@/lib/api";

export default function RetrievalLayer({
  clauses,
  busy,
  corpusSize,
}: {
  clauses: Clause[] | null;
  busy: boolean;
  corpusSize: number;
}) {
  return (
    <Stage camera={{ position: [0, 6, 22], fov: 48 }}>
      <Rig />
      <RetrievalScene clauses={clauses} busy={busy} corpusSize={corpusSize} />
    </Stage>
  );
}
