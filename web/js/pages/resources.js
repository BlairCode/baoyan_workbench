import { api, uploadForm } from "../api.js";
import { renderFileList } from "../files.js";
import { state } from "../state.js";
import { escapeHtml } from "../utils.js";

export async function renderResources(bindCommonActions, scanMaterials) {
  const data = await api("/api/materials/groups");
  const q = state.q.toLowerCase();
  const groups = data.byFolder
    .map((group) => ({
      ...group,
      items: group.items.filter((item) =>
        [item.name, item.relative_path, item.category, item.resource_kind, item.related_professor, item.related_program, item.note].join(" ").toLowerCase().includes(q),
      ),
    }))
    .filter((group) => !q || group.items.length);
  document.querySelector("#app").innerHTML = `
    <section class="panel">
      <div class="panel-head">
        <h3>资源浏览</h3>
        <div class="actions">
          <button class="secondary" id="expandFoldersBtn">全部展开</button>
          <button class="secondary" id="collapseFoldersBtn">全部折叠</button>
          <label class="primary upload-label">添加文件<input id="uploadInput" type="file" hidden /></label>
          <button class="secondary" id="scanInlineBtn">同步文件</button>
        </div>
      </div>
      <div class="panel-body resource-groups">${groups.map(renderResourceGroup).join("") || `<div class="empty">没有匹配的文件。</div>`}</div>
    </section>
  `;
  document.querySelector("#scanInlineBtn").addEventListener("click", scanMaterials);
  document.querySelector("#uploadInput").addEventListener("change", uploadFile);
  document.querySelector("#expandFoldersBtn").addEventListener("click", () => setFoldersOpen(true));
  document.querySelector("#collapseFoldersBtn").addEventListener("click", () => setFoldersOpen(false));
  bindCommonActions();
}

function renderResourceGroup(group) {
  const nested = group.items.map((item) => ({ ...item, _depth: depthInGroup(group.name, item.relative_path) }));
  return `
    <details class="folder">
      <summary>
        <span>${escapeHtml(group.name)}</span>
        <span class="folder-summary-actions"><strong>${group.items.length}</strong><button class="mini" data-open-folder-path="${escapeHtml(group.path)}">打开文件夹</button></span>
      </summary>
      <div class="folder-body">${renderFileList(nested, { nested: true, indent: 1 })}</div>
    </details>
  `;
}

function depthInGroup(group, relativePath) {
  const rel = String(relativePath || "");
  const parts = rel.replace(group, "").split(/[\\/]/).filter(Boolean);
  return Math.max(1, parts.length);
}

function setFoldersOpen(open) {
  document.querySelectorAll(".folder").forEach((folder) => {
    folder.open = open;
  });
}

async function uploadFile(event) {
  const file = event.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  await uploadForm("/api/materials/upload", form);
  window.dispatchEvent(new CustomEvent("app-toast", { detail: `已添加：${file.name}` }));
  window.dispatchEvent(new CustomEvent("app-refresh"));
}
