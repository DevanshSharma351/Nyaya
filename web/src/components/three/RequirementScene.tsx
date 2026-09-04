/* eslint-disable react-hooks/immutability --
 * Per-frame transform writes through refs; see the note in stage.tsx. */
"use client";

/**
 * Extracted requirements, drawn as the structures they are.
 *
 * EARS patterns are not labels, they are shapes: a ubiquitous requirement is
 * one clause, an event-driven one is a trigger and a response, a complex one
 * adds a state precondition. So each requirement is drawn as a chain with
 * exactly that many segments, and the reader can count the parts of an
 * obligation without reading it.
 *
 * The satellites orbiting a chain are its acceptance criteria - a requirement
 * with none is testable only in principle - and the red spikes are detected
 * defects. A fabricated quantity is the one that matters most and is the least
 * visible in prose, because it reads as precision.
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { ExtractedRequirement } from "@/lib/api";
import { useStageMotion } from "./stage";

/*
 * Risk as weight, with one exception.
 *
 * Low, medium and high are shades: they are a scale, and a scale should look
 * like one. Critical gets the only colour in the scene, because it is the only
 * level at which a reader is being asked to stop and do something.
 */
const RISK_COLOR: Record<string, string> = {
  low: "#d4d4d8",
  medium: "#8b8b93",
  high: "#52525b",
  critical: "#b42318",
};

/** How many clauses the EARS pattern has. This is the pattern's definition. */
const ARITY: Record<string, number> = {
  ubiquitous: 1,
  event_driven: 2,
  "event-driven": 2,
  state_driven: 2,
  "state-driven": 2,
  unwanted: 2,
  optional: 2,
  complex: 3,
};

function Chain({
  requirement,
  index,
  total,
}: {
  requirement: ExtractedRequirement;
  index: number;
  total: number;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const born = useRef(0);
  const motion = useStageMotion();

  const segments = ARITY[requirement.ears_pattern] ?? 1;
  const color = RISK_COLOR[requirement.risk_level] ?? "#0a84ff";
  const criteria = Math.min(requirement.acceptance_criteria.length, 5);
  const defects = Math.min(requirement.defects.length, 4);

  // Requirements are laid out along a shallow arc rather than a line, so the
  // ones behind are not hidden by the ones in front.
  const angle = ((index - (total - 1) / 2) / Math.max(total, 1)) * 1.5;
  const x = Math.sin(angle) * 11;
  const z = -Math.cos(angle) * 4 - index * 0.4;

  useFrame((_, delta) => {
    if (!groupRef.current) return;
    const dt = Math.min(delta, 0.05);
    born.current = Math.min(born.current + dt, 4);
    const t = Math.max(0, Math.min((born.current - index * 0.11) / 0.7, 1));
    const eased = 1 - Math.pow(1 - t, 3);
    // Never starts from nothing; see the note in LifecycleScene.
    groupRef.current.scale.setScalar(0.35 + eased * 0.65);
    groupRef.current.position.y = (1 - eased) * -3;
    // Each chain rotates at its own rate so the group never reads as one rigid
    // object being spun.
    groupRef.current.rotation.y += dt * (0.16 + (index % 3) * 0.05);
    groupRef.current.rotation.x = motion.scroll.current * 0.5;
  });

  return (
    <group ref={groupRef} position={[x, 0, z]}>
      {Array.from({ length: segments }, (_, s) => (
        <mesh key={s} position={[0, (s - (segments - 1) / 2) * 1.35, 0]}>
          <boxGeometry args={[1.5, 1.05, 1.5]} />
          <meshPhysicalMaterial
            color={color}
            roughness={0.44}
            metalness={0.04}
            clearcoat={0.55}
            clearcoatRoughness={0.3}
            transparent
            opacity={0.95}
          />
        </mesh>
      ))}

      {Array.from({ length: criteria }, (_, c) => {
        const a = (c / Math.max(criteria, 1)) * Math.PI * 2;
        return (
          <mesh key={`c${c}`} position={[Math.cos(a) * 2.3, -0.2, Math.sin(a) * 2.3]}>
            <sphereGeometry args={[0.19, 16, 16]} />
            <meshBasicMaterial color="#71717a" transparent opacity={0.7} />
          </mesh>
        );
      })}

      {Array.from({ length: defects }, (_, d) => {
        const a = (d / Math.max(defects, 1)) * Math.PI * 2 + 0.4;
        return (
          <mesh
            key={`d${d}`}
            position={[Math.cos(a) * 1.4, 1.6, Math.sin(a) * 1.4]}
            rotation={[0, 0, Math.cos(a) * 0.5]}
          >
            <coneGeometry args={[0.16, 0.9, 8]} />
            <meshBasicMaterial color="#b42318" />
          </mesh>
        );
      })}
    </group>
  );
}

/** Before extraction runs: unstructured prose, drifting. */
function Unstructured() {
  const ref = useRef<THREE.Points>(null);
  const geometry = useMemo(() => {
    const count = 520;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (((i * 7919) % 200) / 100 - 1) * 14;
      positions[i * 3 + 1] = (((i * 104729) % 200) / 100 - 1) * 6;
      positions[i * 3 + 2] = (((i * 15485863) % 200) / 100 - 1) * 8;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geometry;
  }, []);

  useFrame((_, delta) => {
    if (!ref.current) return;
    ref.current.rotation.y += Math.min(delta, 0.05) * 0.05;
  });

  return (
    <points ref={ref} geometry={geometry}>
      <pointsMaterial
        color="#a1a1aa"
        size={0.07}
        transparent
        opacity={0.5}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

export default function RequirementScene({
  requirements,
}: {
  requirements: ExtractedRequirement[] | null;
}) {
  const { camera } = useThree();
  const motion = useStageMotion();

  useEffect(() => {
    camera.position.set(0, 2, 22);
  }, [camera]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const k = 1 - Math.exp(-3.5 * dt);
    const p = motion.scroll.current;
    const [px, py] = motion.pointer.current;
    camera.position.z += (22 - p * 6 - camera.position.z) * k;
    camera.position.y += (2 + py * 1.4 + p * 3 - camera.position.y) * k;
    camera.position.x += (px * 2.4 - camera.position.x) * k;
    camera.lookAt(0, 0, 0);
  });

  const shown = requirements?.slice(0, 7) ?? [];

  return (
    <group>
      {shown.length === 0 ? (
        <Unstructured />
      ) : (
        shown.map((requirement, i) => (
          <Chain
            key={requirement.statement}
            requirement={requirement}
            index={i}
            total={shown.length}
          />
        ))
      )}
    </group>
  );
}
