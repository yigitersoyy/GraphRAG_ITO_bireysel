export function evidenceParts(
  text: string,
  evidence: { start_char: number; end_char: number; quote: string },
) {
  const points = Array.from(text);
  const { start_char: start, end_char: end, quote } = evidence;
  if (
    !Number.isInteger(start) ||
    !Number.isInteger(end) ||
    start < 0 ||
    end <= start ||
    end > points.length
  )
    return null;
  const actual = points.slice(start, end).join("");
  if (actual !== quote) return null;
  return {
    before: points.slice(0, start).join(""),
    quote: actual,
    after: points.slice(end).join(""),
  };
}
