import { api } from "./api.js";
import { escapeHtml, fileSize } from "./utils.js";

const iconMap = {
  ".pdf": "pdf",
  ".doc": "doc",
  ".docx": "doc",
  ".ppt": "ppt",
  ".pptx": "ppt",
  ".xls": "sheet",
  ".xlsx": "sheet",
  ".csv": "sheet",
  ".png": "image",
  ".jpg": "image",
  ".jpeg": "image",
  ".gif": "image",
  ".webp": "image",
  ".md": "text",
  ".txt": "text",
};

export function fileIcon(row) {
  const type = iconMap[(row.ext || "").toLowerCase()] || "file";
  return `
    <span class="file-icon file-icon-${type}" aria-hidden="true">
      <svg viewBox="0 0 28 32" focusable="false">
        <path class="paper" d="M5 1.5h12.5L23 7v23.5H5z" />
        <path class="fold" d="M17.5 1.5V7H23" />
        <path class="mark" d="M9 15h10M9 20h7" />
      </svg>
    </span>
  `;
}

export function fileButtons(row) {
  return `
    <button class="mini" data-open="${row.id}">打开</button>
    ${row.actions?.canPreview ? `<a class="mini link-btn" href="${row.actions.viewUrl}" target="_blank">预览</a>` : ""}
  `;
}

export function renderFileList(rows, options = {}) {
  if (!rows.length) return `<div class="empty small">暂无文件</div>`;
  const nested = options.nested ? " nested-files" : "";
  return `
    <div class="file-list${nested}">
      ${rows.map((row) => renderFileItem(row, options)).join("")}
    </div>
  `;
}

export function renderFileItem(row, options = {}) {
  const rel = row.relative_path || row.path || "";
  const indent = Number(row._depth || options.indent || 0);
  const style = indent ? ` style="--indent:${indent}"` : "";
  return `
    <div class="file-item ${row.missing ? "missing" : ""}"${style}>
      ${fileIcon(row)}
      <div class="file-main">
        <strong title="${escapeHtml(rel)}">${escapeHtml(row.name)}</strong>
        <span>${escapeHtml(row.category || row.resource_kind)} · ${escapeHtml(row.resource_kind || "资料")} · ${fileSize(row.size)}</span>
        <code>${escapeHtml(rel)}</code>
        ${row.related_professor || row.related_program ? `<p class="file-note">${escapeHtml(row.related_professor || row.related_program)}</p>` : ""}
        ${row.note ? `<p class="file-note">${escapeHtml(row.note)}</p>` : ""}
      </div>
      <div class="actions">${fileButtons(row)}<button class="mini" data-edit-material="${row.id}">归类</button><button class="mini danger" data-delete-file="${row.id}" data-file-name="${escapeHtml(row.name)}">删除文件</button></div>
    </div>
  `;
}

export async function openMaterial(id, toast) {
  await api(`/api/materials/${id}/open`, { method: "POST" });
  toast("已调用本机默认程序打开文件");
}

export async function openFolderPath(path, toast) {
  await api("/api/folders/open", { method: "POST", body: JSON.stringify({ path }) });
  toast("已打开文件夹");
}

export async function deleteFile(id, name, toast, refresh) {
  if (!confirm(`确定删除本地文件吗？\n\n${name}\n\n此操作会直接删除文件。`)) return;
  await api(`/api/materials/${id}/file`, { method: "DELETE" });
  toast("已删除本地文件");
  refresh();
}
