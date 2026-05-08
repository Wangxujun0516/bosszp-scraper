#!/usr/bin/env python3
"""
BOSS 直聘 JD 分析工具
=====================
从爬取的数据中提取高频技能词汇、生成词云，并做简单的简历匹配分析。

用法:
  python analyze.py                              # 分析最新爬取的数据
  python analyze.py data/bosszp_jobs_20250101.json   # 分析指定文件
"""

import json, os, sys, re
from collections import Counter
from pathlib import Path

import jieba
import pandas as pd

try:
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt
    HAS_WORDCLOUD = True
except ImportError:
    HAS_WORDCLOUD = False

DATA_DIR = "data"

# ===== 技能词典 =====
# 自定义词库，确保 jieba 能正确切出这些专业词汇
CUSTOM_WORDS = [
    "技术文档", "技术写作", "技术传播", "信息架构",
    "API文档", "SDK文档", "用户手册", "操作指南",
    "Markdown", "reStructuredText", "Sphinx", "MkDocs",
    "API", "RESTful", "OpenAPI", "Swagger", "GraphQL",
    "Git", "GitHub", "GitLab", "SVN", "版本控制",
    "DITA", "XML", "HTML", "CSS", "JavaScript",
    "Python", "Shell", "Linux", "Docker", "Kubernetes",
    "Postman", "JMeter", "Charles", "抓包",
    "Figma", "Sketch", "Axure", "蓝湖",
    "Jira", "Confluence", "Slack", "Trello",
    "SDK", "API", "本地化", "国际化", "i18n", "l10n",
    "技术翻译", "英文文档", "中文文档", "双语",
    "内容策略", "UX写作", "UX Writing", "微文案",
    "小红书", "抖音", "微信公众号", "内容运营",
    "数据分析", "用户调研", "竞品分析",
    "全栈", "前后端", "架构设计", "微服务",
    "项目管理", "Scrum", "敏捷开发",
]

for word in CUSTOM_WORDS:
    jieba.add_word(word)

# BOSS 直聘 JD 中常见的非技能干扰词
STOP_WORDS = set("""
的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你
会 着 没有 看 好 自己 这 他 她 它 们 那 些 什么 怎么 可以 能
我们 他们 它们 这个 那个 这些 那些 因为 所以 但是 如果
需要 负责 任职 要求 工作 职责 职位 岗位 公司 加入 以上 优先
相关 经验 学历 本科 以上学历 及以上 熟悉 了解 掌握 具备
良好 较强 一定 相关经验 团队合作 沟通能力 责任心 抗压能力
优秀 熟练 使用 能够 具有 优先考虑 上班 时间 地点
""".split())

# 同义词映射（归一化用）
SYNONYM_MAP = {
    "技术文档": "技术文档",
    "技术写作": "技术写作",
    "tech writer": "技术写作",
    "technical writer": "技术写作",
    "API文档": "API文档",
    "api文档": "API文档",
    "sdk文档": "SDK文档",
    "操作手册": "用户手册",
    "使用手册": "用户手册",
    "说明文档": "用户手册",
    "git": "Git/GitHub",
    "github": "Git/GitHub",
    "gitlab": "Git/GitHub",
    "英语六级": "英语能力",
    "英语专业": "英语能力",
    "tem-8": "英语能力",
    "英语读写": "英语能力",
    "口语": "英语能力",
    "python": "Python",
    "shell": "Shell",
    "linux": "Linux",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "html": "HTML/CSS",
    "css": "HTML/CSS",
    "javascript": "JavaScript",
    "markdown": "Markdown",
    "sphinx": "文档工具",
    "gitbook": "文档工具",
    "readthedocs": "文档工具",
    "confluence": "文档工具",
    "word": "办公软件",
    "excel": "办公软件",
    "ppt": "办公软件",
    "visio": "办公软件",
}

# ===== 工具函数 =====

def log(msg):
    print(f"[分析] {msg}")


def load_data(filepath=None):
    """加载爬虫数据"""
    if filepath and os.path.exists(filepath):
        path = filepath
    else:
        # 查找最新的数据文件
        data_dir = Path(DATA_DIR)
        json_files = sorted(data_dir.glob("bosszp_jobs_*.json"), reverse=True)
        if not json_files:
            # 尝试 latest.json
            latest = data_dir / "latest.json"
            if latest.exists():
                path = str(latest)
            else:
                print(f"错误: 在 {DATA_DIR}/ 目录下没有找到数据文件")
                print("请先运行 python scraper.py 爬取数据")
                sys.exit(1)
        else:
            path = str(json_files[0])

    log(f"加载数据: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    log(f"共 {len(data)} 条记录")
    return data


# ===== 技能提取 =====

def extract_skills_from_jd(jd_text):
    """
    从职位描述文本中提取技能关键词。
    使用 jieba 分词 + 自定义词典 + 停用词过滤。
    """
    if not jd_text:
        return []

    # 小写化（用于匹配同义词）
    text_lower = jd_text.lower()

    # 第一步：精确匹配自定义词汇（应对 API、SDK 等 jieba 可能切错的词）
    matched = []
    for word in sorted(CUSTOM_WORDS, key=len, reverse=True):
        if word.lower() in text_lower:
            matched.append(word)
            # 从原文中移除已匹配的词，避免重复
            text_lower = text_lower.replace(word.lower(), "", 1)

    # 第二步：jieba 分词提取剩余关键词
    words = jieba.lcut(jd_text)
    for w in words:
        w = w.strip()
        # 过滤条件
        if len(w) < 2:
            continue
        if w in STOP_WORDS:
            continue
        if re.match(r'^[\d\W]+$', w):
            continue
        matched.append(w)

    # 第三步：同义词归一化
    normalized = []
    for w in matched:
        w_lower = w.lower()
        if w_lower in SYNONYM_MAP:
            normalized.append(SYNONYM_MAP[w_lower])
        else:
            normalized.append(w)

    return normalized


def calculate_skill_stats(jobs):
    """
    统计所有岗位中的技能频率。
    返回: (skill_counter, jobs_with_skills)
    """
    counter = Counter()
    jobs_with_tags = 0

    for job in jobs:
        skills = []

        # 从 tags/skills 字段提取
        for key in ["skills", "tags"]:
            if key in job and isinstance(job[key], list):
                for item in job[key]:
                    skills.append(item.lower().strip())

        # 如果有 JD 详情，从中提取
        jd = job.get("jd", "")
        if jd:
            skills.extend(extract_skills_from_jd(jd))

        if skills:
            jobs_with_tags += 1
            for s in set(skills):  # 去重，避免同一岗位多次计数
                counter[s] += 1

    return counter, jobs_with_tags


# ===== 词云生成 =====

def generate_wordcloud(skill_counter, output_path="data/skill_wordcloud.png"):
    """生成技能词云"""
    if not HAS_WORDCLOUD:
        log("wordcloud 库未安装，跳过词云生成")
        log("安装: pip install wordcloud matplotlib")
        return

    if not skill_counter:
        log("没有技能数据，无法生成词云")
        return

    wc = WordCloud(
        font_path="/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        width=1200,
        height=800,
        background_color="white",
        max_words=80,
        max_font_size=120,
        min_font_size=14,
        colormap="viridis",
        prefer_horizontal=0.7,
    )

    wc.generate_from_frequencies(dict(skill_counter.most_common(80)))
    wc.to_file(output_path)
    log(f"词云已保存 → {output_path}")


# ===== 数据汇总展示 =====

def print_summary(jobs, skill_counter, total_with_skills):
    """打印分析报告"""
    total = len(jobs)
    df = pd.DataFrame(jobs)

    print("\n" + "=" * 55)
    print("  BOSS 直聘岗位分析报告")
    print("=" * 55)

    # 基础统计
    print(f"\n📊 基础统计")
    print(f"  总岗位数: {total}")
    print(f"  含技能标签的岗位: {total_with_skills}/{total}")

    # 关键词分布
    if "keyword" in df.columns:
        print(f"\n🔍 关键词分布")
        kw_counts = df["keyword"].value_counts()
        for kw, count in kw_counts.items():
            print(f"  [{kw}] {count} 个岗位")

    # 薪资分布（如果有）
    if "salary" in df.columns and df["salary"].notna().any():
        print(f"\n💰 薪资范围分布（Top 10）")
        salaries = df["salary"].value_counts().head(10)
        for s, c in salaries.items():
            print(f"  {s:30s}  {c} 个岗位")

    # 技能排行榜
    print(f"\n🏆 技能需求 Top 20")
    print(f"  {'技能':20s}  {'出现次数':10s}  {'占比'}")
    print(f"  {'-'*40}")
    for skill, count in skill_counter.most_common(20):
        ratio = count / total * 100
        bar = "█" * int(ratio / 2)
        print(f"  {skill:20s}  {count:<10d}  {ratio:5.1f}%  {bar}")

    print()


# ===== 技能变化趋势（多期对比） =====

def compare_with_previous(new_jobs):
    """
    与上一次的分析结果对比，生成变化报告。
    需要 data/skill_history.json 记录历史数据。
    """
    history_file = os.path.join(DATA_DIR, "skill_history.json")
    if not os.path.exists(history_file):
        # 首次运行，保存当前数据作为基线
        return None

    with open(history_file, "r") as f:
        history = json.load(f)

    old_skills = set(history.get("top_skills", []))
    new_counter, _ = calculate_skill_stats(new_jobs)
    new_skills = set(s for s, _ in new_counter.most_common(30))

    new_appeared = new_skills - old_skills
    disappeared = old_skills - new_skills

    return {
        "new_skills": sorted(new_appeared, key=lambda x: new_counter[x], reverse=True),
        "disappeared": sorted(disappeared),
    }


def save_skill_history(jobs):
    """保存当前技能数据作为历史基线"""
    counter, _ = calculate_skill_stats(jobs)
    top_skills = [s for s, _ in counter.most_common(50)]

    history_file = os.path.join(DATA_DIR, "skill_history.json")
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump({
            "date": pd.Timestamp.now().isoformat(),
            "total_jobs": len(jobs),
            "top_skills": top_skills,
        }, f, ensure_ascii=False, indent=2)
    log(f"技能历史已保存 → {history_file}")


# ===== 主函数 =====

def main():
    import argparse

    parser = argparse.ArgumentParser(description="BOSS 直聘 JD 分析工具")
    parser.add_argument("file", nargs="?", help="数据文件路径（默认使用最新爬取的数据）")
    parser.add_argument("--no-wordcloud", action="store_true", help="跳过词云生成")
    parser.add_argument("--no-history", action="store_true", help="跳过历史对比")
    args = parser.parse_args()

    # 加载数据
    jobs = load_data(args.file)

    # 技能统计
    skill_counter, total_with_skills = calculate_skill_stats(jobs)

    # 打印报告
    print_summary(jobs, skill_counter, total_with_skills)

    # 词云
    if not args.no_wordcloud:
        generate_wordcloud(skill_counter)

    # 历史对比
    if not args.no_history:
        changes = compare_with_previous(jobs)
        if changes:
            print(f"\n📈 与上次对比")
            if changes["new_skills"]:
                print(f"  新增技能: {', '.join(changes['new_skills'][:10])}")
            if changes["disappeared"]:
                print(f"  消失技能: {', '.join(changes['disappeared'][:10])}")
        save_skill_history(jobs)


if __name__ == "__main__":
    main()
