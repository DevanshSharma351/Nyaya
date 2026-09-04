/* eslint-disable react-hooks/immutability --
 * Per-frame writes to Three.js transforms and to a point cloud's position
 * buffer. Animation code has to mutate; routing it through React state would
 * re-render the tree every frame.
 */
"use client";

/**
 * Retrieval, drawn as what it is: a shortlist lifted out of a corpus.
 *
 * The dim field is the corpus - one point per indexed clause, so the size of
 * the haystack is not a metaphor but the actual number the API reports. The
 * bars that rise out of it are the results, ordered left to right by rank, with
 * height set by the cross-encoder's relevance score.
 *
 * That last detail is the reason this is worth drawing at all. Rank and score
 * disagree more often than people expect: a shortlist can be correctly ordered
 * and still have nothing in it worth reading, and a flat row of six bars says
 * so at a glance in a way a numbered list does not.
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { Clause } from "@/lib/api";
import { useStageMotion } from "./stage";

/*
 * Relevance is drawn as darkness rather than as a hue.
 *
 * Three colours for three relevance bands implies three kinds of result, and
 * there is only one kind: a result with a score. A continuous ramp from pale to
 * near-black carries the same information without inventing categories at
 * arbitrary thresholds, and it stays honest about the values in between.
 */
const STRONG = new THREE.Color("#18181b");
const WEAK = new THREE.Color("#d4d4d8");

function toneFor(relevance: number | null): THREE.Color {
  const value = Math.max(0, Math.min(relevance ?? 0, 1));
  return WEAK.clone().lerp(STRONG, value);
}

/** The corpus: one point per indexed clause, drifting on a shallow torus. */
function CorpusField({ size, searching }: { size: number; searching: boolean }) {
  const ref = useRef<THREE.Points>(null);
  const motion = useStageMotion();

  const geometry = useMemo(() => {
    const count = Math.max(size, 24);
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const angle = i * Math.PI * (3 - Math.sqrt(5));
      const radius = 6 + ((i * 7919) % 100) / 100 * 9;
      positions[i * 3] = Math.cos(angle) * radius;
      positions[i * 3 + 1] = -3.2 + (((i * 104729) % 100) / 100 - 0.5) * 1.4;
      positions[i * 3 + 2] = Math.sin(angle) * radius;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geometry;
  }, [size]);

  useFrame((_, delta) => {
    if (!ref.current) return;
    const dt = Math.min(delta, 0.05);
    ref.current.rotation.y += dt * (searching ? 0.55 : 0.05);
    const material = ref.current.material as THREE.PointsMaterial;
    // Brightening while a query runs is the only place in this interface where
    // motion reports state, and it is deliberate: a local model takes long
    // enough that silence reads as breakage.
    const target = searching ? 0.85 : 0.3;
    material.opacity += (target - material.opacity) * (1 - Math.exp(-5 * dt));
    ref.current.position.y = -motion.scroll.current * 1.6;
  });

  return (
    <points ref={ref} geometry={geometry}>
      <pointsMaterial
        color="#a1a1aa"
        size={0.075}
        transparent
        opacity={0.28}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

function ResultBar({
  clause,
  index,
  total,
}: {
  clause: Clause;
  index: number;
  total: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const relevance = clause.relevance ?? 0;
  // A floor on height, so a result with a near-zero score is still a visible
  // object. A bar of height zero looks like a missing result, not a bad one.
  const height = 0.6 + Math.max(relevance, 0) * 6.4;
  const x = (index - (total - 1) / 2) * 2.1;
  const color = useMemo(() => toneFor(clause.relevance), [clause.relevance]);
  const born = useRef(0);

  useFrame((_, delta) => {
    if (!ref.current) return;
    const dt = Math.min(delta, 0.05);
    // Bars grow from the field rather than appearing, staggered by rank, so
    // the ordering is legible as it arrives.
    born.current = Math.min(born.current + dt, 4);
    const t = Math.max(0, Math.min((born.current - index * 0.07) / 0.55, 1));
    const eased = 1 - Math.pow(1 - t, 3);
    // A bar at zero height is indistinguishable from a missing result, so the
    // growth starts at a quarter rather than at nothing.
    const grown = 0.25 + eased * 0.75;
    ref.current.scale.y = grown;
    ref.current.position.y = -3.2 + (height * grown) / 2;
  });

  return (
    <mesh ref={ref} position={[x, -3.2, 0]}>
      <boxGeometry args={[1.15, height, 1.15]} />
      <meshPhysicalMaterial
        color={color}
        roughness={0.45}
        metalness={0.04}
        clearcoat={0.5}
        clearcoatRoughness={0.3}
        transparent
        opacity={0.92}
      />
    </mesh>
  );
}

export default function RetrievalScene({
  clauses,
  busy,
  corpusSize,
}: {
  clauses: Clause[] | null;
  busy: boolean;
  corpusSize: number;
}) {
  const { camera } = useThree();
  const motion = useStageMotion();
  const groupRef = useRef<THREE.Group>(null);

  useEffect(() => {
    camera.position.set(0, 6, 22);
  }, [camera]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const p = motion.scroll.current;
    const [px, py] = motion.pointer.current;

    // Scrolling swings the camera from an oblique three-quarter view down to
    // near eye level with the bars, where the heights can actually be compared.
    // The scene is most decorative where the reader is reading prose, and most
    // like a chart where they are reading results.
    const k = 1 - Math.exp(-3.5 * dt);
    camera.position.y += (6 - p * 5.5 + py * 1.2 - camera.position.y) * k;
    camera.position.z += (22 - p * 4 - camera.position.z) * k;
    camera.position.x += (px * 2.2 - camera.position.x) * k;
    camera.lookAt(0, -1.4, 0);

    if (groupRef.current) {
      groupRef.current.rotation.y += (px * 0.16 - groupRef.current.rotation.y) * k;
    }
  });

  const shown = clauses?.slice(0, 6) ?? [];

  return (
    <group ref={groupRef}>
      <CorpusField size={corpusSize} searching={busy} />
      {shown.map((clause, i) => (
        <ResultBar
          key={clause.citation_key}
          clause={clause}
          index={i}
          total={shown.length}
        />
      ))}
      {/* The floor the corpus and the results share, so the bars read as
          standing on something rather than floating. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -3.25, 0]}>
        <circleGeometry args={[17, 64]} />
        <meshBasicMaterial color="#71717a" transparent opacity={0.05} />
      </mesh>
    </group>
  );
}
