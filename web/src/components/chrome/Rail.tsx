"use client";

/**
 * Persistent navigation.
 *
 * The whole point of splitting the application into modules is that a reader
 * can see where they are and what else exists without scrolling to find out.
 * The current module is marked by an indicator that *travels* between items
 * rather than by two separate highlights cross-fading, because a shared element
 * tells you where you came from as well as where you are.
 *
 * On narrow screens it becomes a bottom bar. Not a compromise - a 236px rail on
 * a phone would take a third of the width - but it does mean the questions are
 * dropped there, so the icon and the name have to carry the meaning alone.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import {
  Activity,
  GitBranch,
  Library,
  ListChecks,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { api, type Health } from "@/lib/api";
import { MODULES, type IconName } from "./modules";

/**
 * Reachability, stated rather than implied.
 *
 * A run without the reranker or the entailment model still returns answers;
 * they are just weaker answers. Leaving a reader to infer that from worse
 * results is not acceptable in a tool whose output is meant to be evidence, so
 * the degraded state is shown where they can always see it - and in the rail,
 * which is the one surface that is always in the same place and never sits on
 * top of anything.
 */
function Reachability({ compact = false }: { compact?: boolean }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => !cancelled && setHealth(h))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  const down = Object.entries(health?.models ?? {}).filter(([, up]) => !up);
  const healthy = health != null && health.database && down.length === 0;
  const tone = failed
    ? "var(--gap)"
    : !health
      ? "var(--text-tertiary)"
      : healthy
        ? "var(--confirmed)"
        : "var(--review)";

  const label = failed
    ? "API unreachable"
    : !health
      ? "checking…"
      : healthy
        ? `${health.corpus_clauses} clauses indexed`
        : `degraded — ${down.map(([n]) => n).join(", ") || "database"} unavailable`;

  return (
    <div
      className="flex items-start gap-2.5 px-3 py-3"
      // Collapsed, the dot alone carries the state, so the full sentence moves
      // to the tooltip rather than disappearing.
      title={compact ? label : undefined}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: tone,
          flexShrink: 0,
          marginTop: 6,
        }}
      />
      {!compact && (
        <span className="caption" style={{ lineHeight: 1.4 }}>
          {label}
        </span>
      )}
    </div>
  );
}

const ICONS: Record<IconName, LucideIcon> = {
  library: Library,
  search: Search,
  "list-checks": ListChecks,
  "shield-check": ShieldCheck,
  "git-branch": GitBranch,
  activity: Activity,
};

const indicator = { type: "spring" as const, stiffness: 420, damping: 36 };

/**
 * Collapsed state, remembered.
 *
 * Kept in localStorage rather than in memory: someone who collapses the rail
 * has expressed a preference about how much of the window they want the
 * navigation to take, and re-expanding it on every route change would override
 * that preference every time. Reads are guarded because storage throws outright
 * in some contexts rather than returning null.
 */
const STORAGE_KEY = "nyaya:rail-collapsed";

const listeners = new Set<() => void>();

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    // Storage can throw outright rather than return null - a private window,
    // or a browser set to block site data. Expanded is the safe default.
    return false;
  }
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  // `storage` fires in *other* tabs, so this also keeps two open windows in
  // step. Same-tab writes notify directly.
  window.addEventListener("storage", notify);
  return () => {
    listeners.delete(notify);
    window.removeEventListener("storage", notify);
  };
}

function useCollapsed(): [boolean, (next: boolean) => void] {
  // Read through `useSyncExternalStore` rather than hydrating state from an
  // effect. The effect version is a cascading render, and it also samples once
  // at mount - a second tab toggling the rail would never be noticed.
  const collapsed = useSyncExternalStore(subscribe, readCollapsed, () => false);

  const update = useCallback((next: boolean) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      // Preference is not persisted; the toggle below still takes effect.
    }
    listeners.forEach((notify) => notify());
  }, []);

  // Published as a custom property rather than threaded through context.
  // Content has to shift when the rail does, and every page would otherwise
  // need to subscribe to a piece of navigation state it has no other use for.
  useEffect(() => {
    document.documentElement.style.setProperty(
      "--rail-width",
      collapsed ? "68px" : "236px",
    );
  }, [collapsed]);

  return [collapsed, update];
}

export default function Rail() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useCollapsed();
  const width = collapsed ? 68 : 236;

  return (
    <>
      {/* Wide: a vertical rail. */}
      <motion.nav
        aria-label="Modules"
        className="fixed inset-y-0 left-0 hidden flex-col md:flex"
        animate={{ width }}
        transition={{ type: "spring", stiffness: 420, damping: 38 }}
        style={{
          zIndex: "var(--z-chrome)" as unknown as number,
          background: "var(--bg-subtle)",
          borderRight: "1px solid var(--hairline)",
        }}
      >
        {/*
          Collapsed, the mark and the toggle stack; expanded, they sit on one
          row. This is a layout problem, not a glyph problem, and it took two
          attempts to see that: at 68px wide with 16px of padding either side
          there are 36px of content, the toggle takes 25 of them, and flex left
          the wordmark about three pixels. Whatever character went in there was
          going to render as a sliver.
        */}
        <div
          className={`flex px-4 pb-6 pt-6 ${
            collapsed
              ? "flex-col items-center gap-4"
              : "flex-row items-start justify-between gap-2"
          }`}
        >
          <Link
            href="/"
            aria-label="Nyaya — home"
            className={collapsed ? "block" : "block min-w-0 overflow-hidden"}
            style={{ textDecoration: "none", color: "inherit" }}
          >
            {/*
              Collapsed, the wordmark is a mark rather than a truncation.

              It used to render "न्या" - the first two syllables of न्याय with
              the third cut off - which is not an abbreviation, it is a word
              with its end missing, and it looked like a rendering fault. The
              full name is also still laid out underneath at 236px while the
              rail is 68px wide, so any of it that escaped `overflow: hidden`
              showed as a sliver of clipped text.

              The replacement has to be a complete letter. "न्" carries a
              virama, which makes it a half-form that does not stand on its own
              - it renders as a bare vertical stroke and reads as another
              artefact. "न" is the whole first letter of न्याय and is legible
              alone.
            */}
            <div
              style={{
                fontSize: collapsed ? "1.375rem" : "1.25rem",
                fontWeight: 600,
                letterSpacing: "-0.03em",
                lineHeight: 1,
                whiteSpace: "nowrap",
              }}
            >
              {collapsed ? "न" : "Nyaya"}
            </div>
            <AnimatePresence initial={false}>
              {!collapsed && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="caption mt-1.5 whitespace-nowrap"
                  style={{ color: "var(--text-tertiary)" }}
                >
                  न्याय · evidence for a claim
                </motion.div>
              )}
            </AnimatePresence>
          </Link>

          <button
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand navigation" : "Collapse navigation"}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-tertiary)",
              cursor: "pointer",
              padding: 4,
              lineHeight: 0,
              flexShrink: 0,
            }}
          >
            {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-0.5 px-3">
          {MODULES.map((module) => {
            const active = pathname === module.href;
            const Icon = ICONS[module.icon];
            return (
              <Link
                key={module.href}
                href={module.href}
                aria-current={active ? "page" : undefined}
                // The name is still rendered when collapsed, clipped rather
                // than removed, so the accessible name of every link survives
                // the collapse. Removing the text would leave six links that
                // announce as nothing but their icon.
                title={collapsed ? `${module.name} — ${module.question}` : undefined}
                className="relative flex items-center gap-3 overflow-hidden rounded-[10px] px-3 py-2.5"
                style={{
                  textDecoration: "none",
                  color: active ? "var(--text)" : "var(--text-secondary)",
                }}
              >
                {active && (
                  <motion.span
                    layoutId="rail-indicator"
                    transition={indicator}
                    style={{
                      position: "absolute",
                      inset: 0,
                      borderRadius: 10,
                      background: "var(--surface)",
                      border: "1px solid var(--hairline)",
                      boxShadow: "var(--shadow-sm)",
                    }}
                  />
                )}
                <Icon
                  size={17}
                  strokeWidth={active ? 2 : 1.7}
                  className="relative shrink-0"
                  style={{ opacity: active ? 1 : 0.7 }}
                />
                <span
                  className="relative whitespace-nowrap"
                  style={{
                    fontSize: "0.875rem",
                    fontWeight: active ? 550 : 450,
                    opacity: collapsed ? 0 : 1,
                    transition: "opacity 0.16s",
                  }}
                >
                  {module.name}
                </span>
              </Link>
            );
          })}
        </div>

        <div className="mx-3 mb-3" style={{ borderTop: "1px solid var(--hairline)" }}>
          <Reachability compact={collapsed} />
        </div>
      </motion.nav>

      {/* Narrow: a bottom bar. */}
      <nav
        aria-label="Modules"
        className="fixed inset-x-0 bottom-0 flex justify-around md:hidden"
        style={{
          zIndex: "var(--z-chrome)" as unknown as number,
          background: "var(--bg-subtle)",
          borderTop: "1px solid var(--hairline)",
          paddingBottom: "env(safe-area-inset-bottom)",
        }}
      >
        {MODULES.map((module) => {
          const active = pathname === module.href;
          const Icon = ICONS[module.icon];
          return (
            <Link
              key={module.href}
              href={module.href}
              aria-current={active ? "page" : undefined}
              className="flex flex-1 flex-col items-center gap-1 py-2.5"
              style={{
                textDecoration: "none",
                color: active ? "var(--text)" : "var(--text-tertiary)",
              }}
            >
              <Icon size={18} strokeWidth={active ? 2 : 1.7} />
              <span style={{ fontSize: "0.625rem", fontWeight: active ? 550 : 450 }}>
                {module.name}
              </span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
