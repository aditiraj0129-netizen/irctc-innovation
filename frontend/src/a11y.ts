// Accessibility preferences, stored on this device and applied as classes on <html>.
export interface A11y { large: boolean; contrast: boolean; simple: boolean }
const KEY = "aglaKadam.a11y";

export function loadA11y(): A11y {
  try { return { large: false, contrast: false, simple: false, ...JSON.parse(window.localStorage.getItem(KEY) || "{}") }; }
  catch { return { large: false, contrast: false, simple: false }; }
}
export function applyA11y(a: A11y) {
  const c = document.documentElement.classList;
  c.toggle("a11y-large", a.large); c.toggle("a11y-contrast", a.contrast); c.toggle("a11y-simple", a.simple);
  try { window.localStorage.setItem(KEY, JSON.stringify(a)); } catch { /* ignore */ }
}
