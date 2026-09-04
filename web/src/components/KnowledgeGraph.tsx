/* eslint-disable react-hooks/immutability -- 
 * A WebGL render loop is imperative by construction. Every frame mutates
 * simulation bodies and writes directly to Three.js objects through refs, which
 * is exactly what these rules exist to prevent in *rendering* code and exactly
 * what animation code must do: routing 137 positions per frame through React
 * state would re-render the tree sixty times a second to no purpose.
 *
 * The exception is deliberately file-scoped. Nothing here participates in
 * React's rendering model beyond mounting the canvas, and no other component in
 * this codebase carries it.
 */
"use client";

/**
 * The regulatory corpus as a 3D force-directed graph.
 *
 * This is 3D because the data is: clauses nest inside clauses inside documents,
 * and a hierarchy of that shape is genuinely hard to read flattened. The
 * alternative - a decorative 3D scene next to a 2D list - would be ornament,
 * which a compliance tool cannot afford.
 *
 * Layout runs on a simple force simulation in a `useFrame` loop rather than a
 * library, so the physics can be tuned to keep documents as stable anchors while
 * clauses settle around them. A layout that drifts continuously is pretty and
 * unusable; this one converges and then holds.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { Graph, GraphNode } from "@/lib/api";

const KIND_COLOR: Record<GraphNode["kind"], string> = {
  document: "#0a84ff",
  clause: "#bf5af2",
  control: "#30d158",
  requirement: "#ff9f0a",
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
    // Documents are placed deterministically on a ring and pinned. Anchoring
    // them keeps the layout legible across reloads: the same corpus produces
    // the same arrangement, so a reader's spatial memory is worth something.
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
    const golden = Math.PI * (3 - Math.sqrt(5));
    const t = index * golden;
    const r = 4 + (index % 7) * 0.8;
    bodies.set(node.id, {
      node,
      position: new THREE.Vector3(
        Math.cos(t) * r,
        (Math.random() - 0.5) * 6,
        Math.sin(t) * r,
      ),
      velocity: new THREE.Vector3(),
      anchored: false,
    });
  });
  return bodies;
}

function Scene({
  graph,
  onHover,
}: {
  graph: Graph;
  onHover: (node: GraphNode | null) => void;
}) {
  const bodies = useMemo(() => buildBodies(graph), [graph]);
  const linesRef = useRef<THREE.LineSegments>(null);
  const groupRef = useRef<THREE.Group>(null);
  const { camera } = useThree();
  const settled = useRef(0);

  const nodes = useMemo(() => [...bodies.values()], [bodies]);
  const edges = useMemo(
    () =>
      graph.edges.filter((e) => bodies.has(e.source) && bodies.has(e.target)),
    [graph.edges, bodies],
  );

  // One mesh per node rather than an InstancedMesh. At ~140 nodes instancing
  // buys nothing measurable, and it removes a class of failure that is hard to
  // diagnose: an instanced mesh whose matrices are never uploaded renders as an
  // empty scene with a perfectly healthy WebGL context.
  const nodeRefs = useRef<(THREE.Mesh | null)[]>([]);

  useEffect(() => {
    camera.position.set(0, 3, 19);
  }, [camera]);

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
      if (mesh) mesh.position.copy(body.position);
    });

    if (linesRef.current) {
      const positions = linesRef.current.geometry.attributes.position
        .array as Float32Array;
      edges.forEach((edge, i) => {
        const a = bodies.get(edge.source)!.position;
        const b = bodies.get(edge.target)!.position;
        positions.set([a.x, a.y, a.z, b.x, b.y, b.z], i * 6);
      });
      linesRef.current.geometry.attributes.position.needsUpdate = true;
    }

    // A slow rotation reads as alive without demanding attention.
    if (groupRef.current) {
      groupRef.current.rotation.y += dt * 0.045;
    }
  });

  const lineGeometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(Math.max(edges.length, 1) * 6), 3),
    );
    return geometry;
  }, [edges.length]);

  return (
    <group ref={groupRef}>
      <lineSegments ref={linesRef} geometry={lineGeometry}>
        <lineBasicMaterial
          color="#8f8fb4"
          transparent
          opacity={0.4}
          depthWrite={false}
        />
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
            onHover(body.node);
          }}
          onPointerOut={() => onHover(null)}
        >
          <icosahedronGeometry args={[1, 2]} />
          <meshPhysicalMaterial
            color={KIND_COLOR[body.node.kind]}
            roughness={0.22}
            metalness={0.15}
            clearcoat={0.9}
            clearcoatRoughness={0.18}
            emissive={KIND_COLOR[body.node.kind]}
            emissiveIntensity={0.28}
          />
        </mesh>
      ))}
    </group>
  );
}

export default function KnowledgeGraph({ graph }: { graph: Graph }) {
  const [hovered, setHovered] = useState<GraphNode | null>(null);

  return (
    <div className="relative h-full w-full">
      <Canvas
        dpr={[1, 2]}
        camera={{ fov: 52, near: 0.1, far: 200 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.45} />
        <directionalLight position={[8, 12, 8]} intensity={1.5} />
        <directionalLight position={[-8, -4, -6]} intensity={0.45} color="#bf5af2" />
        <Scene graph={graph} onHover={setHovered} />
        <OrbitControls
          enablePan={false}
          enableDamping
          dampingFactor={0.06}
          minDistance={9}
          maxDistance={38}
          autoRotate={false}
        />
      </Canvas>

      {hovered && (
        <div className="glass-raised specular pointer-events-none absolute bottom-5 left-5 max-w-sm p-4">
          <div className="mono mb-1" style={{ color: KIND_COLOR[hovered.kind] }}>
            {hovered.label}
          </div>
          <p className="body m-0" style={{ color: "var(--text-secondary)" }}>
            {hovered.detail.slice(0, 190)}
            {hovered.detail.length > 190 ? "…" : ""}
          </p>
        </div>
      )}
    </div>
  );
}
