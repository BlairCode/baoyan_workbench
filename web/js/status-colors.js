const STATUS_COLORS = {
  "未填写": "#8793AA",
  "准备": "#7D8BA6",
  "待补充": "#7D8BA6",
  "待建档": "#7D8BA6",
  "未联系": "#7D8BA6",
  "有意向": "#5B82D8",
  "关注中": "#5877E8",
  "填报中": "#2C9E91",
  "报名": "#D58B3D",
  "入营": "#34A56F",
  "参营": "#65A94B",
  "通过": "#23875B",
  "优营": "#7C5CCF",
  "未通过": "#D95772",
  "入营放弃": "#C4774D",
  "优营放弃": "#A66B53",
  "放弃报名": "#A87655",
  "官回": "#208D88",
  "约面试": "#3A8EBB",
  "已准备套磁信": "#6F70C7",
  "已发送": "#4D85C5",
  "已回复": "#2E9D8D",
  "面试通过": "#26875D",
  "无回复": "#9A7A58",
  "默拒": "#A86A70",
  "拒绝": "#D95772",
  "暂缓": "#BB873E",
  "放弃": "#8A7C75",
  "鸽了": "#6F7480",
  "被鸽了": "#AA647B",
  "养鱼": "#718F49",
  "已归档": "#8B93A2",
  "待办": "#5877E8",
  "进行中": "#D58B3D",
  "已完成": "#23875B",
};

const FALLBACK_COLORS = ["#5877E8", "#2C9E91", "#D58B3D", "#7C5CCF", "#D26387", "#34A56F", "#C4774D", "#6F7480"];

export function statusColor(name, index = 0) {
  return STATUS_COLORS[String(name || "未填写").trim()] || FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

export function statusStyle(name) {
  const color = statusColor(name);
  return `--status-color:${color};--status-border:${color}55;--status-bg:${color}18`;
}
