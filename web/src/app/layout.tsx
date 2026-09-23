import type { Metadata } from "next";
import Cursor from "@/components/chrome/Cursor";
import Rail from "@/components/chrome/Rail";
import { JobsProvider } from "@/components/chrome/Jobs";
import { StatusIsland } from "@/components/chrome/StatusIsland";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Nyaya — evidence-grounded requirements engineering",
    template: "%s · Nyaya",
  },
  description:
    "Agentic requirements engineering, compliance mapping and SDLC selection for regulated financial software. Every citation is checked, not trusted.",
};

/**
 * The application shell.
 *
 * The rail, the pointer and the status island live here rather than in each
 * page, so navigating between modules preserves them: in the App Router a
 * layout is not re-rendered on navigation, which is what lets the rail's
 * selection indicator animate from the module you left to the one you arrived
 * at, and lets the island keep reporting a job across a route change.
 */
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      {/*
        Browser extensions write attributes onto <body> before React hydrates -
        Grammarly adds `data-gr-ext-installed` and `data-new-gr-c-s-check-loaded`,
        password managers and dark-mode extensions do the same. The server cannot
        know about them, so React reports a hydration mismatch it can do nothing
        about, on every page load, for a difference that affects nothing.

        Suppressed here and only here. This is not a blanket escape hatch: it
        applies to this element's own attributes and does not extend to its
        children, so a genuine mismatch anywhere inside the application is still
        reported. Putting it on a component that renders real content would hide
        exactly the bugs this warning exists to catch.
      */}
      <body suppressHydrationWarning>
        {/*
          Jobs outside the island, because the island is one of two readers of
          the same record and the pages are the other. A long extraction
          therefore survives navigation: the request is owned here, and
          returning to a module restores whatever it had.
        */}
        <JobsProvider>
          <Rail />
          <Cursor />
          {children}
          <StatusIsland />
        </JobsProvider>
      </body>
    </html>
  );
}
