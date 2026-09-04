"use client";

/** The TOPSIS ideal/anti-ideal axis with the candidates ranged along it. */

import { Rig, Stage } from "../three/stage";
import LifecycleScene from "../three/LifecycleScene";
import type { SDLCRank } from "@/lib/api";

export default function LifecycleLayer({ ranked }: { ranked: SDLCRank[] | null }) {
  return (
    <Stage camera={{ position: [0, 0, 16], fov: 48 }}>
      <Rig />
      <LifecycleScene ranked={ranked} />
    </Stage>
  );
}
