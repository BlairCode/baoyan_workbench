from __future__ import annotations

RESOURCE_CATEGORIES = ["基本材料", "套磁", "院校", "项目", "面试", "参考"]
RESOURCE_STAGE_BY_CATEGORY = {
    "基本材料": "通用",
    "套磁": "套磁",
    "院校": "夏令营",
    "项目": "科研",
    "面试": "面试",
    "参考": "通用",
}

PROGRAM_STAGES = ["夏令营", "预推免", "九推", "统考复试", "其他"]
PROGRAM_STATUSES = [
    "关注中",
    "准备材料",
    "已报名",
    "已入营",
    "已参营",
    "候补",
    "优营",
    "通过",
    "未入营",
    "未通过",
    "已放弃",
]
PROGRAM_STATUS_RANK = {
    "优营": 10,
    "通过": 20,
    "已入营": 30,
    "已参营": 40,
    "候补": 50,
    "已报名": 60,
    "准备材料": 80,
    "关注中": 90,
    "已放弃": 100,
    "未入营": 110,
    "未通过": 120,
}
PROGRAM_INTEREST_STATUSES = set(PROGRAM_STATUSES)
PROGRAM_APPLIED_STATUSES = {"已报名", "已入营", "已参营", "候补", "优营", "通过", "已放弃"}
PROGRAM_ADMITTED_STATUSES = PROGRAM_APPLIED_STATUSES - {"已报名"}
PROGRAM_EXCELLENT_STATUSES = {"优营", "通过"}
PROGRAM_NEGATIVE_STATUSES = {"未入营", "未通过", "已放弃"}

PROFESSOR_STATUSES = [
    "未联系",
    "已准备套磁信",
    "已发送",
    "官回",
    "养鱼",
    "已回复",
    "约面试",
    "面试通过",
    "无回复",
    "默拒",
    "拒绝",
    "暂缓",
    "已归档",
]
CONTACTED_PROFESSOR_STATUSES = {"已发送", "官回", "养鱼", "已回复", "约面试", "面试通过", "无回复", "默拒", "拒绝"}
REPLIED_PROFESSOR_STATUSES = {"官回", "养鱼", "已回复", "约面试", "面试通过", "拒绝", "暂缓"}

TASK_PRIORITIES = ["高", "中", "低"]
TASK_STATUSES = ["待办", "进行中", "已完成", "搁置"]
QUESTION_TOPICS = ["综合", "自我介绍", "项目", "科研", "专业课", "英语", "导师", "规划", "时事"]


def normalize_category(value: str) -> str:
    mapping = {
        "申请材料": "基本材料",
        "基础材料": "基本材料",
        "套磁资源": "套磁",
        "导师论文": "套磁",
        "择校参考": "院校",
        "夏令营材料": "院校",
        "科研项目": "项目",
        "项目材料": "项目",
        "面试材料": "面试",
        "参考资料": "参考",
        "其他": "参考",
    }
    return mapping.get(value or "", value or "参考")


def default_stage_for_category(category: str) -> str:
    return RESOURCE_STAGE_BY_CATEGORY.get(category, "通用")


def program_status_rank(status: str) -> int:
    return PROGRAM_STATUS_RANK.get(status or "", 95)
