/* eslint-disable react-hooks/immutability --
 * Per-frame transform writes through refs; see the note in stage.tsx. */
"use client";

/**
 * The TOPSIS decision, drawn as the geometry it actually is.
 *
 * TOPSIS is not a scoring heuristic dressed up in mathematics: it computes, for
 * each candidate, the distance to a synthetic ideal and to a synthetic
 * anti-ideal, and ranks by relative closeness. That is a statement about
 * position in space, so it can be drawn without inventing anything.
 *
 * The bright node at the top is the ideal - the best value available on every
 * criterion at once, which no real lifecycle model achieves. The dark node at
 * the bottom is its opposite. Each candidate sits on the axis between them at
 * its own closeness coefficient, which is exactly the number the ranking uses.
 *
 * Drawing it this way makes one thing visible that a bar chart hides: whether
 * the leader is genuinely separated from the field or merely first. When two
 * candidates sit at the same height, the recommendation is a coin toss, and the
 * engine says so - `close_call` - but the picture says it faster.
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { SDLCRank } from "@/lib/api";
import { useStageMotion } from "./stage";

const TOP = 5.5;
const BOTTOM = -5.5;

function Candidate({
  rank,
  index,
  total,
  leading,
}: {
  rank: SDLCRank;
  index: number;
  total: number;
  leading: boolean;
}) {
  const ref = useRef<THREE.Group>(null);
  const born = useRef(0);

  // Height is the closeness coefficient, mapped onto the ideal/anti-ideal
  // axis. Angle only separates candidates that would otherwise overlap; it
  // carries no meaning and is not presented as if it did.
  const y = BOTTOM + rank.closeness * (TOP - BOTTOM);
  const angle = (index / Math.max(total, 1)) * Math.PI * 2;
  const radius = 4.6;
  const x = Math.cos(angle) * radius;
  const z = Math.sin(angle) * radius;
  const size = leading ? 0.72 : 0.44;

  useFrame((_, delta) => {
    if (!ref.current) return;
    const dt = Math.min(delta, 0.05);
    born.current = Math.min(born.current + dt, 4);
    const t = Math.max(0, Math.min((born.current - index * 0.09) / 0.75, 1));
    const eased = 1 - Math.pow(1 - t, 3);
    // Grows from a third of full size, never from nothing. An entrance that
    // starts at zero makes the object's existence depend on the render loop
    // having run, and a scene that renders one frame - a screenshot, a paused
    // tab - then shows an empty stage rather than a small one.
    ref.current.scale.setScalar(0.34 + eased * 0.66);
    // Candidates rise from the anti-ideal to their own closeness, which reads
    // as the ranking being computed rather than asserted.
    ref.current.position.y = BOTTOM + (y - BOTTOM) * eased;
  });

  // The leader is the darkest object in the scene and the rest recede. On a
  // white ground weight separates far more cleanly than hue, and it keeps the
  // one green in the interface reserved for "verified".
  const color = leading ? "#18181b" : "#b4b4bb";

  return (
    <group ref={ref} position={[x, BOTTOM, z]}>
      <mesh>
        <icosahedronGeometry args={[size, 3]} />
        <meshPhysicalMaterial
          color={color}
          roughness={0.36}
          metalness={0.06}
          clearcoat={0.7}
          clearcoatRoughness={0.25}
        />
      </mesh>
    </group>
  );
}

/** The line each candidate would have to travel to reach the ideal. */
function Tethers({ ranked }: { ranked: SDLCRank[] }) {
  const ref = useRef<THREE.LineSegments>(null);

  const geometry = useMemo(() => {
    const positions = new Float32Array(ranked.length * 6);
    ranked.forEach((rank, i) => {
      const angle = (i / Math.max(ranked.length, 1)) * Math.PI * 2;
      const y = BOTTOM + rank.closeness * (TOP - BOTTOM);
      positions.set(
        [Math.cos(angle) * 4.6, y, Math.sin(angle) * 4.6, 0, TOP, 0],
        i * 6,
      );
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geometry;
  }, [ranked]);

  useFrame((_, delta) => {
    if (!ref.current) return;
    const material = ref.current.material as THREE.LineBasicMaterial;
    material.opacity += (0.85 - material.opacity) * (1 - Math.exp(-4 * Math.min(delta, 0.05)));
  });

  return (
    <lineSegments ref={ref} geometry={geometry}>
      <lineBasicMaterial color="#c4c4c8" transparent opacity={0} depthWrite={false} />
    </lineSegments>
  );
}

export default function LifecycleScene({ ranked }: { ranked: SDLCRank[] | null }) {
  const { camera } = useThree();
  const motion = useStageMotion();
  const groupRef = useRef<THREE.Group>(null);
  const idealRef = useRef<THREE.Mesh>(null);

  useEffect(() => {
    camera.position.set(0, 0, 16);
  }, [camera]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const k = 1 - Math.exp(-3 * dt);
    const p = motion.scroll.current;
    const [px, py] = motion.pointer.current;

    // Side elevation at the top of the page, where separation along the axis
    // is what matters; rising towards a three-quarter view further down.
    // Framed for the panel, which is wide and short: at this aspect the
    // limiting dimension is height, and the ideal/anti-ideal axis is eleven
    // units of it.
    camera.position.y += (p * 8 + py * 1.2 - camera.position.y) * k;
    camera.position.z += (16 - p * 3 - camera.position.z) * k;
    camera.position.x += (px * 2.6 - camera.position.x) * k;
    camera.lookAt(0, 0, 0);

    if (groupRef.current) groupRef.current.rotation.y += dt * 0.09;
    // The ideal is the only thing in this application that pulses. It is the
    // one object on screen that is not a measurement - it is a construction,
    // and it should not sit still pretending to be a result.
    if (idealRef.current) {
      const s = 1 + Math.sin(motion.age.current * 1.6) * 0.06;
      idealRef.current.scale.setScalar(s);
    }
  });

  const list = ranked ?? [];

  return (
    <group ref={groupRef}>
      {/* On a white ground the ideal cannot be the brightest thing in the
          scene - there is nothing brighter than the page. So it is the darkest
          and the most solid, and the anti-ideal is the faintest. */}
      <mesh ref={idealRef} position={[0, TOP, 0]}>
        <icosahedronGeometry args={[0.55, 3]} />
        <meshBasicMaterial color="#09090b" />
      </mesh>
      <mesh position={[0, BOTTOM, 0]}>
        <icosahedronGeometry args={[0.4, 2]} />
        <meshBasicMaterial color="#d4d4d8" />
      </mesh>

      {/* The axis itself. */}
      <mesh position={[0, 0, 0]}>
        <cylinderGeometry args={[0.012, 0.012, TOP - BOTTOM, 8]} />
        <meshBasicMaterial color="#c4c4c8" transparent opacity={1} />
      </mesh>

      {list.length > 0 && <Tethers ranked={list} />}

      {list.map((rank, i) => (
        <Candidate
          key={rank.model}
          rank={rank}
          index={i}
          total={list.length}
          leading={i === 0}
        />
      ))}
    </group>
  );
}
