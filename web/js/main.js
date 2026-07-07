import { api } from "./api.js";
import { deleteFile, openFolderPath, openMaterial } from "./files.js";
import { renderContact } from "./pages/contact.js";
import { renderDashboard } from "./pages/dashboard.js";
import { renderResources } from "./pages/resources.js";
import { renderTablePage } from "./pages/table.js";
import { schemas } from "./schemas.js";
import { pages, state } from "./state.js";
import { $, escapeHtml } from "./utils.js";
import { loadSettings, openEditor, openSettings, renderNav, toast } from "./ui.js";

function setPage(page) {
  state.page = page;
  state.q = "";
  $("#searchInput").value = "";
  render();
}

async function render() {
  renderNav(setPage);
  const page = pages.find((item) => item.id === state.page);
  $("#pageTitle").textContent = page.title;
  $("#searchInput").placeholder = state.page === "dashboard" ? "搜索全部文件" : `搜索${page.title}`;
  if (state.page === "dashboard") return renderDashboard(bindCommonActions);
  if (state.page === "contact") return renderContact(bindCommonActions, render);
  if (state.page === "resources") return renderResources(bindCommonActions, scanMaterials);
  return renderTablePage(state.page, bindCommonActions, render);
}

function bindCommonActions() {
  document.querySelectorAll("[data-jump]").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.jump)));
  document.querySelectorAll("[data-open]").forEach((button) => button.addEventListener("click", () => openMaterial(button.dataset.open, toast)));
  document.querySelectorAll("[data-open-folder-path]").forEach((button) =>
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openFolderPath(button.dataset.openFolderPath, toast);
    }),
  );
  document.querySelectorAll("[data-delete-file]").forEach((button) => button.addEventListener("click", () => deleteFile(button.dataset.deleteFile, button.dataset.fileName, toast, render)));
  document.querySelectorAll("[data-edit-material]").forEach((button) => {
    button.addEventListener("click", async () => {
      const data = await api("/api/materials");
      const row = data.items.find((item) => String(item.id) === String(button.dataset.editMaterial));
      if (!row) return toast("没有找到这条文件记录，请先同步文件");
      openEditor("materials", row, render);
    });
  });
}

async function scanMaterials() {
  const data = await api("/api/materials/scan", { method: "POST" });
  toast(`同步完成：新增 ${data.inserted}，更新 ${data.updated}，缺失 ${data.missing}`);
  render();
}

async function backupData() {
  const data = await api("/api/backup", { method: "POST" });
  toast(`备份完成：${data.path}`);
}

$("#scanBtn").addEventListener("click", scanMaterials);
$("#backupBtn").addEventListener("click", backupData);
$("#settingsBtn").addEventListener("click", () => openSettings(render));

let searchTimer = null;
$("#searchInput").addEventListener("input", (event) => {
  window.clearTimeout(searchTimer);
  state.q = event.target.value.trim();
  searchTimer = window.setTimeout(render, 160);
});

window.addEventListener("app-refresh", render);
window.addEventListener("app-scan", scanMaterials);
window.addEventListener("app-toast", (event) => toast(event.detail));

loadSettings()
  .then(render)
  .catch((error) => {
    console.error(error);
    toast(error.message);
  });
