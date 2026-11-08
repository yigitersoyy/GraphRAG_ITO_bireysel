import { describe, expect, it } from "vitest";
import { evidenceParts } from "./text";

describe("immutable source ranges", () => {
  it("uses Unicode code points rather than UTF-16 offsets", () => {
    expect(
      evidenceParts("🧠 Ada, İzmir’de.", {
        start_char: 2,
        end_char: 5,
        quote: "Ada",
      }),
    ).toEqual({ before: "🧠 ", quote: "Ada", after: ", İzmir’de." });
  });
  it("refuses a quote from a different revision or invalid range", () => {
    expect(
      evidenceParts("Yeni metin", {
        start_char: 0,
        end_char: 4,
        quote: "Eski",
      }),
    ).toBeNull();
    expect(
      evidenceParts("Ada", { start_char: -1, end_char: 3, quote: "Ada" }),
    ).toBeNull();
  });
});
