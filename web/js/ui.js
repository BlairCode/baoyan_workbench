import { api, uploadForm } from "./api.js";
import { fileButtons, fileIcon, renderFileList } from "./files.js";
import { schemas } from "./schemas.js";
import { pages, state } from "./state.js";
import { $, escapeHtml, shortText } from "./utils.js";

export function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => {
    el.hidden = true;
  }, 2800);
}

export async function loadSettings() {
  state.settings = await api("/api/settings");
  applySettings();
}

export function applySettings() {
  const settings = state.settings || {};
  const brandTitle = settings.brandTitle || "推免准备";
  const workspaceName = settings.workspaceName || "本地私有工作台";
  $("#brandTitle").textContent = brandTitle;
  $("#workspaceName").textContent = workspaceName;
  document.title = `${brandTitle}工作台`;
  document.body.dataset.theme = settings.theme || "default";
  const mark = $("#brandMark");
  if (settings.avatarMode === "upload" && settings.avatarUrl) {
    mark.innerHTML = `<img src="${settings.avatarUrl}" alt="" />`;
  } else {
    mark.textContent = (settings.avatarText || brandTitle || "推").slice(0, 2);
  }
}

export function renderNav(setPage) {
  $("#nav").innerHTML = pages
    .map(
      (page) => `
        <button class="nav-btn ${state.page === page.id ? "active" : ""}" data-page="${page.id}">
          <span class="nav-icon">${page.icon}</span><span>${page.title}</span>
        </button>
      `,
    )
    .join("");
  $("#nav").querySelectorAll("button").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.page)));
}

export function renderBadge(value, extra = "") {
  return `<span class="badge ${extra}">${escapeHtml(value || "未填写")}</span>`;
}

export function renderSimpleList(rows, titleKey, subKey, metaKey) {
  if (!rows.length) return `<div class="empty">暂无记录。</div>`;
  return `
    <div class="list compact-list">
      ${rows
        .slice(0, 8)
        .map((row) => `<div class="list-item"><strong>${escapeHtml(row[titleKey])}</strong><p>${escapeHtml(row[subKey] || "未填写")} · ${escapeHtml(row[metaKey] || "待补充")}</p></div>`)
        .join("")}
    </div>
  `;
}

export function openPapersDialog(title, rows, allowAssign = false, refreshContact = null) {
  $("#papersTitle").textContent = title;
  $("#papersList").innerHTML = rows.length
    ? `<div class="file-list">${rows
        .map(
          (row) => `
            <div class="file-item">
              ${fileIcon(row)}
              <div class="file-main"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(row.relative_path)} · ${escapeHtml(row.resource_kind || "资料")}</span></div>
              <div class="actions">
                ${fileButtons(row)}
                ${allowAssign ? `${professorAssignSelect(row.id)}<button class="mini" data-remove-contact="${row.id}">移出套磁</button>` : `<button class="mini" data-edit-material="${row.id}">归类</button>`}
              </div>
            </div>
          `,
        )
        .join("")}</div>`
    : `<div class="empty">暂无相关文件。</div>`;
  bindAssignActions(refreshContact);
  $("#papersDialog").showModal();
}

function professorAssignSelect(id) {
  return `
    <select class="mini-select" data-assign-paper="${id}">
      <option value="">归到导师...</option>
      ${(state.contactData?.professors || []).map((prof) => `<option value="${escapeHtml(prof.name)}">${escapeHtml(prof.name)}</option>`).join("")}
    </select>
  `;
}

function bindAssignActions(refreshContact) {
  document.querySelectorAll("[data-assign-paper]").forEach((select) => {
    select.addEventListener("change", async () => {
      if (!select.value) return;
      await api(`/api/materials/${select.dataset.assignPaper}`, {
        method: "PATCH",
        body: JSON.stringify({ category: "套磁", stage: "套磁", related_professor: select.value }),
      });
      $("#papersDialog").close();
      toast(`已归类到：${select.value}`);
      refreshContact?.();
    });
  });
  document.querySelectorAll("[data-remove-contact]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/materials/${button.dataset.removeContact}`, {
        method: "PATCH",
        body: JSON.stringify({ category: "参考", stage: "通用", related_professor: "" }),
      });
      $("#papersDialog").close();
      toast("已从未归类套磁资源移出");
      refreshContact?.();
    });
  });
}

export async function ensureOptions() {
  if (!state.options) state.options = await api("/api/options");
  return state.options;
}

export async function openEditor(page, row = null, refresh) {
  const schema = schemas[page];
  const options = await ensureOptions();
  const dialog = $("#editor");
  $("#editorTitle").textContent = row ? `编辑${schema.title}` : `新增${schema.title}`;
  $("#editorFields").innerHTML = schema.fields.map((field) => renderField(field, row, options)).join("");
  $("#saveBtn").onclick = async (event) => {
    event.preventDefault();
    const payload = collectForm(schema);
    if (page === "materials") normalizeMaterialPayload(payload);
    const missing = schema.fields.find((field) => field.required && !String(payload[field.key] || "").trim());
    if (missing) return toast(`请填写：${missing.label}`);
    const path = row ? `${schema.endpoint}/${row.id}` : schema.endpoint;
    const method = row ? "PATCH" : "POST";
    await api(path, { method, body: JSON.stringify(payload) });
    dialog.close();
    toast("已保存");
    refresh();
  };
  dialog.showModal();
}

function renderField(field, row, options) {
  const value = row?.[field.key] ?? "";
  const full = field.full || field.type === "textarea" ? " full" : "";
  let control = "";
  const optionList = field.optionKey ? options[field.optionKey] || [] : field.options;
  if (optionList) {
    const values = field.allowEmpty ? ["", ...optionList] : [...optionList];
    if (value && !values.includes(value)) values.push(value);
    control = `<select name="${field.key}">${values.map((option) => `<option value="${escapeHtml(option)}" ${String(value) === String(option) ? "selected" : ""}>${escapeHtml(option || "未设置")}</option>`).join("")}</select>`;
  } else if (field.type === "textarea") {
    control = `<textarea name="${field.key}">${escapeHtml(value)}</textarea>`;
  } else {
    control = `<input name="${field.key}" type="${field.type || "text"}" value="${escapeHtml(value)}" />`;
  }
  return `<label class="field${full}"><span>${field.label}</span>${control}</label>`;
}

function collectForm(schema) {
  const payload = {};
  schema.fields.forEach((field) => {
    payload[field.key] = document.querySelector(`[name="${field.key}"]`)?.value ?? "";
  });
  return payload;
}

function normalizeMaterialPayload(payload) {
  const stageMap = { 基本材料: "通用", 套磁: "套磁", 院校: "夏令营", 项目: "科研", 面试: "面试", 参考: "通用" };
  payload.stage = stageMap[payload.category] || "通用";
  if (payload.category !== "套磁") payload.related_professor = "";
  if (payload.category !== "院校") payload.related_program = "";
  if (!payload.resource_kind) payload.resource_kind = payload.category || "参考";
}

export function openSettings(refresh) {
  const dialog = $("#settingsDialog");
  const settings = state.settings || {};
  dialog.querySelector('[name="brandTitle"]').value = settings.brandTitle || "";
  dialog.querySelector('[name="workspaceName"]').value = settings.workspaceName || "";
  dialog.querySelector('[name="avatarText"]').value = settings.avatarText || "";
  dialog.querySelector('[name="motto"]').value = settings.motto || "";
  dialog.querySelector('[name="theme"]').value = settings.theme || "default";
  dialog.querySelector(`[name="avatarMode"][value="${settings.avatarMode || "text"}"]`).checked = true;
  $("#avatarInput").value = "";
  updateAvatarPreview();
  dialog.querySelectorAll('[name="avatarMode"], [name="avatarText"]').forEach((el) => el.addEventListener("input", updateAvatarPreview));
  $("#avatarInput").onchange = updateAvatarPreview;
  $("#saveSettingsBtn").onclick = (event) => saveSettings(event, refresh);
  dialog.showModal();
}

function updateAvatarPreview() {
  const dialog = $("#settingsDialog");
  const mode = dialog.querySelector('[name="avatarMode"]:checked')?.value || "text";
  const preview = $("#avatarPreview");
  const file = $("#avatarInput").files[0];
  if (mode === "upload" && file) {
    preview.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="" />`;
  } else if (mode === "upload" && state.settings?.avatarUrl) {
    preview.innerHTML = `<img src="${state.settings.avatarUrl}" alt="" />`;
  } else {
    preview.textContent = (dialog.querySelector('[name="avatarText"]').value || state.settings?.brandTitle || "推").slice(0, 2);
  }
}

async function saveSettings(event, refresh) {
  event.preventDefault();
  const dialog = $("#settingsDialog");
  const payload = {
    brandTitle: dialog.querySelector('[name="brandTitle"]').value.trim(),
    workspaceName: dialog.querySelector('[name="workspaceName"]').value.trim(),
    avatarText: dialog.querySelector('[name="avatarText"]').value.trim(),
    avatarMode: dialog.querySelector('[name="avatarMode"]:checked')?.value || "text",
    motto: dialog.querySelector('[name="motto"]').value.trim(),
    theme: dialog.querySelector('[name="theme"]').value,
  };
  state.settings = await api("/api/settings", { method: "PATCH", body: JSON.stringify(payload) });
  const avatar = $("#avatarInput").files[0];
  if (payload.avatarMode === "upload" && avatar) {
    const form = new FormData();
    form.append("avatar", avatar);
    state.settings = await uploadForm("/api/settings/avatar", form);
  }
  applySettings();
  dialog.close();
  toast("设置已保存");
  refresh();
}

export function shortDirection(value) {
  return shortText(value, 10);
}
