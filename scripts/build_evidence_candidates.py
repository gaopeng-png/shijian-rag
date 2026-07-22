from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.config import ROOT_DIR

ACCESSED_AT = "2026-07-22"
LICENSE_NOTE = "仅保存引用元数据和定位信息，不转载受版权保护的正文。"


def source(
    source_id: str,
    title: str,
    publisher: str,
    url: str,
    source_type: str,
    authority_level: str,
    language: str = "zh-CN",
) -> dict[str, str]:
    return {
        "source_id": source_id,
        "title": title,
        "publisher": publisher,
        "url": url,
        "source_type": source_type,
        "authority_level": authority_level,
        "language": language,
        "accessed_at": ACCESSED_AT,
        "license_note": LICENSE_NOTE,
    }


SOURCES = [
    source(
        "pep-china-ancient",
        "义务教育课程标准实验教科书·历史与社会（官方教材目录）",
        "人民教育出版社",
        "https://www.pep.com.cn/products/jc/czjks/201510/t20151026_1250699.shtml",
        "official_textbook_portal",
        "B",
    ),
    source(
        "pep-china-modern",
        "中国历史教材编写与教学研究（人民教育出版社）",
        "人民教育出版社",
        "https://www.pep.com.cn/kcs/yjcg/lw/lw2017/201811/t20181113_1933284.html",
        "official_textbook_portal",
        "B",
    ),
    source(
        "pep-world-history",
        "义务教育教科书世界历史教学资源（官方教材平台）",
        "人民教育出版社",
        "https://bp.pep.com.cn/2018qiu/czls2018/",
        "official_textbook_portal",
        "B",
    ),
    source(
        "npc-early-china",
        "中华文明起源与早期发展综合研究",
        "全国人民代表大会",
        "https://www.npc.gov.cn/npc/c2/c30834/202309/t20230901_431407.html",
        "government",
        "A",
    ),
    source(
        "gov-china-modern",
        "近代史",
        "中央人民政府驻香港特别行政区联络办公室（来源：中国政府网）",
        "https://www.locpg.gov.cn/zggq/2014-01/04/c_125956421.htm",
        "government",
        "A",
    ),
    source(
        "mfa-hong-kong-history",
        "中国政府恢复对香港行使主权",
        "中华人民共和国外交部",
        "https://www.mfa.gov.cn/ziliao_674904/wjs_674919/200011/t20001107_7950073.shtml",
        "government",
        "A",
    ),
    source(
        "beijing-xinhai-110",
        "在纪念辛亥革命110周年大会上的讲话",
        "北京市人民政府（新华社稿）",
        "https://www.beijing.gov.cn/ywdt/zyldhd/202110/t20211010_2509326.html",
        "government",
        "A",
    ),
    source(
        "martyrs-may-fourth",
        "五四运动简介",
        "中华英烈网（共产党员网供稿）",
        "https://www.chinamartyrs.gov.cn/wusi/wusiyundongjianjie/202404/t20240424_414845.html",
        "government",
        "A",
    ),
    source(
        "miit-cpc-founded",
        "中国共产党的成立",
        "中华人民共和国工业和信息化部",
        "https://www.miit.gov.cn/ztzl/rdzt/dsxxjyzl/xxzl/art/2021/art_c8df6017406d44899aae3bbf18bb115a.html",
        "government",
        "A",
    ),
    source(
        "nanjing-archives-massacre",
        "南京市档案馆馆藏：侵华日军南京大屠杀档案",
        "南京市档案馆",
        "https://dag.nanjing.gov.cn/daggk/gzjs/",
        "archive",
        "A",
    ),
    source(
        "mod-war-victory",
        "中国人民抗日战争胜利纪念日",
        "中华人民共和国国防部",
        "https://www.mod.gov.cn/gfbw/gfjy_index/js_214151/4856045.html",
        "government",
        "A",
    ),
    source(
        "gov-china-modern-era",
        "现代史",
        "中国政府网",
        "https://www.locpg.gov.cn/zggq/2014-01/04/c_125956423.htm",
        "government",
        "A",
    ),
    source(
        "stats-reform-opening",
        "改革开放30年报告之一：大改革 大开放 大发展",
        "国家统计局",
        "https://www.stats.gov.cn/zt_18555/ztfx/jnggkf30n/202303/t20230301_1920460.html",
        "government",
        "A",
    ),
    source(
        "met-renaissance",
        "The Renaissance in Italy and Spain",
        "The Metropolitan Museum of Art",
        "https://www.metmuseum.org/met-publications/the-metropolitan-museum-of-art-vol-4-the-renaissance-in-italy-and-spain",
        "museum",
        "A",
        "en",
    ),
    source(
        "loc-columbus-1492",
        "Columbus and the Taíno — Exploring the Early Americas",
        "Library of Congress",
        "https://www.loc.gov/exhibits/exploring-the-early-americas/columbus-and-the-taino.html",
        "archive",
        "A",
        "en",
    ),
    source(
        "britannica-french-revolution",
        "French Revolution",
        "Encyclopaedia Britannica",
        "https://www.britannica.com/event/French-Revolution",
        "authoritative_encyclopedia",
        "B",
        "en",
    ),
    source(
        "science-museum-industrial-revolution",
        "The impacts on health of the Industrial Revolution",
        "Science Museum Group",
        "https://www.sciencemuseum.org.uk/objects-and-stories/health-safety-and-welfare-work",
        "museum",
        "A",
        "en",
    ),
    source(
        "nara-declaration",
        "America's Founding Documents: Declaration of Independence",
        "U.S. National Archives",
        "https://www.archives.gov/founding-docs/declaration",
        "archive",
        "A",
        "en",
    ),
    source(
        "iwm-ww1-outbreak",
        "How The World Went To War In 1914",
        "Imperial War Museums",
        "https://www.iwm.org.uk/history/how-the-world-went-to-war-in-1914",
        "museum",
        "A",
        "en",
    ),
    source(
        "iwm-ww2-ended",
        "1945: A momentous year",
        "Imperial War Museums",
        "https://www.iwm.org.uk/history/1945-a-momentous-year",
        "museum",
        "A",
        "en",
    ),
    source(
        "loc-russian-revolution",
        "The Russian revolution (1917 primary-source collection item)",
        "Library of Congress",
        "https://www.loc.gov/item/17023073/",
        "archive",
        "A",
        "en",
    ),
    source(
        "un-founding-history",
        "History of the United Nations",
        "United Nations",
        "https://www.un.org/en/about-us/history-of-the-un",
        "international_organization",
        "A",
        "en",
    ),
]

SECONDARY_BY_NAME = {
    "秦统一六国": "npc-early-china",
    "鸦片战争": "gov-china-modern",
    "南京条约签订": "mfa-hong-kong-history",
    "甲午中日战争": "gov-china-modern",
    "辛亥革命": "beijing-xinhai-110",
    "五四运动": "martyrs-may-fourth",
    "中国共产党成立": "miit-cpc-founded",
    "南京大屠杀": "nanjing-archives-massacre",
    "抗日战争胜利": "mod-war-victory",
    "中华人民共和国成立": "gov-china-modern-era",
    "改革开放": "stats-reform-opening",
    "文艺复兴": "met-renaissance",
    "哥伦布到达美洲": "loc-columbus-1492",
    "法国大革命": "britannica-french-revolution",
    "工业革命": "science-museum-industrial-revolution",
    "美国独立宣言发表": "nara-declaration",
    "第一次世界大战爆发": "iwm-ww1-outbreak",
    "第二次世界大战结束": "iwm-ww2-ended",
    "俄国十月革命": "loc-russian-revolution",
    "联合国成立": "un-founding-history",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-required evidence candidates")
    parser.add_argument("--events", type=Path, default=ROOT_DIR / "data" / "history_events.jsonl")
    parser.add_argument("--sources", type=Path, default=ROOT_DIR / "data" / "sources.jsonl")
    parser.add_argument(
        "--evidence",
        type=Path,
        default=ROOT_DIR / "data" / "event_evidence.jsonl",
    )
    return parser.parse_args()


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    events = [
        json.loads(line)
        for line in args.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    evidence: list[dict[str, object]] = []
    for event in events:
        if event["scope"] == "世界史":
            base_id = "pep-world-history"
        elif int(event["year"]) < 1840:
            base_id = "pep-china-ancient"
        else:
            base_id = "pep-china-modern"
        source_ids = [base_id]
        secondary = SECONDARY_BY_NAME.get(event["name"])
        if secondary and secondary not in source_ids:
            source_ids.append(secondary)
        evidence.append(
            {
                "event_id": event["id"],
                "sources": [
                    {"source_id": source_id, "locator": "待人工核对具体章节或段落"}
                    for source_id in source_ids
                ],
                "claim_sources": {
                    field: source_ids
                    for field in ("summary", "detail", "influence", "exam_points")
                },
                "memory_tip_provenance": "project_original",
                "reviewer_id": "",
                "reviewed_at": "",
                "status": "candidate",
                "notes": "自动建立的候选映射；发布为已审核证据前须逐字段核对原文与定位。",
            }
        )

    missing = sorted(set(SECONDARY_BY_NAME) - {event["name"] for event in events})
    if missing:
        raise SystemExit("priority events missing from dataset: " + ", ".join(missing))
    write_jsonl(args.sources, SOURCES)
    write_jsonl(args.evidence, evidence)
    print(
        json.dumps(
            {
                "sources": len(SOURCES),
                "events": len(evidence),
                "priority_events_with_two_sources": sum(
                    len(record["sources"]) >= 2 for record in evidence
                ),
                "status": "candidate_requires_human_review",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
