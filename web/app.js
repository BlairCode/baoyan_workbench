const state = {
  page: "dashboard",
  q: "",
  rows: {},
  contactData: null,
  resourceMode: "category",
  options: null,
};

const pages = [
  { id: "dashboard", title: "总览", icon: "总" },
  { id: "contact", title: "套磁", icon: "套" },
  { id: "resources", title: "资源", icon: "资" },
  { id: "programs", title: "院校", icon: "校" },
  { id: "tasks", title: "待办", icon: "办" },
  { id: "questions", title: "面试", icon: "面" },
];

const schemas = {
  programs: {
    title: "院校项目",
    endpoint: "/api/programs",
    columns: [
      ["school", "学校"],
      ["college", "学院/项目"],
      ["stage", "阶段"],
      ["date_text", "时间"],
      ["status", "状态"],
      ["result", "结果"],
      ["note", "备注"],
    ],
    fields: [
      { key: "school", label: "学校", required: true },
      { key: "abbreviation", label: "缩写" },
      { key: "college", label: "学院/项目" },
      { key: "stage", label: "阶段", options: ["夏令营", "预推免", "九推", "其他"] },
      { key: "date_text", label: "时间" },
      { key: "account", label: "账号" },
      { key: "password", label: "密码" },
      { key: "status", label: "状态", options: ["关注中", "准备材料", "已报名", "已入营", "已参营", "已放弃", "结束"] },
      { key: "result", label: "结果", options: ["", "待定", "入营", "优营", "候补", "未入营", "通过", "未通过"] },
      { key: "note", label: "备注", type: "textarea", full: true },
    ],
  },
  professors: {
    title: "导师",
    endpoint: "/api/professors",
    fields: [
      { key: "name", label: "姓名", required: true },
      { key: "school", label: "学校" },
      { key: "college", label: "学院/组" },
      { key: "direction", label: "研究方向", full: true },
      { key: "email", label: "邮箱" },
      { key: "homepage", label: "主页" },
      { key: "status", label: "状态", options: ["未联系", "已准备套磁信", "已发送", "已回复", "约面试", "无回复", "暂缓", "已归档"] },
      { key: "display_order", label: "排序", type: "number" },
      { key: "note", label: "备注", type: "textarea", full: true },
    ],
  },
  materials: {
    title: "文件",
    endpoint: "/api/materials",
    fields: [
      { key: "name", label: "名称", required: true },
      { key: "category", label: "归类", options: ["基本材料", "套磁", "院校", "项目", "面试", "参考"] },
      { key: "related_professor", label: "关联导师" },
      { key: "related_program", label: "关联院校" },
      { key: "path", label: "本地路径", full: true },
      { key: "note", label: "备注", type: "textarea", full: true },
      { key: "pinned", label: "置顶", options: ["0", "1"] },
    ],
  },
  tasks: {
    title: "待办",
    endpoint: "/api/tasks",
    columns: [
      ["title", "事项"],
      ["scope", "范围"],
      ["due_date", "截止"],
      ["priority", "优先级"],
      ["status", "状态"],
      ["note", "备注"],
    ],
    fields: [
      { key: "title", label: "事项", required: true, full: true },
      { key: "scope", label: "范围" },
      { key: "due_date", label: "截止日期", type: "date" },
      { key: "priority", label: "优先级", options: ["高", "中", "低"] },
      { key: "status", label: "状态", options: ["待办", "进行中", "已完成", "搁置"] },
      { key: "note", label: "备注", type: "textarea", full: true },
    ],
  },
  questions: {
    title: "面试题",
    endpoint: "/api/questions",
    columns: [
      ["topic", "主题"],
      ["question", "问题"],
      ["answer", "答案要点"],
      ["tag", "标签"],
    ],
    fields: [
      { key: "topic", label: "主题", options: ["综合", "自我介绍", "项目", "科研", "专业课", "英语", "导师"] },
      { key: "question", label: "问题", type: "textarea", required: true, full: true },
      { key: "answer", label: "答案要点", type: "textarea", full: true },
      { key: "tag", label: "标签" },
    ],
  },
};

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fileSize(size) {
  const n = Number(size || 0);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `请求失败：${response.status}`);
  return payload;
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => {
    el.hidden = true;
  }, 2800);
}

function renderNav() {
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

function setPage(page) {
  state.page = page;
  state.q = "";
  $("#searchInput").value = "";
  render();
}

async function render() {
  renderNav();
  const page = pages.find((item) => item.id === state.page);
  $("#pageTitle").textContent = page.title;
  $("#searchInput").placeholder = state.page === "dashboard" ? "搜索全部文件" : `搜索${page.title}`;
  if (state.page === "dashboard") return renderDashboard();
  if (state.page === "contact") return renderContact();
  if (state.page === "resources") return renderResources();
  return renderTablePage(state.page);
}

async function renderDashboard() {
  const data = await api("/api/summary");
  const fileResults = state.q ? await api(`/api/materials?q=${encodeURIComponent(state.q)}`) : null;
  $("#app").innerHTML = `
    <section class="stats compact-stats">
      <div class="stat"><span>夏令营报名数</span><strong>${data.counts.campApplied}/${data.counts.campTotal}</strong></div>
      <div class="stat"><span>已套磁 / 套磁信</span><strong>${data.counts.contacted}/${data.counts.totalLetters}</strong></div>
      <div class="stat"><span>未完成待办</span><strong>${data.counts.tasksOpen}</strong></div>
    </section>
    ${
      state.q
        ? `<section class="panel search-results"><div class="panel-head"><h3>全局文件搜索</h3><span class="muted">${fileResults.items.length} 个结果</span></div><div class="panel-body">${renderFileList(fileResults.items.filter((item) => !item.missing))}</div></section>`
        : ""
    }
    <section class="overview-columns">
      <div class="panel">
        <div class="panel-head"><h3>院校项目</h3><button class="secondary" data-jump="programs">管理</button></div>
        <div class="panel-body no-scroll">${renderSimpleList(data.programs, "school", "college", "status")}</div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>套磁入口</h3><button class="secondary" data-jump="contact">进入</button></div>
        <div class="panel-body no-scroll">
          <div class="list">
            <div class="list-item"><strong>导师记录</strong><p>${data.counts.professors} 位导师</p></div>
            <div class="list-item"><strong>论文归属</strong><p>${data.counts.unassignedPapers} 篇论文待归类</p></div>
            <div class="list-item"><strong>套磁信</strong><p>${data.counts.totalLetters} 份文件已索引</p></div>
          </div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>待办</h3><button class="secondary" data-jump="tasks">管理</button></div>
        <div class="panel-body no-scroll">${renderSimpleList(data.openTasks, "title", "scope", "due_date")}</div>
      </div>
    </section>
  `;
  bindCommonActions();
}

async function renderContact() {
  const data = await api("/api/contact-workspace");
  const q = state.q.toLowerCase();
  data.professors = data.professors.filter((prof) => {
    const text = [prof.name, prof.school, prof.college, prof.direction, prof.status, prof.note, ...prof.letters.map((item) => item.name), ...prof.related.map((item) => item.name)]
      .join(" ")
      .toLowerCase();
    return !q || text.includes(q);
  });
  state.contactData = data;
  $("#app").innerHTML = `
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
            <thead>
              <tr>
                <th>导师</th><th>学校</th><th>学院/组</th><th>方向</th><th>状态</th><th>文件</th><th>操作</th>
              </tr>
            </thead>
            <tbody>${data.professors.map(renderProfessorRow).join("")}</tbody>
          </table>
        </div>
        ${renderUnassigned(data)}
      </div>
    </section>
  `;
  $("#scanInlineBtn").addEventListener("click", scanMaterials);
  $("#addProfessorBtn").addEventListener("click", () => openEditor("professors"));
  bindCommonActions();
  bindProfessorActions();
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
      <td>
        <div class="actions">
          <button class="mini" ${firstLetter ? `data-open="${firstLetter.id}"` : "disabled"}>套磁信</button>
          <button class="mini" data-show-papers="${escapeHtml(prof.name)}">相关文件(${prof.related.length})</button>
        </div>
      </td>
      <td>
        <div class="actions">
          <button class="mini" data-edit-prof="${prof.id}">编辑</button>
          <button class="mini" data-move-prof="${prof.id}" data-dir="-1">↑</button>
          <button class="mini" data-move-prof="${prof.id}" data-dir="1">↓</button>
          <button class="mini" data-archive-prof="${prof.id}">归档</button>
          <button class="mini danger" data-delete-prof="${prof.id}" data-prof-name="${escapeHtml(prof.name)}">删除</button>
        </div>
      </td>
    </tr>
  `;
}

function renderUnassigned(data) {
  if (!data.unassigned.items.length) return "";
  return `
    <div class="unassigned-inline">
      <strong>未归类资源</strong>
      <span>${data.unassigned.items.length} 个文件待确认归属</span>
      <button class="mini" data-show-unassigned>查看</button>
    </div>
  `;
}

function openPapersDialog(title, rows, allowAssign = false) {
  $("#papersTitle").textContent = title;
  $("#papersList").innerHTML = rows.length
    ? `<div class="file-list">${rows
        .map(
          (row) => `
            <div class="file-item">
              <div class="file-main"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(row.relative_path)} · ${fileSize(row.size)}</span></div>
              <div class="actions">
                ${fileButtons(row)}
                ${allowAssign ? `${professorAssignSelect(row.id)}<button class="mini" data-remove-contact="${row.id}">移出套磁</button>` : `<button class="mini" data-edit-material="${row.id}">归类</button>`}
              </div>
            </div>
          `,
        )
        .join("")}</div>`
    : `<div class="empty">暂无相关文件。</div>`;
  bindCommonActions();
  bindAssignActions();
  $("#papersDialog").showModal();
}

function professorAssignSelect(id) {
  return `
    <select class="mini-select" data-assign-paper="${id}">
      <option value="">归到导师...</option>
      ${state.contactData.professors.map((prof) => `<option value="${escapeHtml(prof.name)}">${escapeHtml(prof.name)}</option>`).join("")}
    </select>
  `;
}

async function renderResources() {
  const data = await api("/api/materials/groups");
  const q = state.q.toLowerCase();
  const groups = data.byFolder
    .map((group) => ({
      ...group,
      items: group.items.filter((item) =>
        [item.name, item.relative_path, item.category, item.resource_kind, item.related_professor, item.related_program, item.note]
          .join(" ")
          .toLowerCase()
          .includes(q),
      ),
    }))
    .filter((group) => !q || group.items.length);
  $("#app").innerHTML = `
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
  $("#scanInlineBtn").addEventListener("click", scanMaterials);
  $("#uploadInput").addEventListener("change", uploadFile);
  $("#expandFoldersBtn").addEventListener("click", () => setFoldersOpen(true));
  $("#collapseFoldersBtn").addEventListener("click", () => setFoldersOpen(false));
  bindCommonActions();
}

function renderResourceGroup(group) {
  return `
    <details class="folder">
      <summary>
        <span>${escapeHtml(group.name)}</span>
        <span class="folder-summary-actions"><strong>${group.items.length}</strong><button class="mini" data-open-folder-path="${escapeHtml(group.path)}">打开文件夹</button></span>
      </summary>
      <div class="folder-body">${renderFileList(group.items)}</div>
    </details>
  `;
}

async function renderTablePage(page) {
  const schema = schemas[page];
  const data = await api(`${schema.endpoint}${state.q ? `?q=${encodeURIComponent(state.q)}` : ""}`);
  state.rows[page] = data.items;
  $("#app").innerHTML = `
    <section class="panel">
      <div class="panel-head"><h3>${schema.title}</h3><button class="primary" id="addBtn">新增</button></div>
      <div class="panel-body">
        <div class="toolbar"><p>${data.items.length} 条记录</p></div>
        ${renderTable(page, data.items)}
      </div>
    </section>
  `;
  $("#addBtn").addEventListener("click", () => openEditor(page));
  bindTableActions(page);
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
                  <td><div class="actions">${page === "programs" ? `<button class="mini" data-show-program-files="${escapeHtml(row.school)}">相关文件</button>` : ""}<button class="mini" data-action="edit" data-page="${page}" data-id="${row.id}">编辑</button><button class="mini danger" data-action="delete" data-page="${page}" data-id="${row.id}">删除</button></div></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function formatCell(key, row) {
  const value = row[key] ?? "";
  if (key === "status") return `<span class="badge">${escapeHtml(value || "未填写")}</span>`;
  if (key === "priority") return `<span class="badge ${value === "高" ? "hot" : ""}">${escapeHtml(value)}</span>`;
  if (["note", "answer", "question"].includes(key)) return `<div class="truncate" title="${escapeHtml(value)}">${escapeHtml(value)}</div>`;
  return escapeHtml(value);
}

function renderFileList(rows) {
  if (!rows.length) return `<div class="empty small">暂无文件</div>`;
  return `
    <div class="file-list">
      ${rows
        .map(
          (row) => `
            <div class="file-item ${row.missing ? "missing" : ""}">
              <div class="file-main">
                <strong title="${escapeHtml(row.relative_path || row.path)}">${escapeHtml(row.name)}</strong>
                <span>${escapeHtml(row.category || row.resource_kind)} · ${fileSize(row.size)}${row.related_professor ? ` · ${escapeHtml(row.related_professor)}` : ""}${row.related_program ? ` · ${escapeHtml(row.related_program)}` : ""}</span>
                ${row.note ? `<p class="file-note">${escapeHtml(row.note)}</p>` : ""}
              </div>
              <div class="actions">${fileButtons(row)}<button class="mini" data-edit-material="${row.id}">归类</button><button class="mini danger" data-delete-file="${row.id}" data-file-name="${escapeHtml(row.name)}">删除文件</button></div>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function fileButtons(row) {
  return `
    <button class="mini" data-open="${row.id}">打开</button>
    ${row.actions?.canPreview ? `<a class="mini link-btn" href="${row.actions.viewUrl}" target="_blank">预览</a>` : ""}
  `;
}

function setFoldersOpen(open) {
  document.querySelectorAll(".folder").forEach((folder) => {
    folder.open = open;
  });
}

function renderSimpleList(rows, titleKey, subKey, metaKey) {
  if (!rows.length) return `<div class="empty">暂无记录。</div>`;
  return `
    <div class="list compact-list">
      ${rows
        .slice(0, 6)
        .map((row) => `<div class="list-item"><strong>${escapeHtml(row[titleKey])}</strong><p>${escapeHtml(row[subKey] || "未填写")} · ${escapeHtml(row[metaKey] || "待补充")}</p></div>`)
        .join("")}
    </div>
  `;
}

function shortDirection(value) {
  const text = String(value || "待补充").replace(/[、，,；;。.\s]+/g, " ").trim();
  if (text.length <= 10) return text;
  return `${text.slice(0, 9)}…`;
}

function bindCommonActions() {
  document.querySelectorAll("[data-jump]").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.jump)));
  document.querySelectorAll("[data-open]").forEach((button) => button.addEventListener("click", () => openMaterial(button.dataset.open)));
  document.querySelectorAll("[data-open-folder-path]").forEach((button) =>
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openFolderPath(button.dataset.openFolderPath);
    }),
  );
  document.querySelectorAll("[data-delete-file]").forEach((button) => button.addEventListener("click", () => deleteFile(button.dataset.deleteFile, button.dataset.fileName)));
  document.querySelectorAll("[data-edit-material]").forEach((button) => {
    button.addEventListener("click", async () => {
      const data = await api("/api/materials");
      const row = data.items.find((item) => String(item.id) === String(button.dataset.editMaterial));
      if (!row) return toast("没有找到这条文件记录，请先同步文件");
      openEditor("materials", row);
    });
  });
}

function bindProfessorActions() {
  document.querySelectorAll("[data-edit-prof]").forEach((button) => {
    button.addEventListener("click", async () => {
      const data = await api("/api/professors");
      const row = data.items.find((item) => String(item.id) === String(button.dataset.editProf));
      openEditor("professors", row);
    });
  });
  document.querySelectorAll("[data-show-papers]").forEach((button) => {
    button.addEventListener("click", () => {
      const prof = state.contactData.professors.find((item) => item.name === button.dataset.showPapers);
      openPapersDialog(`${prof.name}的相关文件`, prof.related);
    });
  });
  document.querySelectorAll("[data-show-unassigned]").forEach((button) => {
    button.addEventListener("click", () => openPapersDialog("未归类套磁资源", state.contactData.unassigned.items, true));
  });
  document.querySelectorAll("[data-move-prof]").forEach((button) => {
    button.addEventListener("click", () => moveProfessor(Number(button.dataset.moveProf), Number(button.dataset.dir)));
  });
  document.querySelectorAll("[data-archive-prof]").forEach((button) => {
    button.addEventListener("click", () => archiveProfessor(Number(button.dataset.archiveProf)));
  });
  document.querySelectorAll("[data-delete-prof]").forEach((button) => {
    button.addEventListener("click", () => deleteProfessor(Number(button.dataset.deleteProf), button.dataset.profName));
  });
}

function bindAssignActions() {
  document.querySelectorAll("[data-assign-paper]").forEach((select) => {
    select.addEventListener("change", async () => {
      if (!select.value) return;
      await api(`/api/materials/${select.dataset.assignPaper}`, {
        method: "PATCH",
        body: JSON.stringify({ category: "套磁", stage: "套磁", related_professor: select.value }),
      });
      $("#papersDialog").close();
      toast(`已归类到：${select.value}`);
      renderContact();
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
      renderContact();
    });
  });
}

async function moveProfessor(id, dir) {
  const profs = state.contactData.professors.filter((item) => item.id);
  const index = profs.findIndex((item) => item.id === id);
  const target = profs[index + dir];
  const current = profs[index];
  if (!target || !current) return;
  await api(`/api/professors/${current.id}`, { method: "PATCH", body: JSON.stringify({ display_order: target.display_order }) });
  await api(`/api/professors/${target.id}`, { method: "PATCH", body: JSON.stringify({ display_order: current.display_order }) });
  renderContact();
}

async function archiveProfessor(id) {
  if (!confirm("确定归档这位导师吗？归档后将从套磁页隐藏，可在数据库中保留记录。")) return;
  await api(`/api/professors/${id}`, { method: "PATCH", body: JSON.stringify({ status: "已归档" }) });
  toast("已归档导师");
  renderContact();
}

async function deleteProfessor(id, name) {
  if (!confirm(`确定删除导师记录吗？\n\n${name}\n\n这不会删除本地文件，但会清空这些文件上的导师关联。`)) return;
  await api(`/api/professors/${id}`, { method: "DELETE" });
  toast("已删除导师记录");
  renderContact();
}

function bindTableActions(page) {
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.id;
      const targetPage = button.dataset.page;
      if (button.dataset.action === "edit") {
        const row = state.rows[targetPage].find((item) => String(item.id) === String(id));
        openEditor(targetPage, row);
      }
      if (button.dataset.action === "delete") {
        if (!confirm("确定删除这条网页记录吗？本地文件不会被删除。")) return;
        await api(`${schemas[targetPage].endpoint}/${id}`, { method: "DELETE" });
        toast("已删除记录");
        render();
      }
    });
  });
  document.querySelectorAll("[data-show-program-files]").forEach((button) => {
    button.addEventListener("click", () => openProgramFiles(button.dataset.showProgramFiles));
  });
}

async function openProgramFiles(programName) {
  const data = await api("/api/materials");
  const rows = data.items.filter((item) => !item.missing && item.related_program === programName);
  openPapersDialog(`${programName}的相关文件`, rows);
}

async function ensureOptions() {
  if (!state.options) {
    state.options = await api("/api/options");
  }
  return state.options;
}

async function openEditor(page, row = null) {
  const schema = schemas[page];
  if (page === "materials") {
    const options = await ensureOptions();
    schema.fields = schema.fields.map((field) => {
      if (field.key === "category") return { ...field, options: options.categories };
      if (field.key === "related_professor") return { ...field, options: ["", ...options.professors] };
      if (field.key === "related_program") return { ...field, options: ["", ...options.programs] };
      return field;
    });
  }
  const dialog = $("#editor");
  $("#editorTitle").textContent = row ? `归类${schema.title}` : `新增${schema.title}`;
  $("#editorFields").innerHTML = schema.fields.map((field) => renderField(field, row)).join("");
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
    render();
  };
  dialog.showModal();
}

function normalizeMaterialPayload(payload) {
  const stageMap = {
    基本材料: "通用",
    套磁: "套磁",
    院校: "夏令营",
    项目: "科研",
    面试: "面试",
    参考: "通用",
  };
  payload.stage = stageMap[payload.category] || "通用";
  if (payload.category !== "套磁") payload.related_professor = "";
  if (payload.category !== "院校") payload.related_program = "";
  if (!payload.resource_kind) payload.resource_kind = payload.category || "参考";
}

function renderField(field, row) {
  const value = row?.[field.key] ?? "";
  const full = field.full || field.type === "textarea" ? " full" : "";
  let control = "";
  if (field.options) {
    const options = [...field.options];
    if (value && !options.includes(value)) options.push(value);
    control = `<select name="${field.key}">${options.map((option) => `<option value="${escapeHtml(option)}" ${String(value) === String(option) ? "selected" : ""}>${escapeHtml(option || "未设置")}</option>`).join("")}</select>`;
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

async function openMaterial(id) {
  await api(`/api/materials/${id}/open`, { method: "POST" });
  toast("已调用本机默认程序打开文件");
}

async function openFolder(id) {
  await api(`/api/materials/${id}/open-folder`, { method: "POST" });
  toast("已打开所在文件夹");
}

async function openFolderPath(path) {
  await api("/api/folders/open", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
  toast("已打开文件夹");
}

async function deleteFile(id, name) {
  if (!confirm(`确定删除本地文件吗？\n\n${name}\n\n此操作会直接删除文件。`)) return;
  await api(`/api/materials/${id}/file`, { method: "DELETE" });
  toast("已删除本地文件");
  render();
}

async function scanMaterials() {
  const data = await api("/api/materials/scan", { method: "POST" });
  toast(`同步完成：新增 ${data.inserted}，更新 ${data.updated}，缺失 ${data.missing}`);
  render();
}

async function uploadFile(event) {
  const file = event.target.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/api/materials/upload", { method: "POST", body: form });
  const data = await response.json();
  if (!response.ok) return toast(data.error || "上传失败");
  toast(`已添加：${file.name}`);
  renderResources();
}

async function backupData() {
  const data = await api("/api/backup", { method: "POST" });
  toast(`备份完成：${data.path}`);
}

$("#scanBtn").addEventListener("click", scanMaterials);
$("#backupBtn").addEventListener("click", backupData);
let searchTimer = null;
$("#searchInput").addEventListener("input", (event) => {
  window.clearTimeout(searchTimer);
  state.q = event.target.value.trim();
  searchTimer = window.setTimeout(() => {
    render();
  }, 160);
});

render().catch((error) => {
  console.error(error);
  toast(error.message);
});
