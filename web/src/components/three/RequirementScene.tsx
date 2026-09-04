/* eslint-disable react-hooks/immutability --
 * Positions for ~700 particles are written into a typed array in place every
 * frame. That is the only way to animate a point cloud; the alternative is
 * reallocating a Float32Array sixty times a second.
 */
"use client";

/**
 * Prose becoming structure, driven by scroll.
 *
 * The previous scene here drew each requirement as a chain of blocks with
 * orbiting satellites. It encoded real properties - EARS arity, acceptance
 * criteria, defects - but at panel size it was a cluster of small shapes that
 * had to be decoded against a caption, and before extraction ran it was an
 * invisible cloud of grey dots.
 *
 * This shows the transformation the module performs instead of the output of
 * it. The particles begin scattered, which is what stakeholder language
 * actually is, and scroll pulls them into one column per extracted
 * requirement. Nothing about the assembly is decorative: the number of columns
 * is the number of requirements, a column's height is its acceptance criteria,
 * and the red particles are detected defects. Before extraction runs there is
 * nothing to assemble into, so the cloud stays scattered and drifting - which
 * is a truthful empty state rather than a blank one.
 */

import { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { ExtractedRequirement } from "@/lib/api";
import { useStageMotion } from "./stage";

const COUNT = 700;

const RISK_COLOR: Record<string, THREE.Color> = {
  low: new THREE.Color("#c4c4c8"),
  medium: new THREE.Color("#a1a1aa"),
  high: new THREE.Color("#52525b"),
  critical: new THREE.Color("#18181b"),
};
const DEFECT = new THREE.Color("#b42318");
const LOOSE = new THREE.Color("#c4c4c8");

/**
 * A deterministic stand-in for `Math.random`.
 *
 * The scatter has to be identical on every load, for the same reason the corpus
 * graph pins its documents: a picture that rearranges itself each visit is one
 * you cannot remember, and it would also make every screenshot and test run
 * subtly different.
 */
function noise(index: number, salt: number): number {
  const x = Math.sin(index * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x) - 0.5;
}

/** A round, soft sprite. `pointsMaterial` draws squares, which read as dust. */
function makeDotTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d")!;
  const gradient = context.createRadialGradient(
    size / 2, size / 2, 0, size / 2, size / 2, size / 2,
  );
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.45, "rgba(255,255,255,0.85)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

export default function RequirementScene({
  requirements,
}: {
  requirements: ExtractedRequirement[] | null;
}) {
  const pointsRef = useRef<THREE.Points>(null);
  const motion = useStageMotion();
  const { camera } = useThree();
  const dot = useMemo(() => makeDotTexture(), []);

  const scattered = useMemo(() => {
    const positions = new Float32Array(COUNT * 3);
    for (let i = 0; i < COUNT; i++) {
      positions[i * 3] = noise(i, 1) * 20;
      positions[i * 3 + 1] = noise(i, 2) * 7;
      positions[i * 3 + 2] = noise(i, 3) * 8;
    }
    return positions;
  }, []);

  // The ordered arrangement, rebuilt whenever the extraction result changes.
  // Recomputing it per frame would make the columns shimmer; computing it once
  // means the assembly converges on a fixed target.
  const { ordered, colours, hasStructure } = useMemo(() => {
    const ordered = new Float32Array(COUNT * 3);
    const colours = new Float32Array(COUNT * 3);
    const list = requirements ?? [];

    if (list.length === 0) {
      for (let i = 0; i < COUNT; i++) {
        ordered.set([scattered[i * 3], scattered[i * 3 + 1], scattered[i * 3 + 2]], i * 3);
        colours.set([LOOSE.r, LOOSE.g, LOOSE.b], i * 3);
      }
      return { ordered, colours, hasStructure: false };
    }

    const columns = Math.min(list.length, 8);
    const perColumn = Math.floor(COUNT / columns);

    for (let i = 0; i < COUNT; i++) {
      const column = Math.min(Math.floor(i / perColumn), columns - 1);
      const requirement = list[column];
      const withinColumn = i - column * perColumn;

      // A column is as tall as the requirement is testable: one band per
      // acceptance criterion, plus the statement itself. A requirement with no
      // criteria is a short column, which is exactly what it is in review.
      const bands = Math.max(requirement.acceptance_criteria.length + 1, 1);
      const height = 0.9 + bands * 0.55;
      const x = (column - (columns - 1) / 2) * 2.4;
      const t = (withinColumn % perColumn) / perColumn;

      // A slight helix rather than a straight line, so the columns read as
      // volumes and not as flat bars seen edge-on.
      const angle = t * Math.PI * 4 + column;
      const radius = 0.42 + noise(i, 5) * 0.22;
      ordered[i * 3] = x + Math.cos(angle) * radius;
      ordered[i * 3 + 1] = -height / 2 + t * height;
      ordered[i * 3 + 2] = Math.sin(angle) * radius;

      // Defect share. A requirement with defects has that fraction of its
      // column coloured, so the amount of red is proportional to how much is
      // wrong with it rather than being a single marker.
      const defectShare = Math.min(requirement.defects.length * 0.16, 0.6);
      const colour =
        t > 1 - defectShare
          ? DEFECT
          : (RISK_COLOR[requirement.risk_level] ?? RISK_COLOR.medium);
      colours.set([colour.r, colour.g, colour.b], i * 3);
    }
    return { ordered, colours, hasStructure: true };
  }, [requirements, scattered]);

  const geometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(scattered.slice(), 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(COUNT * 3), 3));
    return geometry;
  }, [scattered]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const points = pointsRef.current;
    if (!points) return;

    // Assembly completes by 70% of the page, so the last section is read
    // against a settled scene rather than a still-moving one. With nothing
    // extracted there is no structure to move towards, so the cloud stays put.
    const p = hasStructure ? Math.min(motion.scroll.current / 0.7, 1) : 0;
    const eased = p * p * (3 - 2 * p);
    const time = motion.age.current;

    const positionAttr = points.geometry.attributes.position as THREE.BufferAttribute;
    const colourAttr = points.geometry.attributes.color as THREE.BufferAttribute;
    const positions = positionAttr.array as Float32Array;
    const colourArray = colourAttr.array as Float32Array;

    for (let i = 0; i < COUNT; i++) {
      const k = i * 3;
      // Sway is largest while scattered and almost gone once ordered.
      // Structure that still wobbles does not read as settled.
      const sway = (1 - eased) * 0.55;
      positions[k] =
        scattered[k] + (ordered[k] - scattered[k]) * eased + Math.sin(time * 0.5 + i) * sway;
      positions[k + 1] =
        scattered[k + 1] +
        (ordered[k + 1] - scattered[k + 1]) * eased +
        Math.cos(time * 0.42 + i * 1.7) * sway;
      positions[k + 2] =
        scattered[k + 2] +
        (ordered[k + 2] - scattered[k + 2]) * eased +
        Math.sin(time * 0.37 + i * 0.9) * sway;

      // Colour arrives with the structure: unstructured text has no risk level
      // and no defects, so claiming one before extraction would be a lie.
      colourArray[k] = LOOSE.r + (colours[k] - LOOSE.r) * eased;
      colourArray[k + 1] = LOOSE.g + (colours[k + 1] - LOOSE.g) * eased;
      colourArray[k + 2] = LOOSE.b + (colours[k + 2] - LOOSE.b) * eased;
    }
    positionAttr.needsUpdate = true;
    colourAttr.needsUpdate = true;

    points.rotation.y += dt * 0.05 * (1 - eased * 0.7);

    const [px, py] = motion.pointer.current;
    const lerp = 1 - Math.exp(-3 * dt);
    camera.position.x += (px * 2 - camera.position.x) * lerp;
    camera.position.y += (py * 1.2 - camera.position.y) * lerp;
    camera.position.z += (16 - eased * 4 - camera.position.z) * lerp;
    camera.lookAt(0, 0, 0);
  });

  return (
    <points ref={pointsRef} geometry={geometry}>
      <pointsMaterial
        map={dot}
        alphaMap={dot}
        size={0.2}
        vertexColors
        transparent
        opacity={0.92}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}
