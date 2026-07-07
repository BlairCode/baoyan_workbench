import { api } from "../api.js";
import { state } from "../state.js";
import { escapeHtml } from "../utils.js";
import { openEditor, openPapersDialog, shortDirection, toast } from "../ui.js";

export async function renderContact(bindCommonActions, refresh) {
  const data = await api("/api/contact-workspace");
  const q = state.q.toLowerCase();
  data.professors = data.professors.filter((prof) => {
    const text = [prof.name, prof.school, prof.college, prof.direction, prof.status, prof.note, ...prof.letters.map((item) => item.name), ...prof.related.map((item) => item.name)].join(" ").toLowerCase();
    return !q || text.includes(q);
  });
  state.contactData = data;
  document.querySelector("#app").innerHTML = `
    <section class="panel">
      <div class="panel-head">
        <h3>导师套磁</h3>
        <div class="actions">
          <button class="secondary" id="scanInlineBtn">同步文件</button>
          <button class="primary" id="addProfessorBtn">新增导师</button>
        </div>
      </div>
      <div class="panel-body">
        <div class="table-wrap contact-table">
          <table>
            <thead><tr><th>导师</th><th>学校</th><th>学院/组</th><th>方向</th><th>状态</th><th>文件</th><th>操作</th></tr></thead>
            <tbody>${data.professors.map(renderProfessorRow).join("")}</tbody>
          </table>
        </div>
        ${renderUnassigned(data)}
      </div>
    </section>
  `;
  document.querySelector("#scanInlineBtn").addEventListener("click", () => window.dispatchEvent(new CustomEvent("app-scan")));
  document.querySelector("#addProfessorBtn").addEventListener("click", () => openEditor("professors", null, refresh));
  bindCommonActions();
  bindProfessorActions(refresh);
}

function renderProfessorRow(prof) {
  const firstLetter = prof.letters[0];
  return `
    <tr>
      <td><strong>${escapeHtml(prof.name)}</strong></td>
      <td>${escapeHtml(prof.school || "待补充")}</td>
      <td>${escapeHtml(prof.college || "待补充")}</td>
      <td><div class="truncate direction" title="${escapeHtml(prof.direction)}">${escapeHtml(shortDirection(prof.direction || prof.note || "待补充"))}</div></td>
      <td><span class="badge">${escapeHtml(prof.status || "未联系")}</span></td>
      <td><div class="actions"><button class="mini" ${firstLetter ? `data-open="${firstLetter.id}"` : "disabled"}>套磁信</button><button class="mini" data-show-papers="${escapeHtml(prof.name)}">相关文件(${prof.related.length})</button></div></td>
      <td><div class="actions"><button class="mini" data-edit-prof="${prof.id}">编辑</button><button class="mini" data-move-prof="${prof.id}" data-dir="-1">↑</button><button class="mini" data-move-prof="${prof.id}" data-dir="1">↓</button><button class="mini" data-archive-prof="${prof.id}">归档</button><button class="mini danger" data-delete-prof="${prof.id}" data-prof-name="${escapeHtml(prof.name)}">删除</button></div></td>
    </tr>
  `;
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
  document.querySelectorAll("[data-move-prof]").forEach((button) => button.addEventListener("click", () => moveProfessor(Number(button.dataset.moveProf), Number(button.dataset.dir), refresh)));
  document.querySelectorAll("[data-archive-prof]").forEach((button) => button.addEventListener("click", () => archiveProfessor(Number(button.dataset.archiveProf), refresh)));
  document.querySelectorAll("[data-delete-prof]").forEach((button) => button.addEventListener("click", () => deleteProfessor(Number(button.dataset.deleteProf), button.dataset.profName, refresh)));
}

async function moveProfessor(id, dir, refresh) {
  const profs = state.contactData.professors.filter((item) => item.id);
  const index = profs.findIndex((item) => item.id === id);
  const target = profs[index + dir];
  const current = profs[index];
  if (!target || !current) return;
  await api(`/api/professors/${current.id}`, { method: "PATCH", body: JSON.stringify({ display_order: target.display_order }) });
  await api(`/api/professors/${target.id}`, { method: "PATCH", body: JSON.stringify({ display_order: current.display_order }) });
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
