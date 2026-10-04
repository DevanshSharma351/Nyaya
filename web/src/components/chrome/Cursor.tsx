"use client";

/**
 * A quiet pointer.
 *
 * The previous version carried a coloured ring, a blend mode and a text label,
 * and it was the loudest thing on the screen - a pointer that announces itself
 * is competing with the content it is pointing at. This one does one thing: a
 * small neutral disc that trails slightly behind the real position and settles
 * over whatever it is on top of.
 *
 * The trailing is the whole effect. Lag gives the pointer apparent mass, which
 * is what makes it read as a physical object rather than a second mouse cursor,
 * and it costs nothing in legibility because the true position is still marked
 * exactly by the dot at its centre.
 *
 * Three rules keep this from becoming an accessibility problem, which is the
 * usual fate of a custom cursor:
 *
 *  - The system cursor is only hidden once this component has mounted and
 *    positioned itself. If the script never runs, the real pointer is there.
 *  - It is never enabled on coarse pointers, where there is no cursor to
 *    replace and a trailing disc is pure noise.
 *  - It is disabled under prefers-reduced-motion, where a lagging element is
 *    exactly the kind of motion being asked about.
 */

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

type Intent = "default" | "interactive" | "text";

/** Diameter, and how much of the ink colour the disc carries. */
const RING: Record<Intent, { size: number; alpha: number }> = {
  default: { size: 26, alpha: 0.14 },
  interactive: { size: 40, alpha: 0.22 },
  text: { size: 3, alpha: 0.55 },
};

/**
 * Subscribes to a media query the way React wants external state read.
 *
 * The obvious version - read `matchMedia` in an effect and call setState - is
 * both a cascading render and wrong: it samples once at mount and never notices
 * a change. Someone who turns on Reduce Motion keeps whatever was true when the
 * page loaded.
 */
function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (notify: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", notify);
      return () => list.removeEventListener("change", notify);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    // On the server there is no pointer and no motion preference. Assuming
    // neither means the custom cursor is never in the server-rendered markup,
    // which is the safe direction: it appears, it never disappears.
    () => false,
  );
}

function intentFor(target: Element | null): Intent {
  if (!target) return "default";
  if (target.closest("input, textarea, [contenteditable='true']")) return "text";
  if (target.closest("a, button, [role='button'], select, summary, label, canvas")) {
    return "interactive";
  }
  return "default";
}

export default function Cursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const discRef = useRef<HTMLDivElement>(null);
  const [intent, setIntent] = useState<Intent>("default");
  const [pressed, setPressed] = useState(false);
  // Until the pointer has actually moved, its position is unknown. Rendering
  // at the viewport centre in the meantime puts a grey disc in the middle of
  // the page that looks like a rendering artefact - which is exactly how it
  // read in the first screenshot.
  const [located, setLocated] = useState(false);

  const precise = useMediaQuery("(pointer: fine)");
  const calm = useMediaQuery("(prefers-reduced-motion: reduce)");
  const enabled = precise && !calm;

  useEffect(() => {
    if (!enabled) return;

    // Positions live in refs and are written straight to the DOM inside the
    // animation frame. Routing 120 pointer events a second through React state
    // would re-render this component for a value that only lands in a
    // transform.
    const target = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const disc = { ...target };
    let frame = 0;
    let shown = false;

    function onMove(event: PointerEvent) {
      target.x = event.clientX;
      target.y = event.clientY;
      const next = intentFor(event.target as Element);
      setIntent((current) => (current === next ? current : next));
      // The system cursor is hidden only now, on first real movement, once
      // there is something to replace it with.
      if (!shown) {
        shown = true;
        setLocated(true);
        document.body.classList.add("has-custom-cursor");
      }
    }

    function tick() {
      disc.x += (target.x - disc.x) * 0.32;
      disc.y += (target.y - disc.y) * 0.32;
      if (dotRef.current) {
        dotRef.current.style.transform = `translate3d(${target.x}px, ${target.y}px, 0) translate(-50%, -50%)`;
      }
      if (discRef.current) {
        discRef.current.style.transform = `translate3d(${disc.x}px, ${disc.y}px, 0) translate(-50%, -50%)`;
      }
      frame = requestAnimationFrame(tick);
    }

    function onDown() {
      setPressed(true);
    }
    function onUp() {
      setPressed(false);
    }
    // Leaving the window must restore the real cursor, or the pointer vanishes
    // over browser chrome.
    function onLeave() {
      document.body.classList.remove("has-custom-cursor");
      setLocated(false);
      shown = false;
    }

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("pointerup", onUp);
    document.addEventListener("pointerleave", onLeave);
    frame = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointerleave", onLeave);
      document.body.classList.remove("has-custom-cursor");
    };
  }, [enabled]);

  if (!enabled || !located) return null;

  const style = RING[intent];
  const size = style.size * (pressed ? 0.85 : 1);
  const isText = intent === "text";
  const base = {
    position: "fixed",
    top: 0,
    left: 0,
    borderRadius: "50%",
    zIndex: "var(--z-cursor)" as unknown as number,
    pointerEvents: "none",
  } as const;

  return (
    <>
      <div
        ref={discRef}
        aria-hidden
        style={{
          ...base,
          width: size,
          height: size,
          background: `rgba(9, 9, 11, ${style.alpha})`,
          opacity: isText ? 0 : 1,
          transition:
            "width 0.22s cubic-bezier(0.16,1,0.3,1), height 0.22s cubic-bezier(0.16,1,0.3,1), background 0.22s, opacity 0.15s ease",
        }}
      />
      <div
        ref={dotRef}
        aria-hidden
        style={{
          ...base,
          width: 4,
          height: 4,
          background: "var(--text)",
          opacity: isText ? 0 : 1,
          transition: "opacity 0.15s ease",
        }}
      />
    </>
  );
}
