import { api } from "../api.js";
import { state } from "../state.js";
import { escapeHtml } from "../utils.js";
import { openEditor, openPapersDialog, renderBadge, shortDirection, toast } from "../ui.js";

const contactFilters = {
  school: "",
  status: "",
};

const SCHOOL_COLOR_PALETTE = [
  "#5B7FA3",
  "#4E8B78",
  "#A66F51",
  "#7A6FA8",
  "#B07A3F",
  "#B05F73",
  "#4C8A9A",
  "#72894B",
];

const SCHOOL_COLOR_PRESETS = {
  东南: { color: "#587558", label: "东南大学官方标准绿" },
  东南大学: { color: "#587558", label: "东南大学官方标准绿" },
  中科大: { color: "#005BAE", label: "中国科大·科大蓝" },
  中国科学技术大学: { color: "#005BAE", label: "中国科大·科大蓝" },
  南大: { color: "#4D0099", label: "南京大学·南大紫" },
  南京大学: { color: "#4D0099", label: "南京大学·南大紫" },
  南理工: { color: "#990099", label: "南京理工大学官方标准紫" },
  南京理工大学: { color: "#990099", label: "南京理工大学官方标准紫" },
};

export async function renderContact(bindCommonActions, refresh) {
  const data = await api("/api/contact-workspace");
  const q = state.q.toLowerCase();
  const allProfessors = data.professors;
  data.professors = allProfessors.filter((prof) => {
    const text = [prof.name, prof.school, prof.college, prof.direction, prof.status, prof.note, ...prof.letters.map((item) => item.name), ...prof.related.map((item) => item.name)].join(" ").toLowerCase();
    const matchSearch = !q || text.includes(q);
    const matchSchool = !contactFilters.school || prof.school === contactFilters.school;
    const matchStatus = !contactFilters.status || prof.status === contactFilters.status;
    return matchSearch && matchSchool && matchStatus;
  });
  state.contactData = data;
  document.querySelector("#app").innerHTML = `
    <section class="panel">
      <div class="panel-head">
        <h3>导师套磁</h3>
        <div class="actions">
          <button class="secondary" id="schoolColorBtn">学校配色</button>
          <button class="secondary" id="scanInlineBtn">同步文件</button>
          <button class="primary" id="addProfessorBtn">新增导师</button>
        </div>
      </div>
      <div class="panel-body">
        ${renderContactFilters(allProfessors, data.professors.length)}
        <div class="table-wrap contact-table">
          <table>
            <thead><tr><th>优先级</th><th>导师</th><th>学校</th><th>学院/组</th><th>方向</th><th>状态</th><th>文件</th><th>操作</th></tr></thead>
            <tbody>${data.professors.map((prof, index) => renderProfessorRow(prof, index)).join("")}</tbody>
          </table>
        </div>
        ${renderUnassigned(data)}
      </div>
    </section>
    ${renderSchoolColorDialog(allProfessors)}
  `;
  document.querySelector("#schoolColorBtn").addEventListener("click", () => document.querySelector("#schoolColorDialog").showModal());
  document.querySelector("#scanInlineBtn").addEventListener("click", () => window.dispatchEvent(new CustomEvent("app-scan")));
  document.querySelector("#addProfessorBtn").addEventListener("click", () => openEditor("professors", null, refresh));
  bindCommonActions();
  bindSchoolColorSettings(refresh);
  bindContactFilters(refresh);
  bindProfessorActions(refresh);
}

function renderSchoolColorDialog(rows) {
  const schools = uniqueValues(rows.map((prof) => prof.school));
  const savedColors = state.settings?.schoolColors || {};
  return `
    <dialog id="schoolColorDialog" class="school-color-dialog">
      <form method="dialog" class="dialog-card">
        <div class="dialog-head">
          <div>
            <h3>学校配色</h3>
            <p>已按学校官方视觉规范预设，可使用 Hex 颜色覆盖。</p>
          </div>
          <button value="cancel" class="icon-btn" title="关闭">×</button>
        </div>
        <div class="school-color-dialog-body">
          <div class="school-color-summary">
            <span>${schools.length} 所学校</span>
            <span>颜色格式：#RRGGBB</span>
          </div>
          ${
            schools.length
              ? `<div class="school-color-grid">
                  ${schools
                    .map((school) => {
                      const preset = officialSchoolPreset(school);
                      const color = savedColors[school] || defaultSchoolColor(school);
                      const hasCustomColor = Boolean(savedColors[school]) && savedColors[school] !== defaultSchoolColor(school);
                      return `
                        <div class="school-color-item">
                          <label title="${escapeHtml(school)}">
                            <input type="color" value="${color}" data-school-color-picker="${escapeHtml(school)}" aria-label="${escapeHtml(`${school}配色`)}" />
                            <span>
                              <strong>${escapeHtml(school)}</strong>
                              <small>${escapeHtml(preset?.label || "自动配色")} · ${defaultSchoolColor(school)}</small>
                            </span>
                          </label>
                          <input class="school-hex-input" value="${color}" maxlength="7" spellcheck="false" data-school-hex="${escapeHtml(school)}" data-original-color="${color}" aria-label="${escapeHtml(`${school} Hex 颜色`)}" />
                          <button class="mini school-color-reset" type="button" data-school-color-reset="${escapeHtml(school)}" ${hasCustomColor ? "" : "disabled"} title="${preset ? "恢复学校官方预设色" : "恢复自动配色"}">${preset ? "官方色" : "自动"}</button>
                        </div>
                      `;
                    })
                    .join("")}
                </div>`
              : `<p class="school-color-empty">为导师填写学校后，即可在这里设置配色。</p>`
          }
        </div>
        <menu>
          <button value="cancel" class="primary">完成</button>
        </menu>
      </form>
    </dialog>
  `;
}

function renderContactFilters(rows, visibleCount) {
  const schools = uniqueValues(rows.map((prof) => prof.school));
  const statuses = uniqueValues(rows.map((prof) => prof.status || "未联系"));
  return `
    <div class="toolbar contact-filters">
      <p>${visibleCount} / ${rows.length} 位导师</p>
      <div class="filter-controls">
        <select class="mini-select" data-contact-filter="school">
          <option value="">全部学校</option>
          ${schools.map((school) => `<option value="${escapeHtml(school)}" ${contactFilters.school === school ? "selected" : ""}>${escapeHtml(school)}</option>`).join("")}
        </select>
        <select class="mini-select" data-contact-filter="status">
          <option value="">全部状态</option>
          ${statuses.map((status) => `<option value="${escapeHtml(status)}" ${contactFilters.status === status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}
        </select>
      </div>
    </div>
  `;
}

function renderProfessorRow(prof, index) {
  const firstLetter = prof.letters[0];
  const schoolColor = prof.school ? schoolColorFor(prof.school) : "";
  const rowClass = schoolColor ? "school-colored" : "";
  const rowStyle = schoolColor ? ` style="--school-color: ${schoolColor}; --school-tint: ${hexToRgba(schoolColor, 0.1)}"` : "";
  return `
    <tr class="${rowClass}"${rowStyle}>
      <td><span class="program-index">${index + 1}</span></td>
      <td><strong>${escapeHtml(prof.name)}</strong></td>
      <td>${prof.school ? `<span class="school-chip">${escapeHtml(prof.school)}</span>` : "待补充"}</td>
      <td>${escapeHtml(prof.college || "待补充")}</td>
      <td><div class="truncate direction" title="${escapeHtml(prof.direction)}">${escapeHtml(shortDirection(prof.direction || prof.note || "待补充"))}</div></td>
      <td>${renderBadge(prof.status || "未联系")}</td>
      <td><div class="actions"><button class="mini" ${firstLetter ? `data-open="${firstLetter.id}"` : "disabled"}>套磁信</button><button class="mini" data-show-papers="${escapeHtml(prof.name)}">相关文件(${prof.related.length})</button></div></td>
      <td><div class="actions">${prof.id ? `<button class="mini" data-edit-prof="${prof.id}">编辑</button><button class="mini" data-move-prof="${prof.id}" data-dir="-1">↑</button><button class="mini" data-move-prof="${prof.id}" data-dir="1">↓</button><button class="mini" data-archive-prof="${prof.id}">归档</button><button class="mini danger" data-delete-prof="${prof.id}" data-prof-name="${escapeHtml(prof.name)}">删除</button>` : `<button class="mini" data-create-prof="${escapeHtml(prof.name)}">建档</button>`}</div></td>
    </tr>
  `;
}

function uniqueValues(values) {
  return [...new Set(values.map((value) => String(value || "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));
}

function defaultSchoolColor(school) {
  const preset = officialSchoolPreset(school);
  if (preset) return preset.color;
  let hash = 0;
  for (const char of school) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
  return SCHOOL_COLOR_PALETTE[hash % SCHOOL_COLOR_PALETTE.length];
}

function officialSchoolPreset(school) {
  return SCHOOL_COLOR_PRESETS[String(school || "").trim()] || null;
}

function schoolColorFor(school) {
  return state.settings?.schoolColors?.[school] || defaultSchoolColor(school);
}

function normalizeHex(value) {
  const text = String(value || "").trim();
  const expanded = /^#?([0-9a-fA-F]{3})$/.exec(text);
  if (expanded) return `#${[...expanded[1]].map((char) => char + char).join("")}`.toUpperCase();
  const full = /^#?([0-9a-fA-F]{6})$/.exec(text);
  return full ? `#${full[1].toUpperCase()}` : "";
}

function hexToRgba(hex, alpha) {
  const value = normalizeHex(hex).slice(1);
  const channels = [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
  return `rgba(${channels.join(", ")}, ${alpha})`;
}

function bindSchoolColorSettings(refresh) {
  document.querySelectorAll("[data-school-color-picker]").forEach((picker) => {
    picker.addEventListener("input", () => {
      const input = picker.closest(".school-color-item")?.querySelector("[data-school-hex]");
      if (input) input.value = picker.value.toUpperCase();
    });
    picker.addEventListener("change", () => saveSchoolColor(picker.dataset.schoolColorPicker, picker.value, refresh));
  });
  document.querySelectorAll("[data-school-hex]").forEach((input) => {
    input.addEventListener("input", () => {
      const color = normalizeHex(input.value);
      input.classList.toggle("invalid", input.value.length >= 4 && !color);
      const picker = input.closest(".school-color-item")?.querySelector("[data-school-color-picker]");
      if (picker && color) picker.value = color;
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        input.blur();
      }
    });
    input.addEventListener("blur", () => {
      const color = normalizeHex(input.value);
      if (!color) {
        input.classList.add("invalid");
        toast("请输入有效的 Hex 颜色，例如 #5B7FA3");
        return;
      }
      input.value = color;
      if (color === normalizeHex(input.dataset.originalColor)) return;
      saveSchoolColor(input.dataset.schoolHex, color, refresh);
    });
  });
  document.querySelectorAll("[data-school-color-reset]").forEach((button) => {
    button.addEventListener("click", () => saveSchoolColor(button.dataset.schoolColorReset, "", refresh, true));
  });
}

async function saveSchoolColor(school, value, refresh, reopenDialog = true) {
  try {
    const colors = { ...(state.settings?.schoolColors || {}) };
    const color = normalizeHex(value);
    if (color) colors[school] = color;
    else delete colors[school];
    state.settings = await api("/api/settings", {
      method: "PATCH",
      body: JSON.stringify({ schoolColors: colors }),
    });
    const preset = officialSchoolPreset(school);
    toast(color ? `已保存 ${school} 的配色 ${color}` : `已恢复 ${school} 的${preset ? "官方预设色" : "自动配色"}`);
    await refresh();
    if (reopenDialog) document.querySelector("#schoolColorDialog")?.showModal();
  } catch (error) {
    toast(error.message || "学校配色保存失败");
  }
}

function renderUnassigned(data) {
  if (!data.unassigned.items.length) return "";
  return `<div class="unassigned-inline"><strong>未归类资源</strong><span>${data.unassigned.items.length} 个文件待确认归属</span><button class="mini" data-show-unassigned>查看</button></div>`;
}

function bindProfessorActions(refresh) {
  document.querySelectorAll("[data-edit-prof]").forEach((button) => {
    button.addEventListener("click", async () => {
      const data = await api("/api/professors");
      const row = data.items.find((item) => String(item.id) === String(button.dataset.editProf));
      openEditor("professors", row, refresh);
    });
  });
  document.querySelectorAll("[data-show-papers]").forEach((button) => {
    button.addEventListener("click", () => {
      const prof = state.contactData.professors.find((item) => item.name === button.dataset.showPapers);
      openPapersDialog(`${prof.name}的相关文件`, prof.related, false, refresh);
    });
  });
  document.querySelectorAll("[data-show-unassigned]").forEach((button) => button.addEventListener("click", () => openPapersDialog("未归类套磁资源", state.contactData.unassigned.items, true, refresh)));
  document.querySelectorAll("[data-create-prof]").forEach((button) => button.addEventListener("click", () => createProfessorRecord(button.dataset.createProf, refresh)));
  document.querySelectorAll("[data-move-prof]").forEach((button) => button.addEventListener("click", () => moveProfessor(Number(button.dataset.moveProf), Number(button.dataset.dir), refresh)));
  document.querySelectorAll("[data-archive-prof]").forEach((button) => button.addEventListener("click", () => archiveProfessor(Number(button.dataset.archiveProf), refresh)));
  document.querySelectorAll("[data-delete-prof]").forEach((button) => button.addEventListener("click", () => deleteProfessor(Number(button.dataset.deleteProf), button.dataset.profName, refresh)));
}

function bindContactFilters(refresh) {
  document.querySelectorAll("[data-contact-filter]").forEach((select) => {
    select.addEventListener("change", () => {
      contactFilters[select.dataset.contactFilter] = select.value;
      refresh();
    });
  });
}

async function createProfessorRecord(name, refresh) {
  const row = await api("/api/professors", {
    method: "POST",
    body: JSON.stringify({ name, status: "待补充", note: `由套磁信文件名自动识别：${name}` }),
  });
  toast("已建立导师记录");
  openEditor("professors", row, refresh);
}

async function moveProfessor(id, dir, refresh) {
  await api(`/api/professors/${id}/move`, { method: "POST", body: JSON.stringify({ direction: dir }) });
  refresh();
}

async function archiveProfessor(id, refresh) {
  if (!confirm("确定归档这位导师吗？归档后将从套磁页隐藏，可在数据库中保留记录。")) return;
  await api(`/api/professors/${id}`, { method: "PATCH", body: JSON.stringify({ status: "已归档" }) });
  toast("已归档导师");
  refresh();
}

async function deleteProfessor(id, name, refresh) {
  if (!confirm(`确定删除导师记录吗？\n\n${name}\n\n这不会删除本地文件，但会清空这些文件上的导师关联。`)) return;
  await api(`/api/professors/${id}`, { method: "DELETE" });
  toast("已删除导师记录");
  refresh();
}
