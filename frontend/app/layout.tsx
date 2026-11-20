import type { Metadata } from "next";
import "../styles/globals.css";
import { AuthProvider } from "@/lib/auth";
import { QueryProvider } from "@/lib/query";
import { ToastProvider } from "@/components/ui";
import OfflineToast from "@/components/feature/OfflineToast";

export const metadata: Metadata = {
  title: "GigPilot — AI co-pilot for freelancers",
  description: "Discover jobs, score fit, draft proposals in your voice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <QueryProvider>
          <AuthProvider>
            <ToastProvider>
              {children}
              <OfflineToast />
            </ToastProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
