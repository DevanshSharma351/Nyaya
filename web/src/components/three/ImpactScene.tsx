/* eslint-disable react-hooks/immutability --
 * Per-frame transform writes through refs; see the note in stage.tsx. */
"use client";

/**
 * An amendment propagating through the requirements that depended on it.
 *
 * The centre holds the clauses that changed between two versions of a source.
 * The ring holds the requirements whose authority those clauses were - amber
 * where the clause was amended and the requirement may now be stale, red where
 * the clause was removed outright and the requirement is orphaned, citing
 * something that no longer exists.
 *
 * The travelling pulses are the one continuous animation in the application
 * that earns its place, because propagation is what this module is about: a
 * regulator changes two sentences and the question is how far that reaches.
 * A static edge says the link exists. A pulse says it carries.
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { Impact } from "@/lib/api";
import { useStageMotion } from "./stage";

type Link = { from: THREE.Vector3; to: THREE.Vector3; tone: string; phase: number };

function Pulse({ link }: { link: Link }) {
  const ref = useRef<THREE.Mesh>(null);
  const motion = useStageMotion();

  useFrame(() => {
    if (!ref.current) return;
    // Phase-offset per link so the pulses do not fire in lockstep, which would
    // read as one object flashing rather than many messages travelling.
    const t = (motion.age.current * 0.42 + link.phase) % 1;
    ref.current.position.lerpVectors(link.from, link.to, t);
    const material = ref.current.material as THREE.MeshBasicMaterial;
    // Fade in and out at the ends so a pulse does not pop into existence at
    // the clause and vanish at the requirement.
    material.opacity = Math.sin(t * Math.PI) * 0.9;
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.13, 12, 12]} />
      <meshBasicMaterial color={link.tone} transparent opacity={0} />
    </mesh>
  );
}

export default function ImpactScene({ impact }: { impact: Impact | null }) {
  const { camera } = useThree();
  const motion = useStageMotion();
  const groupRef = useRef<THREE.Group>(null);

  useEffect(() => {
    camera.position.set(0, 5, 22);
  }, [camera]);

  const { sources, targets, links } = useMemo(() => {
    const sources: { key: string; tone: string; position: THREE.Vector3 }[] = [];
    const targets: { key: string; tone: string; position: THREE.Vector3 }[] = [];
    const links: Link[] = [];
    if (!impact) return { sources, targets, links };

    // Amended and removed carry colour because a reader has to act on them.
    // An added clause is neutral: nothing that already exists is wrong because
    // of it.
    const changed = [
      ...impact.changed_clauses.map((k) => [k, "#b54708"] as const),
      ...impact.removed_clauses.map((k) => [k, "#b42318"] as const),
      ...impact.added_clauses.map((k) => [k, "#a1a1aa"] as const),
    ];

    changed.forEach(([key, tone], i) => {
      const angle = (i / Math.max(changed.length, 1)) * Math.PI * 2;
      sources.push({
        key,
        tone,
        position: new THREE.Vector3(Math.cos(angle) * 1.9, 0, Math.sin(angle) * 1.9),
      });
    });

    impact.affected.forEach((affected, i) => {
      const angle = (i / Math.max(impact.affected.length, 1)) * Math.PI * 2;
      const tone = affected.severity === "orphaned" ? "#b42318" : "#b54708";
      const position = new THREE.Vector3(
        Math.cos(angle) * 9,
        ((i % 5) - 2) * 1.1,
        Math.sin(angle) * 9,
      );
      targets.push({ key: affected.ref, tone, position });

      // Link each affected requirement to the clause it actually cites, when
      // that clause is one of the ones that changed. Falling back to the first
      // source would draw a dependency the data does not support.
      const source =
        sources.find((s) => s.key === affected.citation_key) ?? sources[0];
      if (source) {
        links.push({
          from: source.position,
          to: position,
          tone,
          phase: (i * 0.37) % 1,
        });
      }
    });

    return { sources, targets, links };
  }, [impact]);

  const edgeGeometry = useMemo(() => {
    const positions = new Float32Array(Math.max(links.length, 1) * 6);
    links.forEach((link, i) => {
      positions.set(
        [link.from.x, link.from.y, link.from.z, link.to.x, link.to.y, link.to.z],
        i * 6,
      );
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geometry;
  }, [links]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    const k = 1 - Math.exp(-3 * dt);
    const p = motion.scroll.current;
    const [px, py] = motion.pointer.current;
    camera.position.y += (5 + p * 9 + py * 1.5 - camera.position.y) * k;
    camera.position.z += (22 - p * 5 - camera.position.z) * k;
    camera.position.x += (px * 2.8 - camera.position.x) * k;
    camera.lookAt(0, 0, 0);
    if (groupRef.current) groupRef.current.rotation.y += dt * 0.05;
  });

  return (
    <group ref={groupRef}>
      <lineSegments geometry={edgeGeometry}>
        <lineBasicMaterial color="#c4c4c8" transparent opacity={1} depthWrite={false} />
      </lineSegments>

      {links.map((link, i) => (
        <Pulse key={i} link={link} />
      ))}

      {sources.map((source) => (
        <mesh key={source.key} position={source.position}>
          <icosahedronGeometry args={[0.62, 3]} />
          <meshPhysicalMaterial
            color={source.tone}
            roughness={0.36}
            metalness={0.05}
            clearcoat={0.7}
            clearcoatRoughness={0.25}
          />
        </mesh>
      ))}

      {targets.map((target) => (
        <mesh key={target.key} position={target.position}>
          <boxGeometry args={[0.62, 0.62, 0.62]} />
          <meshPhysicalMaterial
            color={target.tone}
            roughness={0.45}
            metalness={0.04}
            clearcoat={0.5}
            clearcoatRoughness={0.3}
            transparent
            opacity={0.95}
          />
        </mesh>
      ))}
    </group>
  );
}
