import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { downloadBlob, downloadJson } from "./download";

describe("downloadBlob", () => {
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.useFakeTimers();
    createObjectURL = vi.fn(() => "blob:generated");
    revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  function captureClick() {
    const seen: Array<{ connected: boolean; href: string; download: string }> = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      function mockClick(this: HTMLAnchorElement) {
        seen.push({
          connected: this.isConnected,
          href: this.href,
          download: this.download,
        });
      },
    );
    return seen;
  }

  it("clicks an anchor that is attached to the document", () => {
    // Firefox ignores a `download` click on a detached anchor and reports
    // nothing, so attachment is the whole point of the helper.
    const seen = captureClick();

    downloadBlob("report.json", new Blob(["{}"], { type: "application/json" }));

    expect(seen).toHaveLength(1);
    expect(seen[0].connected).toBe(true);
    expect(seen[0].href).toBe("blob:generated");
    expect(seen[0].download).toBe("report.json");
  });

  it("detaches the anchor again once the click is dispatched", () => {
    captureClick();

    downloadBlob("report.json", new Blob(["{}"]));

    expect(document.querySelector("a[download]")).toBeNull();
  });

  it("revokes the object URL on a later task, not during the click", () => {
    const seen = captureClick();

    downloadBlob("report.json", new Blob(["{}"]));

    expect(seen).toHaveLength(1);
    expect(revokeObjectURL).not.toHaveBeenCalled();

    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:generated");
  });

  it("still detaches and schedules the revoke when the click throws", () => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(() => downloadBlob("report.json", new Blob(["{}"]))).toThrow("blocked");
    expect(document.querySelector("a[download]")).toBeNull();

    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:generated");
  });

  it("serialises JSON with downloadJson", async () => {
    // jsdom's Blob has no .text(), and FileReader needs real timers.
    vi.useRealTimers();
    const seen = captureClick();
    const blobs: Blob[] = [];
    createObjectURL.mockImplementation((blob: Blob) => {
      blobs.push(blob);
      return "blob:generated";
    });

    downloadJson("feedback.json", { kind: "weekly", count: 2 });

    expect(seen[0].download).toBe("feedback.json");
    expect(blobs[0].type).toBe("application/json");
    const text = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsText(blobs[0]);
    });
    expect(text).toBe('{\n  "kind": "weekly",\n  "count": 2\n}');
  });
});
