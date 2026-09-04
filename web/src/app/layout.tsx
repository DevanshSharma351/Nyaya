import type { Metadata } from "next";
import Cursor from "@/components/chrome/Cursor";
import Rail from "@/components/chrome/Rail";
import { StatusIslandProvider } from "@/components/chrome/StatusIsland";
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
    <html lang="en">
      <body>
        <StatusIslandProvider>
          <Rail />
          <Cursor />
          {children}
        </StatusIslandProvider>
      </body>
    </html>
  );
}
