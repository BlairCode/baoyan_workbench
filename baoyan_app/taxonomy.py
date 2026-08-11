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

PROGRAM_TYPES = ["专硕", "学硕", "直博", "硕博连读", "其他"]
PROGRAM_STAGES = ["准备", "套磁", "夏令营", "开放日", "预推免", "九推", "统考复试", "其他"]
PROGRAM_STATUSES = [
    "有意向",
    "关注中",
    "填报中",
    "报名",
    "入营",
    "参营",
    "通过",
    "优营",
    "未通过",
    "入营放弃",
    "优营放弃",
    "放弃报名",
    "鸽了",
    "被鸽了",
]
PROGRAM_STATUS_RANK = {
    "优营": 10,
    "通过": 20,
    "入营": 30,
    "参营": 40,
    "报名": 60,
    "填报中": 70,
    "关注中": 90,
    "有意向": 95,
    "入营放弃": 100,
    "优营放弃": 105,
    "放弃报名": 110,
    "未通过": 120,
    "鸽了": 130,
    "被鸽了": 140,
}
PROGRAM_INTEREST_STATUSES = set(PROGRAM_STATUSES)
PROGRAM_APPLIED_STATUSES = {"报名", "入营", "参营", "优营", "通过", "未通过", "入营放弃", "优营放弃", "鸽了", "被鸽了"}
PROGRAM_ADMITTED_STATUSES = {"入营", "参营", "优营", "通过", "入营放弃", "优营放弃"}
PROGRAM_EXCELLENT_STATUSES = {"优营", "通过"}
PROGRAM_NEGATIVE_STATUSES = {"未通过", "入营放弃", "优营放弃", "放弃报名", "鸽了", "被鸽了"}

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
    "放弃",
    "鸽了",
    "被鸽了",
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
