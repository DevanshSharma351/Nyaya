/* eslint-disable react-hooks/immutability --
 * Positions for ~700 particles are written into a typed array in place every
 * frame; see the note in stage.tsx.
 */
"use client";

/**
 * The ambient dot field, shared by every module page.
 *
 * The same lattice the landing page assembles, at rest: three stacked tiers of
 * particles with trace links between them, drifting slowly and parallaxing with
 * scroll. It carries the same meaning wherever it appears - source text, the
 * requirement drawn from it, the clause that obliges it - so a reader who
 * watched it assemble on the landing page sees the finished thing behind every
 * module.
 *
 * Everything about it is set so it can never compete with the content in front
 * of it, because a full-bleed field behind a centred column of dark text on a
 * white ground has no way of avoiding overlap:
 *
 *  - It sits at a fraction of the landing page's opacity, and no particle is
 *    ever darker than the page's faintest border. A dot at body-text weight
 *    inside a paragraph reads as a full stop in the wrong place.
 *  - The links are fainter still. A dot behind a word is a speck; a line is a
 *    strike-through, and these run for hundreds of pixels.
 *  - It is offset right and its density falls off towards the left, where the
 *    text column is.
 *
 * It is decoration, and it is labelled as such: `aria-hidden`, no data, nothing
 * to read. That is the one thing in this interface allowed to be purely
 * atmospheric, and it earns that only by staying out of the way.
 */

import { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { useStageMotion } from "./stage";

const COUNT = 720;

const TIERS = [
  { y: -5.2, radius: 9.5 },
  { y: 0, radius: 7.0 },
  { y: 5.2, radius: 4.8 },
];

const PARTICLE = new THREE.Color("#c3c3ca");
const LINK = "#d8d8dd";
const OFFSET_X = 7;

/** Deterministic, so the field is identical on every page and every reload. */
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

export default function AmbientField() {
  const pointsRef = useRef<THREE.Points>(null);
  const linesRef = useRef<THREE.LineSegments>(null);
  const motion = useStageMotion();
  const { camera } = useThree();
  const dot = useMemo(() => makeDotTexture(), []);

  const { home, geometry, chain, linkGeometry } = useMemo(() => {
    const home = new Float32Array(COUNT * 3);

    for (let i = 0; i < COUNT; i++) {
      const tier = TIERS[i % TIERS.length];
      // The angle comes from the chain, not the particle, so each trace of
      // three is a near-vertical strand rather than a chord across the whole
      // structure. Taking it from the particle index puts consecutive members
      // 137 degrees apart and turns the lattice into a web.
      const strand = Math.floor(i / TIERS.length);
      const angle = strand * Math.PI * (3 - Math.sqrt(5));
      const jitter = noise(i, 4);
      const radius = tier.radius + jitter * 1.6;
      home[i * 3] = Math.cos(angle) * radius;
      home[i * 3 + 1] = tier.y + jitter * 1.1;
      home[i * 3 + 2] = Math.sin(angle) * radius;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(home.slice(), 3));

    // Every fourth strand is linked. Denser than that and the lines start to
    // read as a texture in their own right.
    const chain: number[] = [];
    for (let i = 0; i + 2 < COUNT; i += TIERS.length * 4) {
      chain.push(i, i + 1, i + 1, i + 2);
    }
    const linkGeometry = new THREE.BufferGeometry();
    linkGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(chain.length * 3), 3),
    );

    return { home, geometry, chain, linkGeometry };
  }, []);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const points = pointsRef.current;
    if (!points) return;

    const time = motion.age.current;
    const attribute = points.geometry.attributes.position as THREE.BufferAttribute;
    const positions = attribute.array as Float32Array;

    for (let i = 0; i < COUNT; i++) {
      const k = i * 3;
      // A slow, small sway. Large enough that the field is alive, small enough
      // that nothing appears to be happening if you are trying to read.
      positions[k] = home[k] + Math.sin(time * 0.28 + i) * 0.22;
      positions[k + 1] = home[k + 1] + Math.cos(time * 0.23 + i * 1.7) * 0.22;
      positions[k + 2] = home[k + 2] + Math.sin(time * 0.19 + i * 0.9) * 0.22;
    }
    attribute.needsUpdate = true;

    if (linesRef.current) {
      const linkPositions = linesRef.current.geometry.attributes.position
        .array as Float32Array;
      chain.forEach((particle, i) => {
        linkPositions[i * 3] = positions[particle * 3];
        linkPositions[i * 3 + 1] = positions[particle * 3 + 1];
        linkPositions[i * 3 + 2] = positions[particle * 3 + 2];
      });
      linesRef.current.geometry.attributes.position.needsUpdate = true;
      linesRef.current.rotation.y = points.rotation.y;
    }

    points.rotation.y += dt * 0.035;

    // Scroll parallaxes the camera through the field rather than moving the
    // field itself, so the page reads as travelling past something stationary.
    //
    // The camera stays near the origin and the *group* carries the offset.
    // Moving the camera right instead points it away from an origin-centred
    // field, which puts the whole thing on the left of the frame - directly
    // behind the text column, which is the one place it must not be.
    const p = motion.scroll.current;
    const [px, py] = motion.pointer.current;
    const k = 1 - Math.exp(-2.5 * dt);
    camera.position.x += (px * 1.6 - camera.position.x) * k;
    camera.position.y += (2.5 - p * 7 + py * 1.1 - camera.position.y) * k;
    camera.position.z += (26 - p * 5 - camera.position.z) * k;
    camera.lookAt(0, -p * 2, 0);
  });

  return (
    <group position={[OFFSET_X, 0, 0]}>
      <points ref={pointsRef} geometry={geometry}>
        <pointsMaterial
          map={dot}
          alphaMap={dot}
          color={PARTICLE}
          size={0.19}
          transparent
          opacity={0.4}
          sizeAttenuation
          depthWrite={false}
        />
      </points>
      <lineSegments ref={linesRef} geometry={linkGeometry}>
        <lineBasicMaterial color={LINK} transparent opacity={0.3} depthWrite={false} />
      </lineSegments>
    </group>
  );
}
