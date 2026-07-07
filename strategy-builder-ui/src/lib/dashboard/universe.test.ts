import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

import { apiClient } from "./client";
import { universeApi } from "./universe";

describe("universeApi.resolve", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls the resolve endpoint with the code param", async () => {
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { code: "005930", name: "삼성전자", known: true },
    });

    const res = await universeApi.resolve("005930");

    expect(apiClient.get).toHaveBeenCalledWith("/api/trading/universe/resolve", {
      params: { code: "005930" },
    });
    expect(res.data.known).toBe(true);
  });
});
