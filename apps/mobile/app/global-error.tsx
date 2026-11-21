"use client";

/* Replaces the root layout when rendering itself fails, so it cannot rely on
   globals.css. Styles stay inline on purpose. */

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#ffffff",
          color: "#171717",
          fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
        }}
      >
        <div style={{ maxWidth: "22rem", padding: "2rem", textAlign: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1.125rem" }}>That did not work</h2>
          <p style={{ marginTop: "0.75rem", fontSize: "0.875rem", color: "#52525b" }}>
            Something went wrong.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: "1rem",
              padding: "0.5rem 1.25rem",
              borderRadius: "9999px",
              border: "none",
              background: "#171717",
              color: "#ffffff",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
