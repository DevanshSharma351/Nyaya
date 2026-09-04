"use client";

/** The control pack as a surface with holes where the gaps are. */

import { Rig, Stage } from "../three/stage";
import CoverageScene from "../three/CoverageScene";
import type { ControlCoverage } from "@/lib/api";

export default function CoverageLayer({
  controls,
}: {
  controls: ControlCoverage[] | null;
}) {
  return (
    <Stage camera={{ position: [0, 0, 15], fov: 46 }}>
      <Rig />
      <CoverageScene controls={controls} />
    </Stage>
  );
}
