"""H3 提示词结构与压缩保护；不依赖应用启动或模型服务。"""
from __future__ import annotations

import re
from collections.abc import Awaitable, Callable


H3_BASE_FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
H3_REFERENCE_FIELDS = ("subject_definitions", "summary", "retention_analysis", "detailed_description",
                       "overall_soundscape", "non_diegetic_music")
_FIELDS = tuple(dict.fromkeys(H3_BASE_FIELDS + H3_REFERENCE_FIELDS))
_HEADINGS = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t]+)?(" + "|".join(_FIELDS) + r")[ \t]*[:：][ \t]*")
_REFERENCES = re.compile(r"<(?:Picture|Video|Audio|Subject)\s+\d+>")
_QUOTED = re.compile(r'"[^"\n]*"|“[^”]*”|「[^」]*」|『[^』]*』|‘[^’]*’|(?<!\w)\x27[^\x27\n]+\x27')


def english_narrative_error(text: str) -> bool:
    """只拦截明显的中日韩正文翻译，保留带引号的原语言对白、歌词和画面文字。"""
    narrative = _QUOTED.sub("", text)
    cjk = len(re.findall(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", narrative))
    latin = len(re.findall(r"[A-Za-z]", narrative))
    return cjk >= 20 and cjk * 3 > latin


def parse_h3_prompt(text: str) -> dict[str, str]:
    matches = list(_HEADINGS.finditer(text))
    names = [m.group(1) for m in matches]
    reference_mode = any(name in H3_REFERENCE_FIELDS[:4] for name in names)
    required = H3_REFERENCE_FIELDS if reference_mode else H3_BASE_FIELDS
    missing = [name for name in required if name not in names]
    if missing:
        raise ValueError("H3 提示词缺少必需字段：" + "、".join(missing))
    if names != list(required):
        raise ValueError("H3 提示词字段重复、顺序错误或混用了不同模式")
    sections = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        if not body:
            raise ValueError(f"H3 提示词字段 {match.group(1)} 不能为空")
        if english_narrative_error(body):
            raise ValueError(f"H3 字段 {match.group(1)} 的叙述正文应为英文；对白、歌词及画面文字可保留原语言")
        sections[match.group(1)] = body
    return sections


def render_h3_prompt(sections: dict[str, str]) -> str:
    return "\n\n".join(f"{field}:\n{body}" for field, body in sections.items())


async def compact_h3_prompt(
    text: str, limit: int, complete: Callable[[str, str], Awaitable[str]],
) -> str:
    """仅改写主要描述段；其余内容由本地保留，失败时不交付截断或丢字段的结果。"""
    sections = parse_h3_prompt(text)
    if len(text) <= limit:
        return text
    field = "detailed_description" if "detailed_description" in sections else "integrated_multimodal_description"
    fixed = {**sections, field: ""}
    budget = limit - len(render_h3_prompt(fixed))
    if budget < 100:
        raise ValueError("H3 固定字段已占满字符预算，请先精简主体定义、保留分析或声音段落")
    original_body = sections[field]
    required_tags = set(_REFERENCES.findall(original_body))
    problem = ""
    for attempt in range(2):
        target = max(80, int(budget * (0.92 if attempt == 0 else 0.82)))
        system = (
            "你是视频提示词压缩器。仅输出指定字段压缩后的英文正文，不要标题、字段名、解释或 Markdown。"
            f"只改写 {field}；正文最多 {target} 个字符，空格标点换行均计入。"
            "必须保留主体身份、动作因果、时间顺序、镜头方向、全部引用标签及否定要求。"
            "保持叙述正文为英文，不要翻译成中文；对白、歌词和画面文字保持原语言并放在引号内。"
            "原始其他字段由程序保留，禁止重写或输出它们。优先删重复描述和低优先级修饰。"
        )
        message = (f"完整提示词仅作上下文：\n{text}\n\n请只压缩 {field} 的正文。"
                   f"必须保留的引用：{' '.join(sorted(required_tags)) or '无'}。{problem}")
        body = str(await complete(system, message)).strip()
        if body.startswith("```") and body.endswith("```"):
            body = re.sub(r"^```(?:text)?\s*|\s*```$", "", body).strip()
        body = re.sub(r"^" + re.escape(field) + r"\s*[:：]\s*", "", body)
        if not body or _HEADINGS.search(body):
            problem = "上次返回了空正文或额外章节，本次只返回指定字段的正文。"
            continue
        if english_narrative_error(body):
            problem = "上次错误地翻译了叙述正文，本次必须保留英文叙述。"
            continue
        missing = required_tags - set(_REFERENCES.findall(body))
        if missing:
            problem = "上次遗漏引用：" + "、".join(sorted(missing)) + "，本次必须保留。"
            continue
        candidate = render_h3_prompt({**sections, field: body})
        if len(candidate) > limit:
            problem = f"上次正文仍超过预算 {budget} 字符，本次进一步删除重复描述。"
            continue
        parse_h3_prompt(candidate)
        return candidate
    raise ValueError("H3 提示词压缩未通过结构、语言、引用或长度校验，已停止交付不完整结果。" + problem)
