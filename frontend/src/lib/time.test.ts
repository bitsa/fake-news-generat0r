import { describe, expect, it } from "vitest";
import { relTime } from "./time";

const NOW = new Date("2026-05-07T12:00:00Z");

describe("relTime", () => {
  it("returns em-dash for null", () => {
    expect(relTime(null, NOW)).toBe("—");
  });

  it("returns em-dash for unparseable input", () => {
    expect(relTime("not-a-date", NOW)).toBe("—");
  });

  it("returns 'just now' under a minute", () => {
    expect(relTime("2026-05-07T11:59:30Z", NOW)).toBe("just now");
  });

  it("formats minutes, hours, and days", () => {
    expect(relTime("2026-05-07T11:55:00Z", NOW)).toBe("5m ago");
    expect(relTime("2026-05-07T09:00:00Z", NOW)).toBe("3h ago");
    expect(relTime("2026-05-05T12:00:00Z", NOW)).toBe("2d ago");
  });

  it("clamps future timestamps to 'just now'", () => {
    expect(relTime("2026-05-07T12:00:30Z", NOW)).toBe("just now");
  });
});
