import { api } from "../api.js";
import { schemas } from "../schemas.js";
import { state } from "../state.js";
import { escapeHtml } from "../utils.js";
import { openEditor, openPapersDialog, renderBadge, toast } from "../ui.js";

const programFilters = {
  status: "",
};

export async function renderTablePage(page, bindCommonActions, refresh) {
  const schema = schemas[page];
  const data = await api(`${schema.endpoint}${state.q ? `?q=${encodeURIComponent(state.q)}` : ""}`);
  const allItems = data.items;
  const items = page === "programs" ? allItems.filter((row) => !programFilters.status || row.status === programFilters.status) : allItems;
  state.rows[page] = items;
  document.querySelector("#app").innerHTML = `
    <section class="panel">
      <div class="panel-head"><h3>${schema.title}</h3><button class="primary" id="addBtn">新增</button></div>
      <div class="panel-body">
        ${page === "programs" ? renderProgramFilters(allItems, items.length) : `<div class="toolbar"><p>${items.length} 条记录</p></div>`}
        ${renderTable(page, items)}
      </div>
    </section>
  `;
  document.querySelector("#addBtn").addEventListener("click", () => openEditor(page, null, refresh));
  bindProgramFilters(page, refresh);
  bindTableActions(page, refresh);
  bindCommonActions();
}

function renderProgramFilters(rows, visibleCount) {
  const statuses = uniqueValues(rows.map((row) => row.status || "未填写"));
  return `
    <div class="toolbar program-filters">
      <p>${visibleCount} / ${rows.length} 条记录</p>
      <div class="filter-controls">
        <select class="mini-select" data-program-filter="status">
          <option value="">全部状态</option>
          ${statuses.map((status) => `<option value="${escapeHtml(status)}" ${programFilters.status === status ? "selected" : ""}>${escapeHtml(status)}</option>`).join("")}
        </select>
      </div>
    </div>
  `;
}

function renderTable(page, rows) {
  const schema = schemas[page];
  if (!rows.length) return `<div class="empty">暂无记录。</div>`;
  if (page === "programs") return renderPrograms(rows);
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>${schema.columns.map(([, label]) => `<th>${label}</th>`).join("")}<th>操作</th></tr></thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  ${schema.columns.map(([key]) => `<td>${formatCell(key, row)}</td>`).join("")}
                  <td><div class="actions">${programActions(page, row)}<button class="mini" data-action="edit" data-page="${page}" data-id="${row.id}">编辑</button><button class="mini danger" data-action="delete" data-page="${page}" data-id="${row.id}">删除</button></div></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderPrograms(rows) {
  return `
    <div class="program-list">
      ${rows
        .map(
          (row, index) => `
            <article class="program-row">
              <span class="program-index">${index + 1}</span>
              <strong class="program-school" title="${escapeHtml(row.school || "")}">${escapeHtml(row.school || "未填写学校")}</strong>
              <div class="program-main">
                <span title="${escapeHtml(programMeta(row))}">${escapeHtml(programMeta(row))}</span>
              </div>
              <span class="program-progress" title="${escapeHtml(programProgress(row))}">${escapeHtml(programProgress(row))}</span>
              ${renderBadge(row.status)}
              <p class="program-note-line" title="${escapeHtml(row.note || "")}">${escapeHtml(row.note || "")}</p>
              <div class="actions program-actions">${programActions("programs", row)}<button class="mini" data-action="edit" data-page="programs" data-id="${row.id}">编辑</button><button class="mini danger" data-action="delete" data-page="programs" data-id="${row.id}">删除</button></div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function programActions(page, row) {
  if (page !== "programs") return "";
  return `<button class="mini" data-move-program="${row.id}" data-dir="-1">↑</button><button class="mini" data-move-program="${row.id}" data-dir="1">↓</button><button class="mini" data-show-program-files="${escapeHtml(row.school)}">文件</button>`;
}

function uniqueValues(values) {
  return [...new Set(values.map((value) => String(value || "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));
}

function programMeta(row) {
  return compactLine([row.college, row.major, row.program_type]);
}

function compactLine(parts) {
  const text = parts.filter(Boolean).join(" · ");
  return text || "学院/专业/类型待补充";
}

function programProgress(row) {
  return compactLine([row.stage, row.date_text, row.direction ? `方向: ${shortValue(row.direction, 10)}` : ""]);
}

function shortValue(value, max = 8) {
  const text = String(value || "").trim();
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function formatCell(key, row) {
  const value = row[key] ?? "";
  if (key === "status") return renderBadge(value);
  if (key === "priority") return renderBadge(value, value === "高" ? "hot" : "");
  if (["note", "answer", "question"].includes(key)) return `<div class="truncate" title="${escapeHtml(value)}">${escapeHtml(value)}</div>`;
  return escapeHtml(value);
}

function bindTableActions(page, refresh) {
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.id;
      const targetPage = button.dataset.page;
      if (button.dataset.action === "edit") {
        const row = state.rows[targetPage].find((item) => String(item.id) === String(id));
        return openEditor(targetPage, row, refresh);
      }
      if (!confirm("确定删除这条网页记录吗？本地文件不会被删除。")) return;
      await api(`${schemas[targetPage].endpoint}/${id}`, { method: "DELETE" });
      toast("已删除记录");
      refresh();
    });
  });
  document.querySelectorAll("[data-show-program-files]").forEach((button) => button.addEventListener("click", () => openProgramFiles(button.dataset.showProgramFiles)));
  document.querySelectorAll("[data-move-program]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/programs/${button.dataset.moveProgram}/move`, { method: "POST", body: JSON.stringify({ direction: Number(button.dataset.dir) }) });
      refresh();
    });
  });
}

function bindProgramFilters(page, refresh) {
  if (page !== "programs") return;
  document.querySelectorAll("[data-program-filter]").forEach((select) => {
    select.addEventListener("change", () => {
      programFilters[select.dataset.programFilter] = select.value;
      refresh();
    });
  });
}

async function openProgramFiles(programName) {
  const data = await api("/api/materials");
  const rows = data.items.filter((item) => !item.missing && item.related_program === programName);
  openPapersDialog(`${programName}的相关文件`, rows);
}
