"use client";

/** Extracted requirements as EARS-shaped chains. */

import { Rig, Stage } from "../three/stage";
import RequirementScene from "../three/RequirementScene";
import type { ExtractedRequirement } from "@/lib/api";

export default function RequirementLayer({
  requirements,
}: {
  requirements: ExtractedRequirement[] | null;
}) {
  return (
    <Stage camera={{ position: [0, 0, 16], fov: 50 }}>
      <Rig />
      <RequirementScene requirements={requirements} />
    </Stage>
  );
}
