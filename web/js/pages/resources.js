import { api, uploadForm } from "../api.js";
import { renderFileList } from "../files.js";
import { state } from "../state.js";
import { escapeHtml } from "../utils.js";

export async function renderResources(bindCommonActions, scanMaterials) {
  const query = state.q.trim();
  const params = query
    ? `q=${encodeURIComponent(query)}&limit=200`
    : `path=${encodeURIComponent(state.resourcePath || "")}`;
  const data = await api(`/api/resources?${params}`);
  document.querySelector("#app").innerHTML = `
    <section class="panel">
      <div class="panel-head">
        <div>
          <h3>资源浏览</h3>
          <p class="panel-subtitle">${data.mode === "search" ? `搜索“${escapeHtml(data.query)}”` : "按需加载当前目录，进入文件夹后才读取下一级"}</p>
        </div>
        <div class="actions">
          <label class="primary upload-label">添加文件<input id="uploadInput" type="file" hidden /></label>
          <button class="secondary" id="scanInlineBtn">同步文件</button>
        </div>
      </div>
      <div class="panel-body resource-browser">
        ${data.mode === "search" ? renderSearchResults(data) : renderDirectory(data)}
      </div>
    </section>
  `;
  document.querySelector("#scanInlineBtn").addEventListener("click", scanMaterials);
  document.querySelector("#uploadInput").addEventListener("change", uploadFile);
  document.querySelectorAll("[data-resource-path]").forEach((button) => {
    button.addEventListener("click", () => {
      state.resourcePath = button.dataset.resourcePath || "";
      renderResources(bindCommonActions, scanMaterials).catch(showPageError);
    });
  });
  document.querySelector("[data-clear-resource-search]")?.addEventListener("click", () => {
    state.q = "";
    document.querySelector("#searchInput").value = "";
    renderResources(bindCommonActions, scanMaterials).catch(showPageError);
  });
  bindCommonActions();
}

function renderDirectory(data) {
  const folders = data.directories
    .map(
      (folder) => `
        <article class="resource-folder-card">
          <button class="resource-folder-main" data-resource-path="${escapeHtml(folder.relativePath)}">
            <span class="resource-folder-icon" aria-hidden="true"></span>
            <span><strong>${escapeHtml(folder.name)}</strong><small>${folder.childCount} 个直接子项</small></span>
          </button>
          <button class="mini" data-open-folder-path="${escapeHtml(folder.path)}">本机打开</button>
        </article>
      `,
    )
    .join("");
  const isEmpty = !data.directories.length && !data.files.length;
  return `
    <nav class="resource-breadcrumbs" aria-label="资源路径">
      ${data.breadcrumbs
        .map((item, index) => `<button data-resource-path="${escapeHtml(item.relativePath)}" ${index === data.breadcrumbs.length - 1 ? "disabled" : ""}>${escapeHtml(item.name)}</button>`)
        .join("<span>/</span>")}
      <button class="mini resource-open-current" data-open-folder-path="${escapeHtml(data.path)}">打开当前文件夹</button>
    </nav>
    ${folders ? `<div class="resource-folder-grid">${folders}</div>` : ""}
    ${data.files.length ? `<div class="resource-current-files"><h4>当前层文件 <span>${data.files.length}</span></h4>${renderFileList(data.files)}</div>` : ""}
    ${isEmpty ? `<div class="empty">当前文件夹为空。</div>` : ""}
  `;
}

function renderSearchResults(data) {
  return `
    <div class="resource-search-summary">
      <span>找到 ${data.items.length} 个文件${data.truncated ? "，仅显示前 200 个" : ""}</span>
      <button class="secondary" data-clear-resource-search>返回目录</button>
    </div>
    ${renderFileList(data.items)}
  `;
}

function showPageError(error) {
  window.dispatchEvent(new CustomEvent("app-toast", { detail: error.message }));
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
