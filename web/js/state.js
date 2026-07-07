export const state = {
  page: "dashboard",
  q: "",
  rows: {},
  contactData: null,
  resourceMode: "folder",
  options: null,
  settings: null,
};

export const pages = [
  { id: "dashboard", title: "总览", icon: "总" },
  { id: "contact", title: "套磁", icon: "套" },
  { id: "resources", title: "资源", icon: "资" },
  { id: "programs", title: "院校", icon: "校" },
  { id: "tasks", title: "待办", icon: "办" },
  { id: "questions", title: "面试", icon: "面" },
];
