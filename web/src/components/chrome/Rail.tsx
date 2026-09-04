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
import { motion } from "motion/react";
import {
  Activity,
  GitBranch,
  Library,
  ListChecks,
  Search,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
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
function Reachability() {
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
    <div className="flex items-start gap-2.5 px-3 py-3">
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
      <span className="caption" style={{ lineHeight: 1.4 }}>
        {label}
      </span>
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

export default function Rail() {
  const pathname = usePathname();

  return (
    <>
      {/* Wide: a vertical rail. */}
      <nav
        aria-label="Modules"
        className="fixed inset-y-0 left-0 hidden w-[236px] flex-col md:flex"
        style={{
          zIndex: "var(--z-chrome)" as unknown as number,
          background: "var(--bg-subtle)",
          borderRight: "1px solid var(--hairline)",
        }}
      >
        <Link
          href="/"
          className="block px-5 pb-7 pt-7"
          style={{ textDecoration: "none", color: "inherit" }}
        >
          <div
            style={{
              fontSize: "1.25rem",
              fontWeight: 600,
              letterSpacing: "-0.03em",
              lineHeight: 1,
            }}
          >
            Nyaya
          </div>
          <div className="caption mt-1.5" style={{ color: "var(--text-tertiary)" }}>
            न्याय · evidence for a claim
          </div>
        </Link>

        <div className="flex flex-1 flex-col gap-0.5 px-3">
          {MODULES.map((module) => {
            const active = pathname === module.href;
            const Icon = ICONS[module.icon];
            return (
              <Link
                key={module.href}
                href={module.href}
                aria-current={active ? "page" : undefined}
                className="relative flex items-center gap-3 rounded-[10px] px-3 py-2.5"
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
                  className="relative"
                  style={{ fontSize: "0.875rem", fontWeight: active ? 550 : 450 }}
                >
                  {module.name}
                </span>
              </Link>
            );
          })}
        </div>

        <div className="mx-3 mb-3" style={{ borderTop: "1px solid var(--hairline)" }}>
          <Reachability />
        </div>
      </nav>

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
