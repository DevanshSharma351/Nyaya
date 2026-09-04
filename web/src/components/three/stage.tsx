/* eslint-disable react-hooks/immutability --
 * The whole mechanism here is a bag of refs shared between DOM event handlers
 * and the render loop, and mutating it is the point: scroll position and
 * pointer position must reach the scene without passing through React state,
 * because doing so would re-render every scene sixty times a second to move a
 * camera by a fraction of a unit.
 *
 * The rule is right about the general case and this is a genuine exception, so
 * it is disabled for exactly one rule in exactly this file. Nothing here
 * participates in React's rendering model beyond mounting the canvas.
 */
"use client";

/**
 * The scene substrate every module shares.
 *
 * Three problems are solved once here rather than seven times in the scenes.
 *
 * Scroll. Every module drives its scene from scroll position, and the naive
 * implementation - scroll listener writes React state, state flows down to the
 * scene - re-renders the whole subtree on every scroll event. So progress is
 * written into a ref and read inside `useFrame`. React never sees it, and the
 * value is smoothed towards its target so a trackpad's jittery deltas do not
 * translate into a jittery camera.
 *
 * Pointer. Scenes react to the cursor, which needs the same treatment for the
 * same reason, in normalised [-1, 1] device coordinates.
 *
 * Idling. There is deliberately no visibility gate here, and there was one -
 * `frameloop="never"` whenever `document.hidden`. It caused a real bug. React
 * Three Fiber applies its measured canvas size on its next render, so a scene
 * that mounts while the document reports itself hidden never renders, never
 * takes its size, and sits at the default 300x150 canvas showing nothing. That
 * is not a hypothetical: it is what a page opened in a background tab does.
 *
 * The gate was also solving a problem the platform already solves. Browsers
 * throttle and then suspend requestAnimationFrame in backgrounded tabs on their
 * own, so the render loop was never the CPU cost it looked like.
 */

import { Canvas, useFrame } from "@react-three/fiber";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

export type StageMotion = {
  /** Smoothed scroll progress through the page, 0 at the top, 1 at the end. */
  scroll: { current: number };
  /** Raw target, before smoothing. Useful when a scene needs to snap. */
  scrollTarget: { current: number };
  /** Pointer in normalised device coordinates, smoothed. */
  pointer: { current: [number, number] };
  /** Seconds since the scene mounted, for entrance choreography. */
  age: { current: number };
};

const MotionContext = createContext<StageMotion | null>(null);

export function useStageMotion(): StageMotion {
  const motion = useContext(MotionContext);
  if (!motion) {
    throw new Error("useStageMotion must be called inside a <Stage>");
  }
  return motion;
}

/**
 * Advances the smoothed values once per frame.
 *
 * This lives inside the Canvas because it must run on the render clock: doing
 * it on a scroll event instead would update at the event rate, which is both
 * higher and less regular than the frame rate, and the scene would judder.
 */
function MotionDriver({ motion }: { motion: StageMotion }) {
  useFrame((_, delta) => {
    const dt = Math.min(delta, 0.05);
    // Exponential smoothing, frame-rate independent. A fixed per-frame lerp
    // would move twice as fast at 120Hz as at 60Hz.
    const k = 1 - Math.exp(-7 * dt);
    motion.scroll.current += (motion.scrollTarget.current - motion.scroll.current) * k;
    motion.age.current += dt;
  });
  return null;
}

export function Stage({
  children,
  camera = { position: [0, 0, 18], fov: 50 },
  className = "scene-panel-canvas",
  onCreatedNote,
}: {
  children: ReactNode;
  camera?: { position: [number, number, number]; fov: number };
  className?: string;
  onCreatedNote?: string;
}) {
  const motion = useMemo<StageMotion>(
    () => ({
      scroll: { current: 0 },
      scrollTarget: { current: 0 },
      pointer: { current: [0, 0] },
      age: { current: 0 },
    }),
    [],
  );

  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function readScroll() {
      const travel = document.documentElement.scrollHeight - window.innerHeight;
      // A page shorter than the viewport has no scroll travel. Dividing by zero
      // there yields NaN, which propagates into every position it touches and
      // silently empties the scene.
      motion.scrollTarget.current = travel > 8 ? window.scrollY / travel : 0;
    }
    function readPointer(event: PointerEvent) {
      motion.pointer.current = [
        (event.clientX / window.innerWidth) * 2 - 1,
        -((event.clientY / window.innerHeight) * 2 - 1),
      ];
    }
    readScroll();
    window.addEventListener("scroll", readScroll, { passive: true });
    window.addEventListener("resize", readScroll);
    window.addEventListener("pointermove", readPointer, { passive: true });
    return () => {
      window.removeEventListener("scroll", readScroll);
      window.removeEventListener("resize", readScroll);
      window.removeEventListener("pointermove", readPointer);
    };
  }, [motion]);

  return (
    <div ref={hostRef} className={className} aria-hidden data-scene={onCreatedNote}>
      <Canvas
        dpr={[1, 2]}
        // Measure on resize only. Observing scroll as well makes the size
        // depend on a debounced callback, which is one more thing that has to
        // fire before the scene can draw at all.
        resize={{ scroll: false, debounce: { scroll: 0, resize: 0 } }}
        camera={{ ...camera, near: 0.1, far: 260 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      >
        <MotionContext.Provider value={motion}>
          <MotionDriver motion={motion} />
          {children}
        </MotionContext.Provider>
      </Canvas>
    </div>
  );
}

/**
 * The lighting rig, identical in every module.
 *
 * A key from the upper left, a soft neutral fill opposite it, and a strong
 * ambient. The balance is set for a white ground, which is a genuinely
 * different problem from a dark one: against black, objects are read by the
 * light falling on them, so a dim ambient and a hard key work. Against white,
 * they are read by their own darkness and by the shadow at their edge, so the
 * ambient has to be high or everything turns into a silhouette.
 *
 * Sharing it is what makes six separate scenes read as one application rather
 * than six demos.
 */
export function Rig() {
  return (
    <>
      <ambientLight intensity={1.15} />
      <directionalLight position={[8, 12, 8]} intensity={1.6} />
      <directionalLight position={[-8, -4, -6]} intensity={0.5} color="#e4e4e7" />
    </>
  );
}
