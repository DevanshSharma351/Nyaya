"use client";

/** The corpus graph, with the camera handed to the reader. */

import { Rig, Stage } from "../three/stage";
import CorpusScene from "../three/CorpusScene";
import type { Graph, GraphNode } from "@/lib/api";

export default function CorpusLayer({
  graph,
  onHover,
  focus,
}: {
  graph: Graph;
  onHover?: (node: GraphNode | null) => void;
  focus?: string | null;
}) {
  return (
    <Stage camera={{ position: [0, 2, 17], fov: 52 }}>
      <Rig />
      <CorpusScene graph={graph} onHover={onHover} focus={focus} interactive />
    </Stage>
  );
}
