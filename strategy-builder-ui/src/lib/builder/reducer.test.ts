import { describe, expect, it } from "vitest";
import { builderReducer, INITIAL_STATE } from "./reducer";

describe("builderReducer", () => {
  it("updates metadata without mutating INITIAL_STATE", () => {
    const next = builderReducer(INITIAL_STATE, {
      type: "SET_METADATA",
      payload: {
        id: "mean-reversion-v1",
        name: "Mean Reversion V1",
        tags: ["paper", "stock"],
      },
    });

    expect(next.metadata).toMatchObject({
      id: "mean-reversion-v1",
      name: "Mean Reversion V1",
      tags: ["paper", "stock"],
    });
    expect(next).not.toBe(INITIAL_STATE);
    expect(next.metadata).not.toBe(INITIAL_STATE.metadata);
    expect(INITIAL_STATE.metadata).toEqual({
      id: "",
      name: "",
      description: "",
      category: "custom",
      tags: [],
      author: "user",
    });
  });
});
