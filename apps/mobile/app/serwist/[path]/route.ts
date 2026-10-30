import { spawnSync } from "node:child_process";

import { createSerwistRoute } from "@serwist/turbopack";

// A fresh revision per commit, so a deployed update replaces the precache.
const git = spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf-8" });
const revision = git.stdout?.trim() || crypto.randomUUID();

export const { dynamic, dynamicParams, revalidate, generateStaticParams, GET } = createSerwistRoute(
  {
    additionalPrecacheEntries: [{ url: "/~offline", revision }],
    swSrc: "app/sw.ts",
    // esbuild-wasm is broken on Windows; use the native binary.
    useNativeEsbuild: true,
  },
);
