import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Smart Desk Assistant",
    short_name: "Desk",
    description: "Control your desk: notes, reminders, calendar, and device status.",
    start_url: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0a0a0a",
    theme_color: "#0a0a0a",
    // Icons are added once the logo is ready. Without a 192 and 512 icon Chrome
    // will not offer the install prompt, though the app can still be installed
    // from the browser menu.
  };
}
