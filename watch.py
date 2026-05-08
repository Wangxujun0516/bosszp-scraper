#!/usr/bin/env python3
"""
BOSS 直聘监看模式 — 你搜什么，它存什么
========================================
用法:
  1. python watch.py
  2. 浏览器打开，你手动登录 BOSS 直聘
  3. 正常搜索岗位（任意关键词、翻页）
  4. 脚本自动识别页面上的岗位列表，自动存到 SQLite 数据库
  5. 按 Ctrl+C 停止

数据库: bosszp.db — 包含去重，同一个岗位不会重复保存
"""

import json, os, sys, time, hashlib
from datetime import datetime
from pathlib import Path
import sqlite3

import config as cfg

# ---------- 数据库 ----------

DB_PATH = os.path.join(cfg.OUTPUT_DIR, "bosszp.db")


def init_db():
    """初始化 SQLite 数据库"""
    ensure_dir(cfg.OUTPUT_DIR)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT UNIQUE NOT NULL,   -- 去重指纹
            title TEXT,
            company TEXT,
            salary TEXT,
            location TEXT,
            tags TEXT,           -- JSON 数组
            skills TEXT,         -- JSON 数组
            url TEXT,
            keyword TEXT,        -- 搜索关键词
            city_code TEXT,
            page_url TEXT,       -- 抓取时的页面 URL
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)
    """)
    conn.commit()
    return conn


def make_fingerprint(job):
    """生成去重指纹：title + company + 取 url 哈希"""
    raw = f"{job.get('title','')}|{job.get('company','')}"
    return hashlib.md5(raw.encode()).hexdigest()


def save_to_db(conn, job):
    """存入数据库，已存在的自动跳过"""
    cursor = conn.cursor()
    fp = make_fingerprint(job)
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO jobs 
            (fingerprint, title, company, salary, location, tags, skills, url, keyword, city_code, page_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fp,
            job.get("title", ""),
            job.get("company", ""),
            job.get("salary", ""),
            job.get("location", ""),
            json.dumps(job.get("tags", []), ensure_ascii=False),
            json.dumps(job.get("skills", []), ensure_ascii=False),
            job.get("url", ""),
            job.get("keyword", ""),
            job.get("city_code", ""),
            job.get("page_url", ""),
        ))
        conn.commit()
        return cursor.rowcount > 0  # True 表示新增了
    except Exception as e:
        return False


def get_db_stats(conn):
    """获取数据库统计"""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT keyword) FROM jobs")
    keywords = cursor.fetchone()[0]
    cursor.execute("SELECT keyword, COUNT(*) as cnt FROM jobs GROUP BY keyword ORDER BY cnt DESC")
    by_keyword = cursor.fetchall()
    return total, keywords, by_keyword


# ---------- 工具 ----------

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ---------- 页面抓取 ----------

def extract_jobs_from_page(page, keyword=None):
    """
    从当前页面提取所有岗位卡片。
    返回岗位列表。
    """
    jobs = []

    # 获取当前 URL，提取关键词
    page_url = page.url
    if not keyword:
        keyword = extract_keyword_from_url(page_url)

    try:
        cards = page.query_selector_all(".job-card-wrapper")
        if not cards:
            cards = page.query_selector_all("[class*='job-card']")
    except:
        cards = []

    for card in cards:
        try:
            job = {}
            for sel, key in [
                (".job-name", "title"),
                ("[class*='job-name']", "title"),
                (".company-name", "company"),
                ("[class*='company-name']", "company"),
                (".salary", "salary"),
                ("[class*='salary']", "salary"),
                (".job-area", "location"),
                ("[class*='job-area']", "location"),
            ]:
                try:
                    el = card.query_selector(sel)
                    if el:
                        job[key] = el.inner_text().strip()
                except:
                    pass

            tags = []
            try:
                for el in card.query_selector_all(".job-limit .tag-item, [class*='tag-item']"):
                    tags.append(el.inner_text().strip())
                if tags:
                    job["tags"] = tags
            except:
                pass

            try:
                el = card.query_selector("a.job-card-left")
                if el:
                    href = el.get_attribute("href")
                    if href:
                        job["url"] = f"https://www.zhipin.com{href}" if href.startswith("/") else href
            except:
                pass

            if job.get("title"):
                job["keyword"] = keyword or "未知"
                job["page_url"] = page_url
                jobs.append(job)
        except:
            continue

    return jobs


def extract_keyword_from_url(url):
    """从 URL 中提取搜索关键词"""
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    query = params.get("query", [""])[0]
    if query:
        return urllib.parse.unquote(query)
    return "未知"


def is_search_results_page(url):
    """判断当前页面是否为岗位搜索结果页"""
    return "/web/geek/job" in url or "/web/geek/" in url and "job" in url


# ---------- 监看主循环 ----------

def watch_loop(page, conn, interval=5):
    """
    监看循环：
    - 每 interval 秒检查一次页面
    - 如果检测到岗位卡片，自动提取并保存
    """
    log("=" * 55)
    log("监看模式已启动 👀")
    log("你现在可以正常搜索 BOSS 直聘了")
    log("工具会自动识别岗位列表并保存到数据库")
    log("按 Ctrl+C 停止")
    log("=" * 55)

    last_fingerprints = set()
    capture_count = 0
    loop_count = 0
    last_stats_time = time.time()

    try:
        while True:
            loop_count += 1
            current_url = page.url

            # 每 30 秒显示一次统计
            if time.time() - last_stats_time > 30:
                total, kw_count, by_kw = get_db_stats(conn)
                log(f"📊 数据库: {total} 条岗位, {kw_count} 个关键词")
                last_stats_time = time.time()

            # 只在搜索结果页提取
            if is_search_results_page(current_url):
                keyword = extract_keyword_from_url(current_url)
                jobs = extract_jobs_from_page(page, keyword)

                if jobs:
                    new_count = 0
                    for job in jobs:
                        fp = make_fingerprint(job)
                        if fp not in last_fingerprints:
                            if save_to_db(conn, job):
                                new_count += 1
                        last_fingerprints.add(fp)

                    if new_count > 0:
                        capture_count += new_count
                        log(f"✅ 新增 {new_count} 条 — 当前页共 {len(jobs)} 条, 累计已保存 {capture_count} 条")

                    # 控制指纹集大小，避免内存膨胀
                    if len(last_fingerprints) > 5000:
                        last_fingerprints = set(list(last_fingerprints)[-1000:])

            time.sleep(interval)

    except KeyboardInterrupt:
        log("\n\n监看已停止")
        return capture_count


# ---------- 浏览器 ----------

def open_browser_and_login(playwright):
    """打开浏览器，让用户自己登录"""
    browser = playwright.chromium.launch(
        headless=False,
        timeout=cfg.BROWSER_TIMEOUT,
    )

    context = browser.new_context(
        viewport={"width": 1400, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="zh-CN",
    )

    if os.path.exists(cfg.COOKIE_FILE):
        try:
            with open(cfg.COOKIE_FILE, "r") as f:
                context.add_cookies(json.load(f))
            log(f"已加载 Cookie")
        except:
            pass

    page = context.new_page()

    log("=" * 55)
    log("浏览器已打开 👉 请完成以下操作:")
    log("  1. 打开 https://www.zhipin.com")
    log("  2. 用微信/App 扫码登录")
    log("  3. 正常搜索岗位（任意关键词）")
    log("")
    log("  ⏎ 登录完成后，按 Enter 键启动监看...")
    log("=" * 55)

    page.goto("https://www.zhipin.com/", wait_until="commit", timeout=cfg.BROWSER_TIMEOUT)
    input()

    # 保存 Cookie
    cookies = context.cookies()
    with open(cfg.COOKIE_FILE, "w") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

    return browser, page


# ---------- 主函数 ----------

def main():
    ensure_dir(cfg.OUTPUT_DIR)

    # 初始化数据库
    conn = init_db()
    total, kw_count, _ = get_db_stats(conn)
    log(f"📂 数据库: {DB_PATH}")
    log(f"📊 已有数据: {total} 条, {kw_count} 个关键词")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, page = open_browser_and_login(pw)

        # 启动监看
        captured = watch_loop(page, conn)

        # 最终统计
        total, kw_count, by_kw = get_db_stats(conn)
        print("\n" + "=" * 55)
        print(f"  🎯 本次新增: {captured} 条")
        print(f"  📦 数据库总计: {total} 条, {kw_count} 个关键词")
        if by_kw:
            print(f"  关键词分布:")
            for kw, cnt in by_kw[:10]:
                print(f"    [{kw}] {cnt} 条")
        print("=" * 55)

        browser.close()
        conn.close()


if __name__ == "__main__":
    main()
