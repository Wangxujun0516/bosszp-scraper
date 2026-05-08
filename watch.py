#!/usr/bin/env python3
"""
BOSS 直聘监看模式 v2 — 稳定版
================================
脚本完全不操作浏览器，只"看"不"动"。
你登录、搜索、翻页全部手动，脚本在后台静默读取页面内容并保存。

用法:
  1. python watch.py
  2. 浏览器打开，你手动登录 BOSS 直聘
  3. 正常搜索、翻页、切换关键词
  4. 脚本自动识别岗位列表，自动存到 data/bosszp.db
  5. 按 Ctrl+C 停止
"""

import json, os, sys, time, hashlib, sqlite3, urllib.parse
from datetime import datetime
from pathlib import Path

import config as cfg

DB_PATH = os.path.join(cfg.OUTPUT_DIR, "bosszp.db")

# ========== 数据库 ==========

def init_db():
    ensure_dir(cfg.OUTPUT_DIR)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT UNIQUE,
            title TEXT,
            company TEXT,
            salary TEXT,
            location TEXT,
            tags TEXT,
            url TEXT,
            keyword TEXT,
            page_url TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fp ON jobs(fingerprint)")
    conn.commit()
    return conn


def make_fingerprint(job):
    raw = f"{job.get('title','')}|{job.get('company','')}"
    return hashlib.md5(raw.encode()).hexdigest()


def save_jobs(conn, jobs):
    """批量存入数据库，已存在的自动跳过"""
    cursor = conn.cursor()
    new_count = 0
    for job in jobs:
        fp = make_fingerprint(job)
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO jobs
                (fingerprint, title, company, salary, location, tags, url, keyword, page_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fp,
                job.get("title", ""),
                job.get("company", ""),
                job.get("salary", ""),
                job.get("location", ""),
                json.dumps(job.get("tags", []), ensure_ascii=False),
                job.get("url", ""),
                job.get("keyword", ""),
                job.get("page_url", ""),
            ))
            if cursor.rowcount > 0:
                new_count += 1
        except:
            pass
    conn.commit()
    return new_count


def get_stats(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT keyword, COUNT(*) FROM jobs GROUP BY keyword ORDER BY COUNT(*) DESC LIMIT 10")
    by_keyword = cursor.fetchall()
    return total, by_keyword


# ========== 页面读取（纯 JS，不进过 Playwright API） ==========

EXTRACT_JS = """
() => {
    // 不认 URL，只看页面有没有岗位卡片
    const cards = document.querySelectorAll('.job-card-wrapper');
    if (!cards.length) return [];
    
    const results = [];
    const pageUrl = window.location.href;
    const kw = new URLSearchParams(window.location.search).get('query') || '';
    
    cards.forEach(card => {
        try {
            const job = {};
            
            const getName = (sel) => {
                const el = card.querySelector(sel);
                return el ? el.innerText.trim() : '';
            };
            
            job.title = getName('.job-name') || getName('[class*="job-name"]');
            job.company = getName('.company-name') || getName('[class*="company-name"]');
            job.salary = getName('.salary') || getName('[class*="salary"]');
            job.location = getName('.job-area') || getName('[class*="job-area"]');
            
            const tags = [];
            card.querySelectorAll('.job-limit .tag-item, [class*="tag-item"]').forEach(
                t => tags.push(t.innerText.trim())
            );
            if (tags.length) job.tags = tags;
            
            const a = card.querySelector('a.job-card-left');
            if (a) {
                const h = a.getAttribute('href');
                if (h) job.url = h.startsWith('/') ? 'https://www.zhipin.com' + h : h;
            }
            
            if (job.title) {
                job.keyword = decodeURIComponent(kw);
                job.page_url = pageUrl;
                results.push(job);
            }
        } catch(e) {}
    });
    
    return results;
}
"""


def read_page_jobs(page):
    """通过 JS 读取当前页面上的岗位数据。纯读取，不操作页面。"""
    try:
        return page.evaluate(EXTRACT_JS)
    except:
        return []


def get_page_info(page):
    """获取当前页面 URL 和 title"""
    try:
        return page.url, page.title()
    except:
        return "", ""


# ========== 日志 ==========

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ========== 主流程 ==========

def main():
    ensure_dir(cfg.OUTPUT_DIR)
    conn = init_db()

    total, by_kw = get_stats(conn)
    log(f"📂 数据库: {DB_PATH}")
    log(f"📊 已有 {total} 条数据")
    if by_kw:
        for kw, cnt in by_kw[:5]:
            log(f"   [{kw}] {cnt} 条")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
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

        # 加载已有 Cookie
        if os.path.exists(cfg.COOKIE_FILE):
            try:
                with open(cfg.COOKIE_FILE) as f:
                    context.add_cookies(json.load(f))
            except:
                pass

        page = context.new_page()

        # ----- 打开空白浏览器，让用户完全手动操作 -----
        print()
        log("=" * 55)
        log("浏览器已打开（空白页）👇")
        log("")
        log("  1. 在地址栏输入 https://www.zhipin.com/hangzhou/")
        log("  2. 手动登录（点击「登录」→ 扫码）")
        log('  3. 搜索岗位，比如「外贸业务员」')
        log("")
        log("  ⏎  登录 + 搜索完成后，回终端按 Enter 启动监看...")
        log("=" * 55)

        # 不执行任何导航，打开空白页
        # 用户自己在浏览器里操作，彻底避免脚本导航导致闪退
        page.goto("about:blank")
        input()

        # 保存 Cookie
        try:
            cookies = context.cookies()
            with open(cfg.COOKIE_FILE, "w") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            log(f"Cookie 已保存")
        except:
            pass

        # ----- 监看循环 -----
        log("=" * 55)
        log("🟢 监看已启动（每 3 秒扫描一次）")
        log("   你现在可以正常搜索 BOSS 直聘")
        log("   工具自动识别岗位并保存")
        log("   按 Ctrl+C 停止")
        log("=" * 55)
        print()

        total_captured = 0
        last_url = ""
        last_log_time = time.time()
        last_save_time = 0

        try:
            while True:
                current_url, title = get_page_info(page)

                # 🛡️ 不限制 URL 格式——只要有岗位卡片就读
                # 兼容 /web/geek/job?city=... 和 /hangzhou/jobs?query=... 等格式
                if "zhipin.com" in current_url:
                    # 读取岗位数据
                    jobs = read_page_jobs(page)

                    if jobs:
                        now = time.time()
                        # 节流：同一 URL 每 8 秒最多保存一次
                        if now - last_save_time > 8 or current_url != last_url:
                            new = save_jobs(conn, jobs)
                            if new > 0:
                                total_captured += new
                                kw = jobs[0].get("keyword", "未知")
                                log(f"✅ +{new}  [{kw}] 当前页 {len(jobs)} 条  累计 {total_captured}")

                            last_save_time = now
                            last_url = current_url

                # 每 30 秒输出一次总统计（静默时保持反馈）
                if time.time() - last_log_time > 30:
                    total, _ = get_stats(conn)
                    log(f"📊 数据库总计: {total} 条  |  本次新增: {total_captured} 条")
                    last_log_time = time.time()

                time.sleep(3)

        except KeyboardInterrupt:
            total, by_kw = get_stats(conn)
            print()
            log("=" * 55)
            log(f"  🎯 监看已停止")
            log(f"  📦 本次新增: {total_captured} 条")
            log(f"  📊 数据库总计: {total} 条")
            if by_kw:
                log(f"  关键词分布:")
                for kw, cnt in by_kw[:10]:
                    log(f"    [{kw}] {cnt} 条")
            log("=" * 55)

        browser.close()
        context.close()
        conn.close()


if __name__ == "__main__":
    main()
