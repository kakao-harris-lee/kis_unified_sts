"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

/**
 * Reads a `?highlight=<id>` query param and, once the matching row is in the
 * DOM, scrolls it into view. Returns the highlight id so the caller can apply a
 * ring class to the matching row.
 *
 * The receiving page inherits the root <Suspense> boundary (layout.tsx) that
 * useSearchParams requires, so no extra wrapper is needed here. useSearchParams
 * can be null (no active route context, e.g. under some test renders), so it is
 * accessed defensively.
 *
 * @param domId  Given the highlight id, the DOM id of the element to scroll to
 *               (e.g. `(id) => `trade-${id}``). The caller must render that id
 *               on the matching row.
 * @param ready  When true, the target rows are rendered (e.g. data loaded), so
 *               the scroll is attempted only once the row can exist.
 */
export function useHighlightParam(
  domId: (id: string) => string,
  ready: boolean,
): string | null {
  const searchParams = useSearchParams();
  const highlight = searchParams?.get("highlight") ?? null;
  // Ref (not state) so the one-shot scroll does not trigger a re-render from
  // inside the effect (react-hooks/set-state-in-effect).
  const scrolledRef = useRef(false);

  useEffect(() => {
    if (!highlight || !ready || scrolledRef.current) return;
    const el = document.getElementById(domId(highlight));
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    scrolledRef.current = true;
  }, [highlight, ready, domId]);

  return highlight;
}
