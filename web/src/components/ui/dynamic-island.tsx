"use client";

/**
 * A Dynamic Island.
 *
 * A single pill-shaped surface that changes size to match whatever it currently
 * has to say, animating between shapes rather than swapping panels. The idea is
 * Apple's, and the reason it works is that the *container* is the constant: a
 * reader tracks one object changing state instead of several appearing and
 * disappearing, which is far less demanding to follow.
 *
 * Two details do most of the work and are easy to get wrong:
 *
 *  - The morph is a spring on width, height and radius together. Animating
 *    width and height without the radius makes the corners visibly pop, which
 *    is the single tell that separates this from a resizing div.
 *  - Content is measured out and in on its own, faster than the container. If
 *    the text cross-fades on the same curve as the shape, it appears to stretch
 *    with it.
 *
 * The API is the one the cult-ui component exposes, so the demo written against
 * it works unchanged.
 */

import {
  AnimatePresence,
  MotionConfig,
  motion,
  useReducedMotion,
} from "motion/react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  type HTMLAttributes,
  type ReactNode,
} from "react";

export type SizePresets =
  | "reset"
  | "empty"
  | "default"
  | "compact"
  | "compactLong"
  | "large"
  | "long"
  | "medium"
  | "tall"
  | "ultra";

type Preset = { width: number; height: number; aspectRatio: number; borderRadius: number };

const PRESETS: Record<SizePresets, Preset> = {
  reset: { width: 150, height: 40, aspectRatio: 1, borderRadius: 20 },
  empty: { width: 0, height: 0, aspectRatio: 0, borderRadius: 0 },
  default: { width: 150, height: 40, aspectRatio: 1, borderRadius: 20 },
  compact: { width: 235, height: 40, aspectRatio: 1, borderRadius: 20 },
  compactLong: { width: 300, height: 40, aspectRatio: 1, borderRadius: 20 },
  large: { width: 350, height: 72, aspectRatio: 1, borderRadius: 26 },
  long: { width: 420, height: 48, aspectRatio: 1, borderRadius: 24 },
  medium: { width: 380, height: 210, aspectRatio: 1, borderRadius: 26 },
  tall: { width: 350, height: 260, aspectRatio: 1, borderRadius: 26 },
  ultra: { width: 460, height: 400, aspectRatio: 1, borderRadius: 30 },
};

type State = {
  size: SizePresets;
  previousSize: SizePresets | undefined;
  isAnimating: boolean;
};

type Action = { type: "SET_SIZE"; size: SizePresets } | { type: "SETTLED" };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "SET_SIZE":
      if (action.size === state.size) return state;
      return { size: action.size, previousSize: state.size, isAnimating: true };
    case "SETTLED":
      return { ...state, isAnimating: false };
  }
}

type Context = {
  state: State;
  setSize: (size: SizePresets) => void;
  preset: Preset;
};

const DynamicIslandContext = createContext<Context | null>(null);

export function useDynamicIslandSize(): Context {
  const context = useContext(DynamicIslandContext);
  if (!context) {
    throw new Error(
      "useDynamicIslandSize must be used inside a <DynamicIslandProvider>",
    );
  }
  return context;
}

export function DynamicIslandProvider({
  children,
  initialSize = "default",
}: {
  children: ReactNode;
  initialSize?: SizePresets;
}) {
  const [state, dispatch] = useReducer(reducer, {
    size: initialSize,
    previousSize: undefined,
    isAnimating: false,
  });

  const setSize = useCallback((size: SizePresets) => {
    dispatch({ type: "SET_SIZE", size });
  }, []);

  const value = useMemo(
    () => ({ state, setSize, preset: PRESETS[state.size] }),
    [state, setSize],
  );

  return (
    <DynamicIslandContext.Provider value={value}>
      {children}
    </DynamicIslandContext.Provider>
  );
}

/**
 * Plays a scripted sequence of sizes.
 *
 * The timers are cleared on unmount and the whole schedule is skipped when the
 * reader has asked for reduced motion - a component whose entire purpose is
 * shape-change has no business ignoring that.
 */
export function useScheduledAnimations(
  schedule: { size: SizePresets; delay: number }[],
) {
  const { setSize } = useDynamicIslandSize();
  const calm = useReducedMotion();
  // Serialised so a caller passing a fresh array literal every render - which
  // the demo does - does not restart the schedule on every render.
  const key = JSON.stringify(schedule);

  useEffect(() => {
    if (calm) return;
    const steps: { size: SizePresets; delay: number }[] = JSON.parse(key);
    const timers = steps.map((step) =>
      setTimeout(() => setSize(step.size), step.delay),
    );
    return () => timers.forEach(clearTimeout);
  }, [key, setSize, calm]);
}

export function DynamicIsland({
  children,
  id = "dynamic-island",
  className = "",
}: {
  children: ReactNode;
  id?: string;
  className?: string;
}) {
  const { state, preset, setSize } = useDynamicIslandSize();
  const calm = useReducedMotion();
  void setSize;

  return (
    <MotionConfig
      transition={
        calm
          ? { duration: 0 }
          : { type: "spring", stiffness: 380, damping: 34, mass: 0.9 }
      }
    >
      <div className={`flex justify-center ${className}`}>
        <motion.div
          id={id}
          layout
          // The radius animates with the box. Without it the corners snap at
          // the start of every transition and the illusion of one object
          // changing shape is gone.
          animate={{
            width: preset.width,
            height: preset.height,
            borderRadius: preset.borderRadius,
          }}
          style={{
            background: "var(--text)",
            color: "var(--accent-ink)",
            overflow: "hidden",
            boxShadow: "var(--shadow-lg)",
          }}
        >
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div
              key={state.size}
              initial={{ opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.94 }}
              transition={calm ? { duration: 0 } : { duration: 0.22 }}
              className="h-full w-full"
              style={{ willChange: "opacity, transform" }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </motion.div>
      </div>
    </MotionConfig>
  );
}

/*
 * The content slots.
 *
 * Each forwards every remaining DOM prop - style, aria attributes, handlers -
 * rather than accepting only `className`. A wrapper that silently drops props
 * is the kind of component people fight for ten minutes before reading its
 * source, and here it would have blocked inline colour on the island's own
 * text.
 */
export function DynamicContainer({
  children,
  className = "",
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`h-full w-full ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function DynamicDiv({
  children,
  className = "",
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={className} {...rest}>
      {children}
    </div>
  );
}

export function DynamicTitle({
  children,
  className = "",
  ...rest
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={`m-0 ${className}`} {...rest}>
      {children}
    </h3>
  );
}

export function DynamicDescription({
  children,
  className = "",
  ...rest
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={`m-0 ${className}`} {...rest}>
      {children}
    </p>
  );
}
