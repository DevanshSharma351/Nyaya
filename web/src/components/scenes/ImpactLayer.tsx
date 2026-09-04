"use client";

/** An amendment propagating out to the requirements that cited it. */

import { Rig, Stage } from "../three/stage";
import ImpactScene from "../three/ImpactScene";
import type { Impact } from "@/lib/api";

export default function ImpactLayer({ impact }: { impact: Impact | null }) {
  return (
    <Stage camera={{ position: [0, 5, 22], fov: 50 }}>
      <Rig />
      <ImpactScene impact={impact} />
    </Stage>
  );
}
