import { describe, expect, it } from "vitest";
import {
  canProcess,
  channelSettingsError,
  calendarSlots,
  createDemo,
  datePlus,
  demoWeekStart,
  scheduleError,
  validateDonors,
} from "./studio";
describe("Demo domain protections", () => {
  it("groups visually overlapping calendar cards and retains each distinct job identity", () => {
    const first = createDemo().scheduled[0];
    const groups = calendarSlots([
      first,
      { ...first, id: "second", time: "11:00" },
      { ...first, id: "nearby", time: "12:00" },
      { ...first, id: "later", time: "16:00" },
    ]);
    expect(groups.map((group) => group.jobs.map((job) => job.id))).toEqual([
      ["model-tech", "second", "nearby"],
      ["later"],
    ]);
  });
  it("canonicalizes donor identifiers before exact duplicate validation", () => {
    const rows = validateDonors(
      "@SCIENCE_today\nhttps://t.me/New_source\n@new_SOURCE\nnot a channel",
      ["@science_today"],
    );
    expect(rows.map((row) => row.error)).toEqual([
      "Дубликат",
      "",
      "Дубликат",
      "Неверный username",
    ]);
  });
  it("never allows rejected or pending editorial content into rewrite or scheduling", () => {
    const data = createDemo();
    const rejected = data.posts.find((item) => item.id === "reject")!;
    expect(
      canProcess({ ...rejected, rewriteAllowed: true, state: "Готово" }),
    ).toBe(false);
    expect(
      scheduleError(rejected, data.channels[0], "2026-10-02", "15:00"),
    ).toContain("EditorialGate");
    expect(canProcess(data.posts.find((item) => item.id === "galaxy")!)).toBe(
      false,
    );
  });
  it("validates publication windows and overnight quiet hours", () => {
    const data = createDemo();
    const channel = {
      ...data.channels[0],
      windowStart: "00:00",
      windowEnd: "23:59",
    };
    expect(
      scheduleError(data.posts[0], channel, "2026-10-02", "23:30"),
    ).toContain("тихие часы");
    expect(
      scheduleError(data.posts[0], channel, "2026-10-02", "07:30"),
    ).toContain("тихие часы");
    expect(scheduleError(data.posts[0], channel, "2026-10-02", "15:00")).toBe(
      "",
    );
    expect(
      scheduleError(data.posts[0], data.channels[0], "2026-10-02", "21:00"),
    ).toContain("вне окна");
  });
  it("keeps fixture dates consistent with weekdays and unique schedule identities", () => {
    expect(new Date(`${demoWeekStart}T12:00:00Z`).getUTCDay()).toBe(1);
    expect(datePlus(demoWeekStart, 6)).toBe("2026-10-04");
    const jobs = createDemo().scheduled;
    expect(new Set(jobs.map((job) => job.id)).size).toBe(jobs.length);
  });
  it("rejects normalized impossible dates and out-of-range clock times", () => {
    const data = createDemo();
    for (const [date, time] of [
      ["2026-02-30", "15:00"],
      ["2026-10-02", "24:00"],
      ["2026-10-02", "15:60"],
    ]) {
      expect(
        scheduleError(data.posts[0], data.channels[0], date, time),
      ).toContain("корректные дату");
    }
  });
  it("does not save empty quiet hours, fractional limits or invalid publication windows", () => {
    const channel = createDemo().channels[0];
    expect(channelSettingsError(channel)).toBe("");
    for (const patch of [
      { quietStart: "" },
      { daily: 1.5 },
      { windowStart: "24:00" },
      { windowEnd: "08:00" },
    ]) {
      expect(channelSettingsError({ ...channel, ...patch })).not.toBe("");
    }
  });
});
