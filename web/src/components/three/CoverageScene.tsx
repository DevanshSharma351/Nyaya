/* eslint-disable react-hooks/immutability --
 * Per-frame transform writes through refs; see the note in stage.tsx. */
"use client";

/**
 * The control pack as a surface with holes in it.
 *
 * Every mandatory control in the pack is a tile. A covered control is a solid
 * tile that stands proud of the plane; a gap is an open ring that sits below
 * it. Blockers are red and majors amber, matching the rest of the interface.
 *
 * The reason for drawing it this way rather than as a percentage: a coverage
 * ratio invites the reader to feel good about a large number, and the number is
 * not the finding. The finding is the shape of what is missing - whether the
 * gaps cluster in one area of the pack or are scattered across it, which is the
 * difference between one piece of work and twelve. That is legible here and
 * invisible in a ratio.
 *
 * Scroll tilts the plane from face-on, where the layout reads as a map, to
 * oblique, where the depth difference between covered and missing is obvious.
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { ControlCoverage } from "@/lib/api";
import { useStageMotion } from "./stage";

const COLUMNS = 6;

function Tile({
  control,
  index,
  total,
}: {
  control: ControlCoverage;
  index: number;
  total: number;
}) {
  const ref = useRef<THREE.Group>(null);
  const born = useRef(0);

  const rows = Math.ceil(total / COLUMNS);
  const column = index % COLUMNS;
  const row = Math.floor(index / COLUMNS);
  const x = (column - (COLUMNS - 1) / 2) * 2.5;
  const z = (row - (rows - 1) / 2) * 2.5;

  // Colour is spent only on the half of the pack that needs action. A covered
  // control is neutral: it is the absence of a problem, and the absence of a
  // problem does not need a colour.
  const color = control.is_gap
    ? control.severity === "blocker"
      ? "#b42318"
      : "#b54708"
    : "#c4c4c8";
  // Covered stands proud, missing sits below. The sign of the offset is the
  // whole message.
  const targetY = control.is_gap ? -0.75 : 0.45;

  useFrame((_, delta) => {
    if (!ref.current) return;
    const dt = Math.min(delta, 0.05);
    born.current = Math.min(born.current + dt, 4);
    // Staggered by position rather than by index, so the pack assembles as a
    // wave across the plane instead of a queue.
    const t = Math.max(0, Math.min((born.current - (column + row) * 0.045) / 0.6, 1));
    const eased = 1 - Math.pow(1 - t, 3);
    // Never starts from nothing; see the note in LifecycleScene.
    ref.current.scale.setScalar(0.4 + eased * 0.6);
    ref.current.position.y = targetY * eased;
  });

  return (
    <group ref={ref} position={[x, 0, z]}>
      {control.is_gap ? (
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.85, 0.11, 12, 40]} />
          <meshBasicMaterial color={color} transparent opacity={0.9} />
        </mesh>
      ) : (
        <mesh>
          <boxGeometry args={[1.75, 0.34, 1.75]} />
          <meshPhysicalMaterial
            color={color}
            roughness={0.5}
            metalness={0.03}
            clearcoat={0.45}
            clearcoatRoughness={0.35}
            transparent
            opacity={0.95}
          />
        </mesh>
      )}
    </group>
  );
}

export default function CoverageScene({
  controls,
}: {
  controls: ControlCoverage[] | null;
}) {
  const { camera } = useThree();
  const motion = useStageMotion();
  const planeRef = useRef<THREE.Group>(null);

  useEffect(() => {
    camera.position.set(0, 17, 0.1);
  }, [camera]);

  // Gaps first. The reader's eye lands top-left, and that is where the
  // actionable half of the pack belongs.
  const ordered = useMemo(() => {
    if (!controls) return [];
    return [...controls].sort((a, b) => Number(b.is_gap) - Number(a.is_gap));
  }, [controls]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const k = 1 - Math.exp(-3 * dt);
    const p = motion.scroll.current;
    const [px, py] = motion.pointer.current;

    // From directly overhead at the top of the page to a low oblique at the
    // foot of it.
    // Framed so the whole pack is in view at the top of the page - a plane
    // 26 units across needs the camera well back at this field of view - and
    // then swung down to an oblique where the depth difference between covered
    // and missing is what the reader is looking at.
    camera.position.y += (17 - p * 9 + py * 1.6 - camera.position.y) * k;
    camera.position.z += (0.1 + p * 17 - camera.position.z) * k;
    camera.position.x += (px * 3 - camera.position.x) * k;
    camera.lookAt(0, 0, 0);

    if (planeRef.current) {
      planeRef.current.rotation.y += dt * 0.035;
    }
  });

  return (
    <group ref={planeRef}>
      {ordered.map((control, i) => (
        <Tile
          key={control.control_id}
          control={control}
          index={i}
          total={ordered.length}
        />
      ))}
      {/* The plane the pack sits on, so "below the surface" is a real
          reference and not just a lower number. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]}>
        <planeGeometry args={[26, 26]} />
        <meshBasicMaterial color="#71717a" transparent opacity={0.05} />
      </mesh>
    </group>
  );
}
