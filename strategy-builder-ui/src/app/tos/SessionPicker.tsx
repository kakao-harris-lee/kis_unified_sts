"use client";

import { useState, type FormEvent } from 'react';
import {
  LATEST_SESSION,
  groupSessionsByDate,
  sessionOptionLabel,
} from '@/lib/dashboard/tosBars';
import type { SessionsRead } from './queries';

interface SessionPickerProps {
  sessions: SessionsRead;
  /** The session the page is showing. */
  value: string;
  onChange: (session: string) => void;
}

/**
 * Which exported session the sections below describe.
 *
 * The cards above cover the newest trading day; this is how an older one is
 * reached. It is a selection control, not a command: nothing here starts,
 * stops or re-exports anything, and the one button on the page's whole bar
 * surface belongs to the fallback text box — the route's cap keeps the NEWEST
 * sessions, so without a box to name an older one the cap would make it
 * unreachable from the browser entirely.
 */
export default function SessionPicker({ sessions, value, onChange }: SessionPickerProps) {
  const [draft, setDraft] = useState('');
  const groups = groupSessionsByDate(sessions.sessions);
  // Falling back to the text box is what keeps a session reachable when the
  // listing cannot be had — a dropdown with nothing in it would be a dead end.
  const picker = groups.length > 0;
  const unlisted =
    value !== LATEST_SESSION && !sessions.sessions.some((entry) => entry.session === value);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onChange(draft.trim() || LATEST_SESSION);
  };

  // The one text box, rendered under two different ids: it IS the «세션»
  // control when there is no listing, and a second, separately labelled one
  // beside the picker when the cap cut the list. One definition, so the two
  // cannot drift into behaving differently.
  const manualBox = (id: string) => (
    <>
      <input
        id={id}
        name="session"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder={LATEST_SESSION}
        className="w-48 rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-950"
      />
      <button
        type="submit"
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-700"
      >
        조회
      </button>
    </>
  );

  return (
    <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
      <label htmlFor="bars-session" className="text-sm text-slate-500 dark:text-slate-400">
        세션
      </label>
      {picker ? (
        <select
          id="bars-session"
          name="session"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="max-w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-950"
        >
          <option value={LATEST_SESSION}>최신 세션 ({LATEST_SESSION})</option>
          {/* A session the operator asked for that the listing does not carry —
              typed before the listing arrived, or exported and then removed.
              Without its own option the select would show blank while the
              panels below render that very session. */}
          {unlisted && (
            <option value={value} title={value}>
              {value}
            </option>
          )}
          {groups.map((group) => (
            <optgroup key={group.label} label={group.label}>
              {group.sessions.map((entry) => (
                <option key={entry.session} value={entry.session} title={entry.session}>
                  {sessionOptionLabel(entry)}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      ) : (
        manualBox('bars-session')
      )}
      {/* The cap keeps the newest sessions, so an older one is in the directory
          and readable but not in the dropdown. Without a box to name it, the
          cap would make it unreachable from the UI entirely — so the picker and
          the box stand side by side here. */}
      {picker && sessions.truncated && (
        <div className="flex w-full flex-wrap items-center gap-2">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            최근 {sessions.sessions.length}개 세션만 목록에 있습니다. 더 오래된 세션은 이름으로
            조회해 주세요.
          </p>
          <label htmlFor="bars-session-id" className="text-sm text-slate-500 dark:text-slate-400">
            직접 입력
          </label>
          {manualBox('bars-session-id')}
        </div>
      )}
    </form>
  );
}
