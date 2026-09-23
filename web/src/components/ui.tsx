"use client";

/**
 * Shared surfaces.
 *
 * The rule these follow: ambient layers may move, data layers may not. A panel
 * can rise into place, but the number inside it does not animate, pulse or
 * shimmer. In a compliance tool a moving figure reads as a moving target.
 *
 * The exception is direct manipulation. A control the reader is physically
 * pressing should answer immediately - that is feedback about their own action,
 * not decoration applied to a finding.
 */

import { motion } from "motion/react";
import type { ReactNode } from "react";

export const spring = { type: "spring" as const, stiffness: 260, damping: 26 };
export const press = { type: "spring" as const, stiffness: 520, damping: 30 };

/**
 * Mixes a token colour with the page ground.
 *
 * This replaces string concatenation of the form `${tone}44`, which silently
 * produced invalid CSS whenever `tone` was a custom property: `var(--gap)44` is
 * not a colour, so the browser dropped the whole declaration and the tinted
 * borders and backgrounds it was meant to create never rendered at all. It
 * looked deliberate, because the text colour on its own still worked.
 */
function tint(tone: string, percent: number): string {
  return `color-mix(in srgb, ${tone} ${percent}%, transparent)`;
}

export function SectionHeading({
  eyebrow,
  title,
  lede,
}: {
  eyebrow: string;
  title: string;
  lede?: string;
}) {
  return (
    <header className="mb-8 max-w-2xl">
      <div className="eyebrow mb-3">{eyebrow}</div>
      <h2 className="title m-0">{title}</h2>
      {lede && (
        <p className="body mt-3" style={{ color: "var(--text-secondary)" }}>
          {lede}
        </p>
      )}
    </header>
  );
}

/** A metric. Deliberately static: the value is the point, not its arrival. */
export function Stat({
  value,
  label,
  tone = "var(--text)",
}: {
  value: string;
  label: string;
  tone?: string;
}) {
  return (
    <div>
      <div
        style={{
          color: tone,
          fontSize: "1.875rem",
          fontWeight: 600,
          letterSpacing: "-0.03em",
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      <div className="caption mt-1">{label}</div>
    </div>
  );
}

export function Badge({
  children,
  tone = "var(--text-secondary)",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <span
      className="mono"
      style={{
        color: tone,
        border: `1px solid ${tint(tone, 22)}`,
        background: tint(tone, 7),
        borderRadius: 6,
        padding: "2px 7px",
        fontSize: "0.75rem",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "quiet";
}) {
  const primary = variant === "primary";
  return (
    <motion.button
      // Scale down on press rather than up on hover. Pressing is the moment the
      // reader is asking whether the control registered, and a control that
      // yields under the pointer answers that faster than a colour change.
      whileHover={disabled ? undefined : { y: -1 }}
      whileTap={disabled ? undefined : { scale: 0.97, y: 0 }}
      transition={press}
      onClick={onClick}
      disabled={disabled}
      style={{
        background: primary ? "var(--accent)" : "var(--surface)",
        color: primary ? "var(--accent-ink)" : "var(--text)",
        border: primary ? "1px solid var(--accent)" : "1px solid var(--hairline)",
        borderRadius: 10,
        padding: "9px 16px",
        fontSize: "0.875rem",
        fontWeight: 550,
        letterSpacing: "-0.01em",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.4 : 1,
        boxShadow: primary ? "var(--shadow-sm)" : "none",
      }}
    >
      {children}
    </motion.button>
  );
}

/**
 * A progress ring.
 *
 * Draws to its value once and stops. A gauge that sweeps on every render makes
 * a reader wait to learn a number they are trying to act on.
 */
export function Ring({
  value,
  size = 96,
  tone = "var(--accent)",
  label,
}: {
  value: number;
  size?: number;
  tone?: string;
  label?: string;
}) {
  const stroke = 7;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--bg-inset)"
          strokeWidth={stroke}
        />
        {/*
          Drawn at its value, with a CSS transition for later changes.

          It used to sweep from empty on entering the viewport, which gated the
          figure on an animation running - and when the document reports itself
          hidden, it does not run, leaving an empty ring beside a real number.
          It also contradicted the rule the rest of this file follows: data does
          not animate. A reader should not have to wait to learn a coverage
          ratio they are trying to act on.
        */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={tone}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - value)}
          style={{ transition: "stroke-dashoffset 0.7s cubic-bezier(0.16,1,0.3,1)" }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "grid",
          placeItems: "center",
          textAlign: "center",
        }}
      >
        <div>
          <div style={{ fontSize: "1.125rem", fontWeight: 600, letterSpacing: "-0.02em" }}>
            {Math.round(value * 100)}%
          </div>
          {label && <div className="caption">{label}</div>}
        </div>
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="body" style={{ color: "var(--text-tertiary)", padding: "24px 4px" }}>
      {children}
    </div>
  );
}

/**
 * Distinguishes "nothing found" from "we could not check".
 *
 * And, within the second, distinguishes a backend that is not running from one
 * that answered badly. The browser reports a refused connection, a DNS failure
 * and a rejected CORS origin all as "Failed to fetch"; printed verbatim on six
 * modules at once it reads as the application being broken, when what is
 * actually true is that nobody started the API. Saying so, with the command
 * that starts it, turns a dead end into a next step.
 */
export function Failure({ message }: { message: string }) {
  const unreachable = /failed to fetch|could not reach the api|networkerror|load failed/i.test(
    message,
  );
  // A slow local model and a stopped backend look identical from a spinner,
  // and the remedies share nothing.
  const timedOut = /took too long|timed out|model_timeout|504/i.test(message);

  return (
    <div
      className="body"
      style={{
        color: unreachable || timedOut ? "var(--text)" : "var(--gap)",
        border: `1px solid ${tint(unreachable || timedOut ? "var(--review)" : "var(--gap)", 30)}`,
        background: tint(unreachable || timedOut ? "var(--review)" : "var(--gap)", 5),
        borderRadius: 12,
        padding: "14px 16px",
      }}
    >
      {timedOut ? (
        <>
          <div style={{ fontWeight: 550 }}>The model ran out of time.</div>
          <p className="caption mt-1.5 mb-0" style={{ maxWidth: 560 }}>
            Nothing is broken. Extraction runs an 8B model on this machine, and a
            long brief makes it slower — a few hundred words can take two to
            three minutes. Try a shorter brief, or raise{" "}
            <span className="mono" style={{ color: "var(--text)" }}>
              NYAYA_OLLAMA_TIMEOUT_SECONDS
            </span>{" "}
            and run it again.
          </p>
        </>
      ) : unreachable ? (
        <>
          <div style={{ fontWeight: 550 }}>The API is not responding.</div>
          <p className="caption mt-1.5 mb-0" style={{ maxWidth: 560 }}>
            Nothing is wrong with this page — it has no data because the backend
            could not be reached. Start it with{" "}
            <span className="mono" style={{ color: "var(--text)" }}>
              make api
            </span>
            , or run{" "}
            <span className="mono" style={{ color: "var(--text)" }}>
              make doctor
            </span>{" "}
            to see which of Postgres, Ollama and the API is down.
          </p>
        </>
      ) : (
        <>Could not complete the check — {message}</>
      )}
    </div>
  );
}
