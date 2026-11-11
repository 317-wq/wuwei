# -*- coding: utf-8 -*-
"""文本清洗与字段解析的小工具。

两个爬虫框架取到的原始字符串格式略有差异（换行、不可见字符、空行数量），
统一在这里处理，保证两份 CSV 的内容可以逐字段对比。
"""

from __future__ import annotations

import re
from typing import Iterable

from common.config import IMG_ATTRS

# 不可见字符：零宽空格 / 词连接符（站点脚注编号后面就带 \u2060）
_INVISIBLE = "\u200b\u2060\ufeff"


def clean_text(value: str | None) -> str:
    """把一段单行文本压成干净的一行：去不可见字符、合并空白、去首尾空格。"""
    if not value:
        return ""
    text = str(value).replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    for ch in _INVISIBLE:
        text = text.replace(ch, "")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def clean_content(value: str | None) -> str:
    """清洗正文：按行去首尾空白、合并行内空白、丢弃连续空行（段落之间保留一个空行）。"""
    if not value:
        return ""
    text = str(value).replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")          # 段落之间保留一个空行
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def parse_comment_count(value: str | None) -> int | None:
    """从 “8 comments” / “1 comment” / “0 Comments” 里取数字；取不到返回 None。

    Disqus 对 0 条评论的处理是把占位元素写成空白，
    所以“空字符串”在这里返回 None，由调用方决定是 0 还是去调接口兜底。
    """
    if not value:
        return None
    match = re.search(r"(\d[\d,]*)", str(value))
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def pick_image_src(attributes: dict) -> str:
    """按 IMG_ATTRS 的优先级取图片真实地址（懒加载相册的图没有 src）。"""
    for name in IMG_ATTRS:
        value = attributes.get(name)
        if value:
            return value.strip()
    return ""


def unique_image_srcs(srcs: Iterable[str]) -> list[str]:
    """去重并去掉空值，保持出现顺序。"""
    seen: set[str] = set()
    result: list[str] = []
    for src in srcs:
        if not src:
            continue
        if src in seen:
            continue
        seen.add(src)
        result.append(src)
    return result


def date_to_iso(value: str | None) -> str:
    """把 '2026-11-09T00:00:00-05:00' 收敛成 '2026-11-09'。"""
    if not value:
        return ""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", str(value).strip())
    return match.group(1) if match else clean_text(value)


def strip_author_suffix(title: str, author_label: str) -> str:
    """文章页 h1 里带着 “by Janet G. '27”，把作者部分从标题尾部去掉。"""
    title = clean_text(title)
    label = clean_text(author_label)
    if label and title.endswith(label):
        title = title[: -len(label)].strip()
    return title


def normalize_for_compare(text: str) -> str:
    """对比两份结果时用：把所有空白（含换行）压成单个空格，忽略排版差异。"""
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()
