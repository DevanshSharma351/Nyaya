/* eslint-disable react-hooks/immutability --
 * A WebGL render loop is imperative by construction. Every frame mutates
 * simulation bodies and writes directly to Three.js objects through refs, which
 * is exactly what these rules exist to prevent in *rendering* code and exactly
 * what animation code must do: routing 140 positions per frame through React
 * state would re-render the tree sixty times a second to no purpose.
 */
"use client";

/**
 * The regulatory corpus as a force-directed graph.
 *
 * This is 3D because the data is: clauses nest inside clauses inside
 * documents, and a hierarchy of that shape is genuinely hard to read
 * flattened. The alternative - a decorative scene beside a 2D list - would be
 * ornament, which a compliance tool cannot afford.
 *
 * Layout is a hand-written force simulation rather than a library, so
 * documents can be pinned as stable anchors while clauses settle around them.
 * A layout that drifts forever is pretty and unusable; this one converges and
 * then holds, so a reader's spatial memory of the corpus is worth something
 * across reloads.
 *
 * Scroll drives the camera *through* the graph: at the top the whole corpus is
 * in frame, and by the foot of the page the camera is inside the cloud among
 * individual clauses. That is the module's argument made physical - the page
 * moves from the corpus in aggregate to a single clause you can cite.
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { Graph, GraphNode } from "@/lib/api";
import { useStageMotion } from "./stage";

/*
 * Neutral by kind, separated by value rather than by hue.
 *
 * Four hues for four node kinds looked like a legend and behaved like
 * confetti: hue is the strongest signal in a scene and spending it on a
 * category the reader can also get from size and position is waste. Documents
 * are the darkest because they anchor the layout; clauses recede.
 */
export const KIND_COLOR: Record<GraphNode["kind"], string> = {
  document: "#18181b",
  clause: "#a8a8b0",
  control: "#52525b",
  requirement: "#71717a",
};

type Body = {
  node: GraphNode;
  position: THREE.Vector3;
  velocity: THREE.Vector3;
  anchored: boolean;
};

function buildBodies(graph: Graph): Map<string, Body> {
  const bodies = new Map<string, Body>();
  const documents = graph.nodes.filter((n) => n.kind === "document");

  graph.nodes.forEach((node, index) => {
    if (node.kind === "document") {
      const i = documents.indexOf(node);
      const angle = (i / Math.max(documents.length, 1)) * Math.PI * 2;
      bodies.set(node.id, {
        node,
        position: new THREE.Vector3(Math.cos(angle) * 7, 0, Math.sin(angle) * 7),
        velocity: new THREE.Vector3(),
        anchored: true,
      });
      return;
    }
    // A golden-angle spiral for the initial scatter. Random placement gives a
    // different layout on every reload even with identical data, which makes
    // the picture useless as a thing to remember.
    const golden = Math.PI * (3 - Math.sqrt(5));
    const t = index * golden;
    const r = 4 + (index % 7) * 0.8;
    bodies.set(node.id, {
      node,
      position: new THREE.Vector3(Math.cos(t) * r, ((index % 11) - 5) * 0.6, Math.sin(t) * r),
      velocity: new THREE.Vector3(),
      anchored: false,
    });
  });
  return bodies;
}

export default function CorpusScene({
  graph,
  onHover,
  focus,
  interactive = false,
}: {
  graph: Graph;
  onHover?: (node: GraphNode | null) => void;
  /** Citation key to pull forward, when the reader has selected a clause. */
  focus?: string | null;
  /**
   * Hands the camera to the reader.
   *
   * Orbit controls and a scroll-driven camera cannot both own the camera - each
   * would overwrite the other every frame, and the result is a scene that
   * fights the mouse. So this is a choice, not a combination: the corpus module
   * is for exploring and gives the camera away; everywhere else scroll keeps it.
   */
  interactive?: boolean;
}) {
  const bodies = useMemo(() => buildBodies(graph), [graph]);
  const linesRef = useRef<THREE.LineSegments>(null);
  const groupRef = useRef<THREE.Group>(null);
  const { camera } = useThree();
  const motion = useStageMotion();
  const settled = useRef(0);

  const nodes = useMemo(() => [...bodies.values()], [bodies]);
  const edges = useMemo(
    () => graph.edges.filter((e) => bodies.has(e.source) && bodies.has(e.target)),
    [graph.edges, bodies],
  );

  // One mesh per node rather than an InstancedMesh. At ~140 nodes instancing
  // buys nothing measurable, and it removes a class of failure that is hard to
  // diagnose: an instanced mesh whose matrices are never uploaded renders as an
  // empty scene with a perfectly healthy WebGL context.
  const nodeRefs = useRef<(THREE.Mesh | null)[]>([]);

  useEffect(() => {
    camera.position.set(0, 2, 17);
  }, [camera]);

  const lineGeometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(Math.max(edges.length, 1) * 6), 3),
    );
    return geometry;
  }, [edges.length]);

  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    settled.current = Math.min(settled.current + dt, 6);
    const cooling = Math.max(0.08, 1 - settled.current / 6);

    // Repulsion, sampled rather than all-pairs: at this size the visual
    // difference is nil and the frame budget matters more than exactness.
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      if (a.anchored) continue;
      for (let k = 0; k < 12; k++) {
        const b = nodes[(i + 1 + k * 7) % nodes.length];
        if (b === a) continue;
        const dx = a.position.x - b.position.x;
        const dy = a.position.y - b.position.y;
        const dz = a.position.z - b.position.z;
        const d2 = dx * dx + dy * dy + dz * dz + 0.6;
        const force = (2.2 / d2) * cooling;
        a.velocity.x += dx * force * dt;
        a.velocity.y += dy * force * dt;
        a.velocity.z += dz * force * dt;
      }
      // A gentle pull to origin keeps the cloud in frame. It has to stay well
      // below the repulsion term: overwhelm that and every node collapses onto
      // the same point, which renders as an empty scene.
      a.velocity.addScaledVector(a.position, -0.09 * dt);
    }

    // Attraction along edges: an edge is a spring whose stiffness is the
    // strength of the relationship it represents.
    for (const edge of edges) {
      const a = bodies.get(edge.source)!;
      const b = bodies.get(edge.target)!;
      const dx = b.position.x - a.position.x;
      const dy = b.position.y - a.position.y;
      const dz = b.position.z - a.position.z;
      const distance = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1;
      const pull = (distance - 2.2) * (0.7 + edge.strength * 0.5) * dt;
      if (!a.anchored) {
        a.velocity.x += (dx / distance) * pull;
        a.velocity.y += (dy / distance) * pull;
        a.velocity.z += (dz / distance) * pull;
      }
      if (!b.anchored) {
        b.velocity.x -= (dx / distance) * pull;
        b.velocity.y -= (dy / distance) * pull;
        b.velocity.z -= (dz / distance) * pull;
      }
    }

    for (const body of nodes) {
      if (body.anchored) continue;
      body.velocity.multiplyScalar(0.86);
      body.position.addScaledVector(body.velocity, dt * 8);
    }

    nodes.forEach((body, i) => {
      const mesh = nodeRefs.current[i];
      if (!mesh) return;
      mesh.position.copy(body.position);
      // A selected clause grows and the rest recede, so "which one is that"
      // has an answer in the scene and not only in the list beside it.
      const selected = focus != null && body.node.label === focus;
      const base = 0.2 + body.node.weight * 0.13;
      const target = selected ? base * 2.4 : focus ? base * 0.75 : base;
      mesh.scale.lerp(new THREE.Vector3(target, target, target), 1 - Math.exp(-8 * dt));
    });

    if (linesRef.current) {
      const positions = linesRef.current.geometry.attributes.position.array as Float32Array;
      edges.forEach((edge, i) => {
        const a = bodies.get(edge.source)!.position;
        const b = bodies.get(edge.target)!.position;
        positions.set([a.x, a.y, a.z, b.x, b.y, b.z], i * 6);
      });
      linesRef.current.geometry.attributes.position.needsUpdate = true;
    }

    // Scroll flies the camera in from outside the cloud to inside it, and the
    // pointer parallaxes it slightly - enough to read as a window onto a solid
    // object rather than a picture of one. Skipped entirely when the reader
    // has the camera.
    if (!interactive) {
      const p = motion.scroll.current;
      const [px, py] = motion.pointer.current;
      const k = 1 - Math.exp(-4 * dt);
      camera.position.z += (26 - p * 19 - px * 1.2 - camera.position.z) * k;
      camera.position.y += (3 - p * 2 + py * 1.6 - camera.position.y) * k;
      camera.lookAt(0, 0, 0);
    }

    if (groupRef.current) {
      groupRef.current.rotation.y += dt * 0.045;
    }
  });

  return (
    <>
      {interactive && (
        <OrbitControls
          enablePan={false}
          enableDamping
          dampingFactor={0.06}
          minDistance={7}
          maxDistance={34}
        />
      )}
      <group ref={groupRef}>
      <lineSegments ref={linesRef} geometry={lineGeometry}>
        <lineBasicMaterial color="#d4d4d8" transparent opacity={0.95} depthWrite={false} />
      </lineSegments>

      {nodes.map((body, i) => (
        <mesh
          key={body.node.id}
          ref={(mesh) => {
            nodeRefs.current[i] = mesh;
          }}
          position={body.position}
          scale={0.2 + body.node.weight * 0.13}
          onPointerOver={(event) => {
            event.stopPropagation();
            onHover?.(body.node);
          }}
          onPointerOut={() => onHover?.(null)}
        >
          <icosahedronGeometry args={[1, 2]} />
          <meshPhysicalMaterial
            color={KIND_COLOR[body.node.kind]}
            roughness={0.42}
            metalness={0.05}
            clearcoat={0.6}
            clearcoatRoughness={0.3}
          />
        </mesh>
      ))}
      </group>
    </>
  );
}
