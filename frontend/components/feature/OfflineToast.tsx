"use client";
import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

export default function OfflineToast() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => setOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      className="fixed bottom-4 left-4 z-50 flex items-center gap-2 px-4 py-3 rounded-md border border-warn/30 bg-warn/10 text-warn text-sm shadow-e2"
    >
      <WifiOff className="h-4 w-4 shrink-0" aria-hidden="true" />
      You&rsquo;re offline — changes aren&rsquo;t saved
    </div>
  );
}
