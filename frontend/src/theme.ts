export type Theme = "dark" | "light";

export function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem("workspace-theme");
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    /* Storage may be unavailable in private browser contexts. */
  }
  return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", theme === "light" ? "#f5f7fa" : "#181818");
}
