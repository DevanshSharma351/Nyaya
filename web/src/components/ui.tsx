"use client";

/**
 * Shared surfaces.
 *
 * The rule these follow: ambient layers may move, data layers may not. A panel
 * can rise into place, but the number inside it does not animate, pulse or
 * shimmer. In a compliance tool a moving figure reads as a moving target.
 */

import { motion } from "framer-motion";
import type { ReactNode } from "react";

export const spring = { type: "spring" as const, stiffness: 260, damping: 26 };

export function Panel({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 26 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ ...spring, delay }}
      className={`glass-raised specular ${className}`}
    >
      {children}
    </motion.section>
  );
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
      <div
        className="mono mb-3 uppercase"
        style={{ color: "var(--accent)", letterSpacing: "0.14em" }}
      >
        {eyebrow}
      </div>
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
          fontSize: "2rem",
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
        border: `1px solid ${tone}44`,
        background: `${tone}12`,
        borderRadius: 7,
        padding: "3px 8px",
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
      whileHover={disabled ? undefined : { scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      transition={spring}
      onClick={onClick}
      disabled={disabled}
      style={{
        background: primary ? "var(--accent)" : "var(--glass-strong)",
        color: primary ? "#fff" : "var(--text)",
        border: primary ? "none" : "1px solid var(--hairline)",
        borderRadius: 12,
        padding: "10px 18px",
        fontSize: "0.9375rem",
        fontWeight: 590,
        letterSpacing: "-0.01em",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.45 : 1,
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
  size = 112,
  tone = "var(--accent)",
  label,
}: {
  value: number;
  size?: number;
  tone?: string;
  label?: string;
}) {
  const stroke = 8;
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
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={tone}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          whileInView={{ strokeDashoffset: circumference * (1 - value) }}
          viewport={{ once: true }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
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
          <div style={{ fontSize: "1.35rem", fontWeight: 600, letterSpacing: "-0.02em" }}>
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
    <div
      className="body"
      style={{ color: "var(--text-tertiary)", padding: "28px 4px" }}
    >
      {children}
    </div>
  );
}

/** Distinguishes "nothing found" from "we could not check". */
export function Failure({ message }: { message: string }) {
  return (
    <div
      className="body"
      style={{
        color: "var(--gap)",
        border: "1px solid var(--gap)44",
        background: "var(--gap)10",
        borderRadius: 12,
        padding: "12px 14px",
      }}
    >
      Could not complete the check — {message}
    </div>
  );
}
