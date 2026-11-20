import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "GigPilot",
  description: "AI co-pilot for freelancers: discover jobs, score fit, draft proposals.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
