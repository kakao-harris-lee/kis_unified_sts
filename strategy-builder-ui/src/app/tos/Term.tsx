"use client";

import { useId, useState, type ReactNode } from 'react';
import { glossaryTerm } from '@/lib/dashboard/tosGlossary';

interface TermProps {
  /** The raw document string — a field name, rule id, halt code, flag letter. */
  name: string | null | undefined;
  /** What to show. Defaults to the glossary's plain-Korean label. */
  children?: ReactNode;
  className?: string;
}

/**
 * A term that carries its own explanation — the one disclosure primitive here.
 *
 * It is NOT a button. `/tos` is a read model, and an element with a button role
 * reads — to a screen reader and to the suite that guards this page — as
 * something that acts on the runtime. This is a focusable term with a
 * description instead.
 *
 * **Two descriptions, one text.** The explanation rides on `title` at all
 * times, which is the accessible description whenever nothing better is
 * present, and the styled popup is rendered — with `aria-describedby` pointing
 * at it, which takes precedence — exactly while the term is hovered, focused
 * or tapped. Since focus opens the popup synchronously, assistive technology
 * always reaches a described element; since the popup is absent when closed,
 * its sentence never leaks into the surrounding element's text, where it would
 * turn every table cell on the page into a paragraph.
 *
 * Touch has no hover, so a tap toggles the same popup a pointer reveals.
 */
export default function Term({ name, children, className }: TermProps) {
  const term = glossaryTerm(name);
  const id = useId();
  const [open, setOpen] = useState(false);
  const shown = children ?? term?.label ?? name ?? '알 수 없음';

  // Nothing to explain: render the text plainly rather than a control that
  // opens an empty popup.
  if (!term) return <span className={className}>{shown}</span>;

  return (
    <span className={`relative inline-block ${className ?? ''}`}>
      <span
        tabIndex={0}
        title={term.meaning}
        aria-describedby={open ? id : undefined}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        // Touch fires pointerenter immediately before the click it precedes,
        // so letting it open would leave the tap with nothing to do but close
        // again. Hover belongs to pointers that can leave; a tap toggles.
        onPointerEnter={(event) => {
          if (event.pointerType !== 'touch') setOpen(true);
        }}
        onPointerLeave={(event) => {
          if (event.pointerType !== 'touch') setOpen(false);
        }}
        onClick={() => setOpen((previous) => !previous)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
        }}
        className="cursor-help border-b border-dotted border-slate-400 outline-none focus-visible:rounded-sm focus-visible:ring-2 focus-visible:ring-slate-500 dark:border-slate-500"
      >
        {shown}
      </span>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute left-0 top-full z-20 mt-1 w-64 max-w-[min(16rem,calc(100vw-2rem))] rounded-lg border border-slate-300 bg-white p-2 text-xs font-normal leading-relaxed text-slate-700 shadow-lg dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
        >
          {term.meaning}
        </span>
      )}
    </span>
  );
}
