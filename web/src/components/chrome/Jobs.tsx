"use client";

/**
 * Long-running work, owned above the page that starts it.
 *
 * Extraction runs on a local model for forty to a hundred seconds, and a reader
 * is entitled to go and read something else while it does. Until now they could
 * not: each module held its own `useState`, React destroyed it on navigation,
 * and coming back showed an empty form while the status island still reported
 * the job running. The work continued - `fetch` is not cancelled by unmounting -
 * and its result was written into state nobody could see.
 *
 * So the job lives here, in the layout, which the App Router does not re-render
 * on navigation. Three consequences, all of them the point:
 *
 *  - The request is issued and awaited by this provider, not by the page. A
 *    page that unmounts mid-flight loses nothing, because it never owned the
 *    promise.
 *  - Returning to a module restores exactly what it had: the input that was
 *    submitted, the running state, or the finished result.
 *  - The island and the page read the same record, so they cannot disagree. The
 *    previous arrangement had two sources of truth and they drifted within
 *    seconds.
 *
 * State is per-session and deliberately not persisted. A result is only
 * meaningful beside the input that produced it, and reviving a half-finished
 * job across a reload - with no request still running behind it - would show a
 * spinner that could never resolve.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type JobState = "idle" | "running" | "done" | "failed";

export type Job<T = unknown> = {
  state: JobState;
  /** What was submitted. Restored into the form when the reader returns. */
  input?: string;
  result?: T;
  error?: string;
  /** Short human label for the island, e.g. "13 requirements". */
  label?: string;
  detail?: string;
  startedAt?: number;
};

type Store = {
  jobs: Record<string, Job>;
  start: (
    key: string,
    input: string,
    work: () => Promise<unknown>,
    describe: (result: never) => { label: string; detail?: string },
    running: { label: string; detail?: string },
  ) => Promise<void>;
  setResult: (
    key: string,
    input: string,
    result: unknown,
    describe: (result: never) => { label: string; detail?: string }
  ) => void;
  clear: (key: string) => void;
};

const JobsContext = createContext<Store | null>(null);

export function useJobs(): Store {
  const store = useContext(JobsContext);
  if (!store) throw new Error("useJobs must be used inside <JobsProvider>");
  return store;
}

/**
 * One module's job.
 *
 * `run` is intentionally not memoised on the caller's behalf: the work closure
 * captures the current input, and memoising it would run yesterday's text.
 */
const IDLE_JOB: Job<unknown> = Object.freeze({ state: "idle" });

export function useJob<T>(key: string) {
  const { jobs, start, setResult: storeSetResult, clear: storeClear } = useJobs();
  const job = (jobs[key] ?? IDLE_JOB) as Job<T>;

  const run = useCallback(
    (
      input: string,
      work: () => Promise<T>,
      describe: (result: T) => { label: string; detail?: string },
      running: { label: string; detail?: string },
    ) =>
      start(
        key,
        input,
        work as () => Promise<unknown>,
        describe as unknown as (result: never) => { label: string; detail?: string },
        running,
      ),
    [key, start],
  );

  const setResult = useCallback(
    (input: string, result: T, describe: (result: T) => { label: string; detail?: string }) => {
      storeSetResult(
        key,
        input,
        result,
        describe as unknown as (result: never) => { label: string; detail?: string }
      );
    },
    [key, storeSetResult]
  );

  const clear = useCallback(() => storeClear(key), [key, storeClear]);

  return { job, run, setResult, clear };
}

export function JobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Record<string, Job>>({});

  // Guards against a second submission while one is in flight. Held in a ref
  // rather than read from state, because two clicks in the same tick would both
  // see the pre-update value.
  const inFlight = useRef<Set<string>>(new Set());

  const start = useCallback<Store["start"]>(
    async (key, input, work, describe, running) => {
      if (inFlight.current.has(key)) return;
      inFlight.current.add(key);

      setJobs((current) => ({
        ...current,
        [key]: {
          state: "running",
          input,
          label: running.label,
          detail: running.detail,
          startedAt: Date.now(),
        },
      }));

      try {
        const result = await work();
        const described = describe(result as never);
        setJobs((current) => ({
          ...current,
          [key]: {
            state: "done",
            input,
            result,
            label: described.label,
            detail: described.detail,
          },
        }));
      } catch (error) {
        const message = (error as Error).message;
        setJobs((current) => ({
          ...current,
          [key]: { state: "failed", input, error: message, label: "Failed", detail: message },
        }));
      } finally {
        inFlight.current.delete(key);
      }
    },
    [],
  );

  const setResult = useCallback<Store["setResult"]>((key, input, result, describe) => {
    const described = describe(result as never);
    setJobs((current) => ({
      ...current,
      [key]: {
        state: "done",
        input,
        result,
        label: described.label,
        detail: described.detail,
        startedAt: Date.now(),
      },
    }));
  }, []);

  const clear = useCallback((key: string) => {
    setJobs((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }, []);

  const value = useMemo(() => ({ jobs, start, setResult, clear }), [jobs, start, setResult, clear]);

  return <JobsContext.Provider value={value}>{children}</JobsContext.Provider>;
}

/**
 * The job the island should be showing.
 *
 * A running job always wins - it is the only state a reader might be waiting
 * on. Otherwise the most recently finished one, so a result is acknowledged
 * even if the reader has already navigated away from the module that produced
 * it.
 */
export function useActiveJob(): [string, Job] | null {
  const { jobs } = useJobs();
  const entries = Object.entries(jobs);
  if (entries.length === 0) return null;

  const running = entries.find(([, job]) => job.state === "running");
  if (running) return running;

  const settled = entries
    .filter(([, job]) => job.state !== "idle")
    .sort(([, a], [, b]) => (b.startedAt ?? 0) - (a.startedAt ?? 0));
  return settled[0] ?? null;
}
