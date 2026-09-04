import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nyaya — evidence-grounded requirements engineering",
  description:
    "Agentic requirements engineering, compliance mapping and SDLC selection for regulated financial software. Every citation is checked, not trusted.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="aurora" aria-hidden />
        <div className="grain" aria-hidden />
        {children}
      </body>
    </html>
  );
}
