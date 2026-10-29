/**
 * Environment access for the PWA. Every `NEXT_PUBLIC_` value is inlined at build
 * time, so it must never hold a secret.
 *
 * An empty value falls back to the local backend: `??` alone would keep the empty
 * string and send every request to the Next server instead of the API.
 */
const configured = process.env.NEXT_PUBLIC_API_URL?.trim();

export const API_URL = (configured || "http://localhost:8000").replace(/\/+$/, "");
