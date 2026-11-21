"use client";

import { useEffect, useState } from "react";

export function OfflineBanner() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      className="bg-amber-500/15 px-4 py-2 text-center text-xs text-amber-900 dark:text-amber-200"
    >
      Offline. Cached screens still open; notes, reminders, and calendar need the server.
    </div>
  );
}
