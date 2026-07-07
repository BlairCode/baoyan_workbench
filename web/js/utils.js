export const $ = (selector) => document.querySelector(selector);

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function fileSize(size) {
  const n = Number(size || 0);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function percent(value, total) {
  const n = Number(value || 0);
  const d = Number(total || 0);
  return d ? Math.round((n / d) * 100) : 0;
}

export function shortText(value, max = 12) {
  const text = String(value || "待补充").replace(/[、，,；;。.\s]+/g, " ").trim();
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}
