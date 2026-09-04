/* eslint-disable react-hooks/immutability --
 * Per-frame transform writes through refs; see the note in stage.tsx. */
"use client";

/**
 * Retrieval as what it is: a shortlist lifted out of a corpus, in rank order.
 *
 * The earlier version had a translucent floor disc seventeen units across. In a
 * panel this wide and short it filled the entire frame, and the result was a
 * pale grey dome with the actual data - a scatter of small points and a row of
 * thin bars - invisible against it. It read as a rendering failure, which is
 * the worst thing an empty state can do.
 *
 * What is drawn now: the corpus is a shallow band of marks, one per indexed
 * clause, so the size of the haystack is the number the API reports rather than
 * a metaphor. The results stand out of it as columns, ordered left to right by
 * rank, with height set by the cross-encoder's score.
 *
 * The gap between the first column and the rest is the point. Measured on the
 * labelled set, the top result is the governing clause 82% of the time and the
 * second only 29%, so a first column that fails to separate from its neighbours
 * is a shortlist worth doubting - which is legible here and invisible in a
 * numbered list.
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { Clause } from "@/lib/api";
import { useStageMotion } from "./stage";

const FLOOR = -1.9;
const LEAD = new THREE.Color("#18181b");
const REST = new THREE.Color("#a1a1aa");

/** The corpus: one mark per indexed clause, on a shallow band. */
function CorpusField({ size, searching }: { size: number; searching: boolean }) {
  const ref = useRef<THREE.Points>(null);

  const geometry = useMemo(() => {
    const count = Math.max(size, 24);
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      // Deterministic placement, so the corpus looks the same on every visit.
      // A field that reshuffles per render is one nobody can recognise.
      const angle = i * Math.PI * (3 - Math.sqrt(5));
      const radius = 3.6 + ((i * 7919) % 100) / 100 * 4.4;
      positions[i * 3] = Math.cos(angle) * radius;
      positions[i * 3 + 1] = FLOOR - 0.3 + (((i * 104729) % 100) / 100) * 0.6;
      positions[i * 3 + 2] = Math.sin(angle) * radius * 0.55;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geometry;
  }, [size]);

  useFrame((_, delta) => {
    if (!ref.current) return;
    const dt = Math.min(delta, 0.05);
    // Spinning faster while a query runs is the one place in this interface
    // where motion reports state, and it is deliberate: retrieval takes long
    // enough that stillness reads as breakage.
    ref.current.rotation.y += dt * (searching ? 0.6 : 0.07);
    const material = ref.current.material as THREE.PointsMaterial;
    const target = searching ? 0.95 : 0.5;
    material.opacity += (target - material.opacity) * (1 - Math.exp(-5 * dt));
  });

  return (
    <points ref={ref} geometry={geometry}>
      <pointsMaterial
        color="#8b8b93"
        size={0.1}
        transparent
        opacity={0.5}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

function ResultColumn({
  clause,
  index,
  total,
}: {
  clause: Clause;
  index: number;
  total: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const born = useRef(0);

  // Cross-encoder scores on this corpus are small and very unevenly spread -
  // a correct top result routinely scores 0.08. Mapping them linearly makes
  // every column the same stub. The square root spreads the low end, where the
  // differences that matter actually live, without inventing any ordering.
  const score = Math.max(0, Math.min(clause.relevance ?? 0, 1));
  const height = 0.5 + Math.sqrt(score) * 4.6;
  const x = (index - (total - 1) / 2) * 1.6;
  const colour = useMemo(
    () => (index === 0 ? LEAD : REST.clone().lerp(LEAD, Math.max(0, 0.5 - index * 0.12))),
    [index],
  );

  useFrame((_, delta) => {
    if (!ref.current) return;
    const dt = Math.min(delta, 0.05);
    born.current = Math.min(born.current + dt, 4);
    const t = Math.max(0, Math.min((born.current - index * 0.07) / 0.55, 1));
    const eased = 1 - Math.pow(1 - t, 3);
    // Grows from a quarter, never from nothing: a column of zero height is
    // indistinguishable from a missing result rather than a weak one.
    const grown = 0.25 + eased * 0.75;
    ref.current.scale.y = grown;
    ref.current.position.y = FLOOR + (height * grown) / 2;
  });

  return (
    <mesh ref={ref} position={[x, FLOOR, 0]}>
      <boxGeometry args={[0.82, height, 0.82]} />
      <meshPhysicalMaterial
        color={colour}
        roughness={0.4}
        metalness={0.05}
        clearcoat={0.65}
        clearcoatRoughness={0.28}
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
    camera.position.set(0, 1.6, 13);
  }, [camera]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const k = 1 - Math.exp(-3.5 * dt);
    const p = motion.scroll.current;
    const [px, py] = motion.pointer.current;

    // Scrolling drops the camera towards the tops of the columns, where their
    // heights can be compared directly. The scene is most three-dimensional
    // where the reader is reading prose, and most like a chart where they are
    // reading results.
    camera.position.y += (1.6 - p * 1.4 + py * 0.8 - camera.position.y) * k;
    camera.position.z += (13 - p * 1.5 - camera.position.z) * k;
    camera.position.x += (px * 1.4 - camera.position.x) * k;
    camera.lookAt(0, -0.4, 0);

    if (groupRef.current) {
      groupRef.current.rotation.y += (px * 0.12 - groupRef.current.rotation.y) * k;
    }
  });

  const shown = clauses?.slice(0, 6) ?? [];

  return (
    <group ref={groupRef}>
      <CorpusField size={corpusSize} searching={busy} />
      {shown.map((clause, i) => (
        <ResultColumn
          key={clause.citation_key}
          clause={clause}
          index={i}
          total={shown.length}
        />
      ))}
    </group>
  );
}
