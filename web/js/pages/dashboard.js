import { api } from "../api.js";
import { renderFileList } from "../files.js";
import { state } from "../state.js";
import { escapeHtml, percent } from "../utils.js";
import { statusColor } from "../status-colors.js";

export async function renderDashboard(bindCommonActions) {
  const data = await api("/api/summary");
  const fileResults = state.q ? await api(`/api/materials?q=${encodeURIComponent(state.q)}&limit=100`) : null;
  const c = data.counts;
  document.querySelector("#app").innerHTML = `
    <section class="screen-hero">
      <div>
        <p class="eyebrow">Application Command Center</p>
        <h3>推免进度数据大屏</h3>
      </div>
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
      ${piePanel("院校状态占比", data.programStatus, "programs", "管理院校")}
      ${piePanel("套磁状态占比", data.professorStatus, "contact", "进入套磁")}
    </section>
    <section class="motto-banner"><p>${escapeHtml(state.settings?.motto || "金鳞岂是池中物，一遇风云便化龙")}</p></section>
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

function piePanel(title, rows, page, actionText) {
  return `
    <div class="panel data-panel pie-panel">
      <div class="panel-head"><h3>${title}</h3><button class="secondary" data-jump="${page}">${actionText}</button></div>
      <div class="panel-body">${pieChart(rows)}</div>
    </div>
  `;
}

function pieChart(rows) {
  if (!rows.length) return `<div class="empty small">暂无数据</div>`;
  const total = rows.reduce((sum, item) => sum + Number(item.count || 0), 0);
  let cursor = 0;
  const segments = rows
    .map((item, index) => {
      const value = Number(item.count || 0);
      const start = cursor;
      cursor += total ? (value / total) * 100 : 0;
      return `${statusColor(item.name, index)} ${start}% ${cursor}%`;
    })
    .join(", ");
  return `
    <div class="pie-layout">
      <div class="pie-visual" style="background: conic-gradient(${segments || "#e7eef2 0 100%"});">
        <span>${total}</span>
      </div>
      <div class="pie-legend">
        ${rows
        .map(
          (item, index) => `
            <div class="pie-row">
              <i style="background:${statusColor(item.name, index)}"></i>
              <span title="${escapeHtml(item.name || "未填写")}">${escapeHtml(item.name || "未填写")}</span>
              <b>${item.count}</b>
              <em>${total ? Math.round((Number(item.count || 0) / total) * 100) : 0}%</em>
            </div>
          `,
        )
        .join("")}
      </div>
    </div>
  `;
}
