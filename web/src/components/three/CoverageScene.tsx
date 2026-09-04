/* eslint-disable react-hooks/immutability --
 * Per-frame transform writes through refs; see the note in stage.tsx. */
"use client";

/**
 * Coverage as what it actually is: a bipartite graph with holes on one side.
 *
 * The earlier version drew the control pack as a surface of tiles and rings.
 * It was legible only if you had already read the caption, because it showed
 * the *result* - covered or not - without showing the thing that produces the
 * result. A control is a gap for exactly one reason: nothing points at it.
 *
 * So this draws the pointing. Requirements are the column on the left, controls
 * are the grid on the right, and an edge means a requirement satisfies a
 * control. A covered control has a line running into it. A gap has none, and
 * sits there unconnected, which is the finding stated directly rather than
 * encoded in a colour the reader has to look up.
 *
 * It also makes the shape of the problem visible in a way a percentage cannot.
 * Four requirements against twenty-one controls looks like what it is - a
 * handful of threads reaching a wall - and whether the unreached controls
 * cluster in one area of the pack or scatter across it is the difference
 * between one piece of work and twelve.
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { ControlCoverage } from "@/lib/api";
import { useStageMotion } from "./stage";

const COLUMNS = 3;
const CONTROL_X = 3.2;
const REQUIREMENT_X = -7.2;

function toneFor(control: ControlCoverage): string {
  if (!control.is_gap) return "#52525b";
  return control.severity === "blocker" ? "#b42318" : "#b54708";
}

type Placed = { control: ControlCoverage; position: THREE.Vector3 };

export default function CoverageScene({
  controls,
}: {
  controls: ControlCoverage[] | null;
}) {
  const { camera } = useThree();
  const motion = useStageMotion();
  const groupRef = useRef<THREE.Group>(null);
  const edgesRef = useRef<THREE.LineSegments>(null);

  useEffect(() => {
    camera.position.set(0, 0, 15);
  }, [camera]);

  const { placed, requirements, edges } = useMemo(() => {
    const placed: Placed[] = [];
    const requirements = new Map<string, THREE.Vector3>();
    const edges: [THREE.Vector3, THREE.Vector3][] = [];
    if (!controls) return { placed, requirements, edges };

    // Gaps first, so the unconnected half of the pack reads top-left where the
    // eye lands. Ordering by outcome is the one arrangement that makes the
    // picture answer the module's question without being read left to right.
    const ordered = [...controls].sort(
      (a, b) => Number(b.is_gap) - Number(a.is_gap),
    );

    const rows = Math.ceil(ordered.length / COLUMNS);
    ordered.forEach((control, i) => {
      const column = i % COLUMNS;
      const row = Math.floor(i / COLUMNS);
      placed.push({
        control,
        position: new THREE.Vector3(
          CONTROL_X + column * 2.3,
          ((rows - 1) / 2 - row) * 1.25,
          0,
        ),
      });
    });

    // Requirements are only known through the controls they satisfy, so the
    // column is built from the union of every `satisfied_by`.
    const refs = [...new Set(ordered.flatMap((c) => c.satisfied_by))].sort();
    refs.forEach((ref, i) => {
      requirements.set(
        ref,
        new THREE.Vector3(REQUIREMENT_X, ((refs.length - 1) / 2 - i) * 1.6, 0),
      );
    });

    for (const { control, position } of placed) {
      for (const ref of control.satisfied_by) {
        const from = requirements.get(ref);
        if (from) edges.push([from, position]);
      }
    }

    return { placed, requirements, edges };
  }, [controls]);

  const edgeGeometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(Math.max(edges.length, 1) * 6);
    edges.forEach(([from, to], i) => {
      positions.set([from.x, from.y, from.z, to.x, to.y, to.z], i * 6);
    });
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geometry;
  }, [edges]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const k = 1 - Math.exp(-3 * dt);
    const p = motion.scroll.current;
    const [px, py] = motion.pointer.current;

    // Face-on at the top of the page, where the graph reads as a diagram, then
    // swung to an oblique further down where the two sides separate in depth.
    camera.position.z += (15 - p * 2 - camera.position.z) * k;
    camera.position.x += (px * 1.8 - camera.position.x) * k;
    camera.position.y += (py * 1.2 - camera.position.y) * k;
    camera.lookAt(0, 0, 0);

    if (groupRef.current) {
      groupRef.current.rotation.y = p * 0.5 + px * 0.08;
    }
    if (edgesRef.current) {
      // Edges fade in after the nodes, so the connections read as being drawn
      // between things that already exist.
      const material = edgesRef.current.material as THREE.LineBasicMaterial;
      const target = Math.min(motion.age.current / 1.4, 1) * 0.9;
      material.opacity += (target - material.opacity) * k;
    }
  });

  return (
    <group ref={groupRef}>
      <lineSegments ref={edgesRef} geometry={edgeGeometry}>
        <lineBasicMaterial color="#18181b" transparent opacity={0} depthWrite={false} />
      </lineSegments>

      {[...requirements.values()].map((position, i) => (
        <mesh key={`req-${i}`} position={position}>
          <sphereGeometry args={[0.3, 20, 20]} />
          <meshPhysicalMaterial
            color="#18181b"
            roughness={0.35}
            metalness={0.06}
            clearcoat={0.7}
          />
        </mesh>
      ))}

      {placed.map(({ control, position }) => (
        <mesh key={control.control_id} position={position}>
          {/* A covered control is a solid block; a gap is a flat open ring, so
              the two differ in silhouette and not only in colour. */}
          {control.is_gap ? (
            <torusGeometry args={[0.34, 0.075, 10, 28]} />
          ) : (
            <boxGeometry args={[0.62, 0.62, 0.62]} />
          )}
          <meshPhysicalMaterial
            color={toneFor(control)}
            roughness={0.42}
            metalness={0.05}
            clearcoat={0.6}
            clearcoatRoughness={0.3}
          />
        </mesh>
      ))}
    </group>
  );
}
