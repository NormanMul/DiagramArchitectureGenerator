import { describe, expect, it } from "vitest";

describe("smoke", () => {
  it("env is jsdom", () => {
    expect(typeof window).toBe("object");
  });

  it("typeof React types loadable (import-only)", async () => {
    const types = await import("../app/lib/types");
    expect(types).toBeTruthy();
  });
});
