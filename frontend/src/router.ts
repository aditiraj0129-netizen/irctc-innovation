// Tiny hash router helper: "#/options/<id>" etc.
export function go(path: string) {
  window.location.hash = "#/" + path;
  window.scrollTo(0, 0);
}
