"use client";

/**
 * The landing scene layer.
 *
 * Each module's scene lives in its own file so a page can dynamically import
 * only its own. three.js and a scene together come to roughly 600 KB, and
 * bundling all six behind one entry point would make every module pay for the
 * other five.
 */

import { Rig, Stage } from "../three/stage";
import HeroScene from "../three/HeroScene";

export default function HeroLayer() {
  return (
    <Stage camera={{ position: [0, 1, 23], fov: 50 }} className="scene-layer">
      <Rig />
      <HeroScene />
    </Stage>
  );
}
