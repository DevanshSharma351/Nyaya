"use client";

/**
 * The frame every module page sits in.
 *
 * It exists so a module file contains only that module's substance. Header,
 * scroll indicator, spacing, and the link on to the next module are the same
 * everywhere and are decided once here - which is also what stops six pages
 * from slowly diverging into six different layouts.
 */

import Link from "next/link";
import dynamic from "next/dynamic";
import { ChevronRight } from "lucide-react";
import { motion, useScroll, useSpring } from "motion/react";
import type { ReactNode } from "react";
import { neighbours } from "./modules";

/**
 * The ambient field, on every module page.
 *
 * Mounted here rather than in the root layout so the landing page is excluded:
 * it assembles its own copy of this lattice as its hero, and running both would
 * put two fields on top of each other. Loaded lazily and after the content,
 * because it is decoration and must never be on the critical path for
 * something a reader is trying to act on.
 */
const AmbientLayer = dynamic(() => import("@/components/scenes/AmbientLayer"), {
  ssr: false,
});

export function ModuleShell({
  eyebrow,
  title,
  lede,
  pathname,
  scene,
  sceneCaption,
  children,
}: {
  eyebrow: string;
  title: string;
  lede: string;
  pathname: string;
  /**
   * The module's scene, mounted in a framed panel below the header.
   *
   * It is a figure, not a backdrop: it gets a border, its own ground and a
   * caption, and the reader can look at it directly instead of squinting past
   * the text sitting on top of it.
   */
  scene?: ReactNode;
  /** What the scene is showing. A figure without one is decoration. */
  sceneCaption?: ReactNode;
  children: ReactNode;
}) {
  const { scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, {
    stiffness: 180,
    damping: 30,
    restDelta: 0.001,
  });
  const { previous, next } = neighbours(pathname);

  return (
    <>
      <AmbientLayer />

      {/* Reading position. A hairline rather than a bar: it answers "how much
          is left" without asking to be looked at. */}
      <motion.div
        aria-hidden
        style={{
          scaleX: progress,
          transformOrigin: "0% 50%",
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: "var(--text)",
          zIndex: "var(--z-chrome)" as unknown as number,
        }}
      />

      <main className="content-layer with-rail pb-36">
        <div className="mx-auto max-w-5xl px-6 lg:px-12">
          {/*
            Entrances are CSS, not JavaScript.

            They were motion components that animated from `opacity: 0`, and
            that turned out to make content visibility depend on an animation
            actually running. It does not always: motion suspends while the
            document reports itself hidden, so a page opened in a background
            tab - or rendered by any tool that reports hidden, which is how this
            was found - sat at zero opacity with a fully populated DOM behind
            it. A reveal effect is a nice thing to have; content that can fail
            to appear is a defect, and the two are not worth trading.

            CSS keyframes have neither problem. They run without hydration and
            they end in the final state regardless of when they ran.
          */}
          <header className="rise pt-16 pb-10 md:pt-24">
            <div className="eyebrow mb-4">{eyebrow}</div>
            <h1 className="title m-0 max-w-3xl">{title}</h1>
            <p className="body mt-4 max-w-2xl" style={{ color: "var(--text-secondary)" }}>
              {lede}
            </p>
          </header>

          {scene && (
            <section className="rise mb-8" style={{ animationDelay: "0.06s" }}>
              <div className="scene-panel">{scene}</div>
              {sceneCaption && <p className="caption mt-2.5 max-w-2xl">{sceneCaption}</p>}
            </section>
          )}

          {children}

          <nav className="mt-20 flex flex-wrap items-stretch justify-between gap-4">
            {previous ? (
              <motion.div
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.99 }}
                transition={{ type: "spring", stiffness: 480, damping: 32 }}
                style={{ flex: 1, minWidth: 220 }}
              >
                <Link
                  href={previous.href}
                  className="glass block h-full p-5"
                  style={{ textDecoration: "none", color: "inherit" }}
                >
                  <div className="caption">← previous</div>
                  <div className="headline mt-1">{previous.name}</div>
                  <div className="caption mt-1">{previous.question}</div>
                </Link>
              </motion.div>
            ) : (
              <span style={{ flex: 1, minWidth: 220 }} />
            )}
            {next && (
              <motion.div
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.99 }}
                transition={{ type: "spring", stiffness: 480, damping: 32 }}
                style={{ flex: 1, minWidth: 220 }}
              >
                <Link
                  href={next.href}
                  className="glass block h-full p-5 text-right"
                  style={{ textDecoration: "none", color: "inherit" }}
                >
                  <div className="caption">next →</div>
                  <div className="headline mt-1">{next.name}</div>
                  <div className="caption mt-1">{next.question}</div>
                </Link>
              </motion.div>
            )}
          </nav>
        </div>
      </main>
    </>
  );
}

/**
 * A named division inside a module.
 *
 * Rises once when it first enters the viewport and then stays put. Content
 * that re-animates every time it is scrolled past makes a page feel unstable
 * to anyone reading it twice.
 */
export function Block({
  title,
  aside,
  children,
  className = "",
  delay = 0,
}: {
  title?: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Seconds to stagger this block behind the one above it. */
  delay?: number;
}) {
  return (
    <section
      className={`rise mb-6 ${className}`}
      style={{ animationDelay: `${delay}s` }}
    >
      {(title || aside) && (
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
          {title && <h2 className="headline m-0">{title}</h2>}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

/**
 * Reasoning that a reader may want and should not have to read.
 *
 * The measured caveats behind these numbers matter - they are the difference
 * between a figure and a claim - but printing every one of them beside the
 * figure is how a compliance interface becomes unreadable. Disclosed, not
 * hidden, and never opened by default.
 */
export function Rationale({ children }: { children: ReactNode }) {
  return (
    <details className="mt-4 group">
      {/* The default marker is hidden, so the affordance has to be rebuilt:
          without a chevron and a border this read as a stray line of body text
          and nobody would have clicked it. */}
      <summary
        className="caption inline-flex items-center gap-2"
        style={{
          cursor: "pointer",
          listStyle: "none",
          color: "var(--text)",
          border: "1px solid var(--hairline)",
          borderRadius: 999,
          padding: "6px 13px",
          userSelect: "none",
        }}
      >
        <ChevronRight
          size={13}
          className="transition-transform duration-200 group-open:rotate-90"
        />
        why this is trustworthy, and where it is not
      </summary>
      <div
        className="caption mt-3"
        style={{
          borderLeft: "2px solid var(--hairline)",
          paddingLeft: 14,
          lineHeight: 1.6,
        }}
      >
        {children}
      </div>
    </details>
  );
}
