"use client";

/** The shared ambient field, mounted full-bleed behind a module's content. */

import { Rig, Stage } from "../three/stage";
import AmbientField from "../three/AmbientField";

export default function AmbientLayer() {
  return (
    <Stage camera={{ position: [0, 2.5, 26], fov: 52 }} className="scene-layer">
      <Rig />
      <AmbientField />
    </Stage>
  );
}
