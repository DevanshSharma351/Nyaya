/* eslint-disable react-hooks/immutability --
 * Positions for ~1100 particles are written into a typed array in place every
 * frame. That is the only way to animate a point cloud; the alternative is
 * reallocating a Float32Array sixty times a second.
 */
"use client";

/**
 * Prose becoming structure.
 *
 * The particles start as an unordered cloud - stakeholder language, which is
 * what actually arrives - and scroll pulls them onto three stacked rings:
 * source text, the requirement derived from it, the clause that obliges it.
 * Filaments appear between the layers as they lock in.
 *
 * The transition is driven by scroll rather than by time, so the reader is
 * doing the work of the pipeline rather than watching a loop. Nothing here is
 * decorative in the sense of arbitrary: the three tiers are the three tiers the
 * system actually maintains, and the filaments are the trace links.
 */

import { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { useStageMotion } from "./stage";

const COUNT = 520;

/**
 * A deterministic stand-in for `Math.random`.
 *
 * The scatter has to be the same on every load. This is the same argument the
 * corpus graph makes for pinning its documents: a picture that rearranges
 * itself each time you visit is one you cannot remember, and here it would also
 * mean the hero was subtly different in every screenshot and every test run.
 * A hash of the index gives an even, uncorrelated spread that is nevertheless
 * fixed.
 */
function scatterAt(index: number, salt: number): number {
  const x = Math.sin(index * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x) - 0.5;
}
/*
 * The three tiers are separated by weight, not hue: source text is the
 * faintest, the clause that obliges it is the darkest. On a white ground that
 * ordering is legible at a glance and needs no legend.
 */
const TIERS = [
  { y: -4.6, radius: 8.4, color: new THREE.Color("#b4b4bb") }, // stakeholder text
  { y: 0, radius: 6.2, color: new THREE.Color("#71717a") }, // requirement
  { y: 4.6, radius: 4.2, color: new THREE.Color("#52525b") }, // clause
];

/*
 * The cloud is pushed to the right of the frame.
 *
 * On a dark ground the earlier version could sit behind the headline under a
 * scrim. On white there is no scrim to apply - darkening the page behind text
 * that is already dark makes both worse - so the scene and the copy are given
 * separate halves of the frame instead. The particles are also darker than the
 * first attempt at this palette, where grey-300 on white was so close to the
 * ground that the scene rendered correctly and looked like nothing at all.
 */
const OFFSET_X = 9;

/**
 * A round, soft sprite for the particles.
 *
 * `pointsMaterial` draws squares by default, and 500 grey squares on a white
 * page read as dust on a screen rather than as anything designed. A radial
 * alpha ramp costs one 64px canvas and is the whole difference between the two.
 */
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

export default function HeroScene() {
  const pointsRef = useRef<THREE.Points>(null);
  const dot = useMemo(() => makeDotTexture(), []);
  const linesRef = useRef<THREE.LineSegments>(null);
  const motion = useStageMotion();
  const { camera } = useThree();

  // Both endpoints of every particle's journey, computed once. Recomputing
  // them per frame would make the cloud reshuffle continuously, which reads as
  // noise rather than as convergence.
  const { scattered, ordered, geometry, filaments, filamentGeometry } =
    useMemo(() => {
      const scattered = new Float32Array(COUNT * 3);
      const ordered = new Float32Array(COUNT * 3);
      const colors = new Float32Array(COUNT * 3);

      for (let i = 0; i < COUNT; i++) {
        // Scattered: a slab, wider than tall, so the starting state reads as a
        // body of text rather than a sphere of dots.
        scattered[i * 3] = scatterAt(i, 1) * 15;
        scattered[i * 3 + 1] = scatterAt(i, 2) * 15;
        scattered[i * 3 + 2] = scatterAt(i, 3) * 22;

        const tier = TIERS[i % TIERS.length];
        // Golden-angle placement around the ring keeps the spacing even
        // without the clumping that uniform random angles produce.
        const angle = i * Math.PI * (3 - Math.sqrt(5));
        const jitter = (i % 17) / 17 - 0.5;
        ordered[i * 3] = Math.cos(angle) * (tier.radius + jitter * 1.1);
        ordered[i * 3 + 1] = tier.y + jitter * 0.5;
        ordered[i * 3 + 2] = Math.sin(angle) * (tier.radius + jitter * 1.1);

        colors[i * 3] = tier.color.r;
        colors[i * 3 + 1] = tier.color.g;
        colors[i * 3 + 2] = tier.color.b;
      }

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(scattered.slice(), 3));
      geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

      // Trace links: text particle -> requirement particle -> clause particle,
      // one chain for every third particle so the lattice stays readable.
      const chains: number[] = [];
      for (let i = 0; i + 2 < COUNT; i += 9) {
        chains.push(i, i + 1, i + 1, i + 2);
      }
      const filamentGeometry = new THREE.BufferGeometry();
      filamentGeometry.setAttribute(
        "position",
        new THREE.BufferAttribute(new Float32Array(chains.length * 3), 3),
      );

      return { scattered, ordered, geometry, filaments: chains, filamentGeometry };
    }, []);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const points = pointsRef.current;
    if (!points) return;

    // Convergence is complete by 70% of the page, so the last section is read
    // against a settled scene rather than a still-moving one.
    const p = Math.min(motion.scroll.current / 0.7, 1);
    const eased = p * p * (3 - 2 * p);
    const t = motion.age.current;

    const attribute = points.geometry.attributes.position as THREE.BufferAttribute;
    const array = attribute.array as Float32Array;

    for (let i = 0; i < COUNT; i++) {
      const k = i * 3;
      // A small per-particle sway, largest while scattered and almost gone
      // once ordered. Structure that still wobbles does not read as settled.
      const sway = (1 - eased) * 0.9;
      array[k] =
        scattered[k] + (ordered[k] - scattered[k]) * eased + Math.sin(t * 0.5 + i) * sway;
      array[k + 1] =
        scattered[k + 1] +
        (ordered[k + 1] - scattered[k + 1]) * eased +
        Math.cos(t * 0.42 + i * 1.7) * sway;
      array[k + 2] =
        scattered[k + 2] +
        (ordered[k + 2] - scattered[k + 2]) * eased +
        Math.sin(t * 0.37 + i * 0.9) * sway;
    }
    attribute.needsUpdate = true;

    if (linesRef.current) {
      const linePositions = linesRef.current.geometry.attributes
        .position.array as Float32Array;
      filaments.forEach((particle, i) => {
        linePositions[i * 3] = array[particle * 3];
        linePositions[i * 3 + 1] = array[particle * 3 + 1];
        linePositions[i * 3 + 2] = array[particle * 3 + 2];
      });
      linesRef.current.geometry.attributes.position.needsUpdate = true;
      // Links only become visible once the tiers exist to be linked.
      const material = linesRef.current.material as THREE.LineBasicMaterial;
      material.opacity = Math.max(0, eased - 0.45) * 1.4;
    }

    points.rotation.y += dt * 0.06;
    if (linesRef.current) linesRef.current.rotation.y = points.rotation.y;

    const [px, py] = motion.pointer.current;
    // The camera stays near the origin and the cloud sits to its right. Moving
    // the camera to the offset as well would cancel it out and re-centre the
    // scene behind the headline, which is the thing the offset exists to
    // prevent.
    const k = 1 - Math.exp(-3 * dt);
    camera.position.x += (px * 2.6 - camera.position.x) * k;
    camera.position.y += (py * 1.8 + 1 - camera.position.y) * k;
    camera.position.z += (23 - eased * 5 - camera.position.z) * k;
    camera.lookAt(0, 0, 0);
  });

  return (
    <group position={[OFFSET_X, 0, 0]}>
      <points ref={pointsRef} geometry={geometry}>
        {/* Normal blending, not additive. Additive blending sums towards white,
            which on a white page makes every particle invisible exactly where
            they overlap most - the opposite of the intended effect, and a
            mistake that looks correct on a dark ground. */}
        <pointsMaterial
          map={dot}
          alphaMap={dot}
          size={0.28}
          vertexColors
          transparent
          opacity={0.9}
          sizeAttenuation
          depthWrite={false}
        />
      </points>
      <lineSegments ref={linesRef} geometry={filamentGeometry}>
        <lineBasicMaterial color="#a1a1aa" transparent opacity={0} depthWrite={false} />
      </lineSegments>
    </group>
  );
}
