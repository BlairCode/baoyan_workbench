import { api } from "../api.js";
import { schemas } from "../schemas.js";
import { state } from "../state.js";
import { escapeHtml } from "../utils.js";
import { openEditor, openPapersDialog, renderBadge, toast } from "../ui.js";

export async function renderTablePage(page, bindCommonActions, refresh) {
  const schema = schemas[page];
  const data = await api(`${schema.endpoint}${state.q ? `?q=${encodeURIComponent(state.q)}` : ""}`);
  state.rows[page] = data.items;
  document.querySelector("#app").innerHTML = `
    <section class="panel">
      <div class="panel-head"><h3>${schema.title}</h3><button class="primary" id="addBtn">新增</button></div>
      <div class="panel-body">
        <div class="toolbar"><p>${data.items.length} 条记录</p></div>
        ${renderTable(page, data.items)}
      </div>
    </section>
  `;
  document.querySelector("#addBtn").addEventListener("click", () => openEditor(page, null, refresh));
  bindTableActions(page, refresh);
  bindCommonActions();
}

function renderTable(page, rows) {
  const schema = schemas[page];
  if (!rows.length) return `<div class="empty">暂无记录。</div>`;
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

function programActions(page, row) {
  if (page !== "programs") return "";
  return `<button class="mini" data-move-program="${row.id}" data-dir="-1">↑</button><button class="mini" data-move-program="${row.id}" data-dir="1">↓</button><button class="mini" data-show-program-files="${escapeHtml(row.school)}">相关文件</button>`;
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

async function openProgramFiles(programName) {
  const data = await api("/api/materials");
  const rows = data.items.filter((item) => !item.missing && item.related_program === programName);
  openPapersDialog(`${programName}的相关文件`, rows);
}
