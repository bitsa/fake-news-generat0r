import { describe, expect, it } from "vitest";
import { SOURCES } from "./sources";
import type { SourceId } from "../types/api";

describe("SOURCES", () => {
  it("has an entry for every SourceId with matching id", () => {
    const ids: SourceId[] = ["NYT", "NPR", "Guardian"];
    for (const id of ids) {
      expect(SOURCES[id]).toBeDefined();
      expect(SOURCES[id].id).toBe(id);
      expect(SOURCES[id].name.length).toBeGreaterThan(0);
      expect(SOURCES[id].color).toMatch(/^var\(--/);
    }
  });
});
