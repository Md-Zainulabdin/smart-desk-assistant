"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import type { SearchResult } from "@desk/shared-types";

import { CardList, CardRow } from "@/components/ui/card-list";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { searchWeb } from "@/lib/api";

export function SearchView() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = query.trim();
    if (!text || searching) return;

    setSearching(true);
    setError(null);
    try {
      const data = await searchWeb(text);
      setResults(data.results);
    } catch (cause) {
      setResults(null);
      setError(cause instanceof Error ? cause.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Search" subtitle="Search the web from your desk" />

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search the web"
          aria-label="Search the web"
          className="surface-field w-full bg-transparent text-[14px] outline-none placeholder:text-zinc-500"
        />
        <button
          type="submit"
          disabled={searching || query.trim().length === 0}
          className="shrink-0 rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background disabled:opacity-50"
        >
          {searching ? "Searching…" : "Search"}
        </button>
      </form>

      {error && <p className="text-[13px] text-red-500">{error}</p>}

      {results !== null &&
        (results.length === 0 ? (
          <EmptyState message="No results found." />
        ) : (
          <CardList>
            {results.map((result, index) => (
              <CardRow key={`${result.url}-${index}`}>
                <a
                  href={result.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block transition-colors hover:text-foreground"
                >
                  <p className="text-[14px] font-medium tracking-tight">{result.title}</p>
                  <p className="mt-1 text-[13px] leading-snug text-zinc-500">{result.snippet}</p>
                  <p className="mt-1 truncate text-[12px] text-zinc-500">{result.url}</p>
                </a>
              </CardRow>
            ))}
          </CardList>
        ))}
    </div>
  );
}
