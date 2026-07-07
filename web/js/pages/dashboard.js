import { api } from "../api.js";
import { renderFileList } from "../files.js";
import { state } from "../state.js";
import { escapeHtml, percent } from "../utils.js";

export async function renderDashboard(bindCommonActions) {
  const data = await api("/api/summary");
  const fileResults = state.q ? await api(`/api/materials?q=${encodeURIComponent(state.q)}`) : null;
  const c = data.counts;
  document.querySelector("#app").innerHTML = `
    <section class="screen-hero">
      <div>
        <p class="eyebrow">Application Command Center</p>
        <h3>推免进度数据大屏</h3>
      </div>
      <div class="hero-orbit" aria-hidden="true"><span></span><span></span><span></span></div>
    </section>
    <section class="metric-grid">
      ${metricCard("关注院校", c.campInterested, percent(c.campInterested, c.programs))}
      ${metricCard("入营 / 报名", `${c.campAdmitted}/${c.campApplied}`, percent(c.campAdmitted, c.campApplied))}
      ${metricCard("优营 / 通过", c.campExcellent, percent(c.campExcellent, c.campApplied))}
      ${metricCard("套磁回复 / 发送", `${c.replied}/${c.sent}`, data.rates.replyRate)}
      ${metricCard("待办", c.tasksOpen, Math.max(0, 100 - c.tasksOpen * 8))}
    </section>
    ${
      state.q
        ? `<section class="panel search-results"><div class="panel-head"><h3>全局文件搜索</h3><span class="muted">${fileResults.items.length} 个结果</span></div><div class="panel-body">${renderFileList(fileResults.items.filter((item) => !item.missing))}</div></section>`
        : ""
    }
    <section class="dashboard-grid">
      <div class="dashboard-stack">
        <div class="panel data-panel">
          <div class="panel-head"><h3>院校进度</h3><button class="secondary" data-jump="programs">管理院校</button></div>
          <div class="panel-body">${pipeline(data)}${barList(data.programStatus)}</div>
        </div>
        <div class="panel data-panel">
          <div class="panel-head"><h3>套磁状态</h3><button class="secondary" data-jump="contact">进入套磁</button></div>
          <div class="panel-body">${barList(data.contactStatus)}</div>
        </div>
      </div>
      <div class="panel data-panel recent-panel">
        <div class="panel-head"><h3>近期文件</h3></div>
        <div class="panel-body">${recentFiles(data.recentMaterials)}</div>
      </div>
    </section>
  `;
  bindCommonActions();
}

function metricCard(label, value, score) {
  const safeScore = Math.max(0, Math.min(100, Number(score || 0)));
  return `
    <div class="metric-card" style="--score:${safeScore}">
      <span>${label}</span>
      <strong>${value}</strong>
      <i aria-hidden="true"></i>
    </div>
  `;
}

function pipeline(data) {
  const c = data.counts;
  const rows = [
    ["关注", c.campInterested],
    ["报名", c.campApplied],
    ["入营", c.campAdmitted],
    ["优营", c.campExcellent],
  ];
  const max = Math.max(...rows.map(([, value]) => Number(value || 0)), 1);
  return `
    <div class="pipeline-strip">
      ${rows
        .map(
          ([label, value], index) => `
            <div class="pipeline-item" style="--delay:${index * 80}ms">
              <span>${label}</span><b>${value}</b><i style="--w:${Math.max(14, (value / max) * 100)}%"></i>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function recentFiles(rows) {
  if (!rows.length) return `<div class="empty small">暂无文件</div>`;
  return `
    <div class="recent-files">
      ${rows
        .slice(0, 9)
        .map(
          (row) => `
            <div class="recent-file">
              <strong title="${escapeHtml(row.relative_path || row.name)}">${escapeHtml(row.name)}</strong>
              ${row.actions?.canPreview ? `<a class="mini link-btn" href="${row.actions.viewUrl}" target="_blank">预览</a>` : ""}
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function barList(rows) {
  if (!rows.length) return `<div class="empty small">暂无数据</div>`;
  const max = Math.max(...rows.map((item) => Number(item.count || 0)), 1);
  return `
    <div class="bar-list">
      ${rows
        .slice(0, 8)
        .map(
          (item, index) => `
            <div class="bar-row" style="--w:${(Number(item.count || 0) / max) * 100}%; --delay:${index * 60}ms">
              <span>${escapeHtml(item.name || "未填写")}</span><b>${item.count}</b><i></i>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}
