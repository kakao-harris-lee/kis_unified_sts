/**
 * Hand the viewer a file built from an in-memory blob.
 *
 * Three call sites grew their own copy of this and two of them diverged:
 *
 * - The feedback report download clicked an anchor that was never attached to
 *   the document. Firefox ignores a `download` click on a detached anchor, so
 *   nothing happened at all.
 * - All three revoked the object URL synchronously on the line after `click()`.
 *   A browser that has not finished reading the blob then finds the URL already
 *   gone.
 *
 * Neither failure throws, so a caller's `catch` cannot report it — the download
 * simply does not happen. Hence one helper: attach, click, detach, and revoke
 * on a later task.
 */
export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    // Deferred, not synchronous: the click only starts the download, and
    // revoking in the same task can invalidate the URL before the blob is read.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}

/** Convenience wrapper for the common case of downloading a JSON document. */
export function downloadJson(filename: string, value: unknown): void {
  downloadBlob(
    filename,
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
}
