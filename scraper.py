#!/usr/bin/env python3
"""
Scraper 改进版 — 由用户手动登录，脚本只负责抓取
==================================================
用法:
  1. python scraper.py
  2. 浏览器自动打开，你手动输入 zhipin.com 并登录
  3. 登录完回到终端按 Enter
  4. 脚本自动抓取
"""

import json, os, sys, time, random
from datetime import datetime
from pathlib import Path

import config as cfg

# ---------- 操作计数器 ----------

_op_count = 0

def count_op():
    global _op_count
    _op_count += 1
    return _op_count <= cfg.MAX_OPS_PER_SESSION


# ---------- 工具函数 ----------

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def random_delay(lo, hi):
    time.sleep(random.uniform(lo, hi))


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f"已保存 {len(data)} 条记录 → {filepath}")


# ---------- 🛡️ 防封检测 ----------

def check_time_of_day():
    now = datetime.now()
    hour = now.hour
    if hour < cfg.HOUR_START or hour >= cfg.HOUR_END:
        log(f"🛑 当前时间 {now.strftime('%H:%M')} 不在允许时段内 ({cfg.HOUR_START}:00~{cfg.HOUR_END}:00)")
        return False
    return True


def is_captcha_page(page):
    try:
        body = page.inner_text("body")[:500].lower()
        page_url = page.url.lower()
        combined = body + " " + page_url
        for kw in cfg.CAPTCHA_KEYWORDS:
            if kw.lower() in combined:
                log(f"🛑 检测到验证码/封禁: '{kw}'")
                return True
    except:
        pass
    return False


def behave_like_human(page):
    """模拟真人滚动"""
    try:
        for _ in range(random.randint(1, 3)):
            scroll_y = random.randint(200, 600)
            page.evaluate(f"window.scrollBy(0, {scroll_y})")
            time.sleep(random.uniform(0.3, 1.0))
        page.evaluate(f"window.scrollTo(0, {random.randint(0, 100)})")
    except:
        pass


# ---------- 浏览器管理 ----------

def get_browser_context(playwright):
    browser = playwright.chromium.launch(
        headless=False,  # 必须显示浏览器，用户要手动操作
        timeout=cfg.BROWSER_TIMEOUT,
    )

    vw = random.choice(cfg.VIEWPORT_WIDTHS)
    vh = random.choice(cfg.VIEWPORT_HEIGHTS)

    context = browser.new_context(
        viewport={"width": vw, "height": vh},
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
            with open(cfg.COOKIE_FILE, "r") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            log(f"已加载 {len(cookies)} 个 Cookie")
        except Exception as e:
            log(f"Cookie 加载失败: {e}")

    return browser, context


def save_cookies(context):
    cookies = context.cookies()
    with open(cfg.COOKIE_FILE, "w") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    log(f"已保存 {len(cookies)} 个 Cookie → {cfg.COOKIE_FILE}")


# ---------- 💡 新的登录方式：用户手动操作 ----------

def wait_for_user_login(page):
    """
    打开空浏览器，让用户自己手动登录 BOSS 直聘。
    登录完成后回到终端按 Enter 继续。
    """
    log("=" * 55)
    log("浏览器已打开 👉 请在浏览器中手动完成以下操作:")
    log("  1. 打开 https://www.zhipin.com")
    log("  2. 用微信/App 扫码登录")
    log("  3. 登录成功后，回到这个终端按 Enter 键继续")
    log("=" * 55)
    log("")

    # 先打开 BOSS 直聘
    try:
        page.goto("https://www.zhipin.com/", wait_until="commit", timeout=cfg.BROWSER_TIMEOUT)
    except:
        pass

    # 等待用户按 Enter
    input("⏎  按 Enter 键继续（确认已登录）...")

    # 确认登录成功
    time.sleep(2)
    current_url = page.url
    log(f"当前页面: {current_url}")

    if "/web/geek/" in current_url or "/web/chat" in current_url:
        log("✅ 登录状态确认成功！")
        save_cookies(context)
        return True
    else:
        log("⚠️ 看起来还没登录成功，尝试再次等待...")
        # 导航到首页，看看会不会自动跳转
        try:
            page.goto("https://www.zhipin.com/web/geek/job", wait_until="commit", timeout=15000)
            time.sleep(3)
        except:
            pass
        current_url = page.url
        if "/web/geek/" in current_url:
            log("✅ 登录状态确认成功！")
            save_cookies(context)
            return True
        log("❌ 仍未登录成功，请重新运行脚本")
        return False


# ---------- 核心爬取逻辑 ----------

def safe_goto(page, url):
    try:
        resp = page.goto(url, wait_until="commit", timeout=cfg.BROWSER_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=15000)
        return resp
    except:
        return None


def search_jobs(page, keyword, city_code, max_pages):
    jobs = []

    url = f"https://www.zhipin.com/web/geek/job?city={city_code}&query={keyword}"
    log(f"搜索: [{keyword}] 城市码: {city_code}")
    safe_goto(page, url)
    if not count_op():
        return jobs

    # 验证码检测
    if is_captcha_page(page):
        log(f"  🛑 遇到验证码，跳过后续搜索")
        return jobs

    # 等待搜索结果加载
    try:
        page.wait_for_selector(".job-list-box", timeout=20000)
    except:
        try:
            page.wait_for_selector(".job-card-wrapper", timeout=15000)
        except:
            log(f"  [警告] 搜索结果未加载")
            return jobs

    behave_like_human(page)

    for page_num in range(1, max_pages + 1):
        log(f"  第 {page_num} 页...")
        random_delay(cfg.PAGE_DELAY_MIN, cfg.PAGE_DELAY_MAX)

        page_jobs = parse_job_cards(page, keyword, city_code)
        jobs.extend(page_jobs)
        log(f"    本页获取 {len(page_jobs)} 条，累计 {len(jobs)} 条")

        if page_num < max_pages:
            if not go_next_page(page, page_num):
                log(f"  没有更多页了")
                break
            if not count_op():
                break

    return jobs


def parse_job_cards(page, keyword, city_code):
    jobs = []
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

            # 标签
            try:
                tags = []
                for el in card.query_selector_all(".job-limit .tag-item, [class*='tag-item']"):
                    tags.append(el.inner_text().strip())
                if tags:
                    job["tags"] = tags
            except:
                pass

            # 链接
            try:
                el = card.query_selector("a.job-card-left")
                if el:
                    href = el.get_attribute("href")
                    if href:
                        job["url"] = f"https://www.zhipin.com{href}" if href.startswith("/") else href
            except:
                pass

            if job.get("title"):
                job["keyword"] = keyword
                job["city_code"] = city_code
                job["scraped_at"] = datetime.now().isoformat()
                jobs.append(job)
        except:
            continue

    return jobs


def go_next_page(page, current_page):
    try:
        next_btn = page.query_selector(".page-next")
        if not next_btn:
            next_btn = page.query_selector("[class*='next']")
        if not next_btn:
            pagers = page.query_selector_all(".page-item")
            for p in pagers:
                text = p.inner_text().strip()
                if text == str(current_page + 1):
                    next_btn = p
                    break
        if next_btn and next_btn.is_enabled():
            behave_like_human(page)
            next_btn.click()
            time.sleep(random.uniform(2, 4))
            return True
        return False
    except:
        return False


# ---------- 关键词调度 ----------

def get_filtered_keywords():
    keywords = cfg.SEARCH_KEYWORDS.copy()
    if cfg.SKIP_KEYWORDS_RANDOMLY:
        skip_ratio = random.uniform(0.2, 0.4)
        skip_count = max(1, int(len(keywords) * skip_ratio))
        skip_indices = set(random.sample(range(len(keywords)), skip_count))
        filtered = [k for i, k in enumerate(keywords) if i not in skip_indices]
        skipped = [k for i, k in enumerate(keywords) if i in skip_indices]
        log(f"🛡️ 本次随机跳过 {len(skipped)} 个: {', '.join(skipped)}")
        keywords = filtered
    random.shuffle(keywords)
    return keywords


# ---------- 主流程 ----------

def main():
    if not check_time_of_day():
        sys.exit(1)

    ensure_dir(cfg.OUTPUT_DIR)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, context = get_browser_context(pw)
        page = context.new_page()

        # --- 第一步：让用户手动登录 ---
        if not wait_for_user_login(page):
            browser.close()
            sys.exit(1)

        # 🛡️ 登录后闲逛一会儿
        idle = random.uniform(cfg.POST_LOGIN_IDLE_MIN, cfg.POST_LOGIN_IDLE_MAX)
        log(f"🛡️ 等待 {idle:.0f} 秒后开始搜索...")
        time.sleep(idle)
        behave_like_human(page)

        # --- 第二步：搜索 ---
        all_jobs = []
        keywords = get_filtered_keywords()

        for keyword in keywords:
            log(f"\n{'='*50}")
            log(f"搜索关键词: {keyword}")
            log(f"{'='*50}")

            jobs = search_jobs(page, keyword, cfg.CITY_CODE, cfg.MAX_PAGES)
            all_jobs.extend(jobs)

            if _op_count >= cfg.MAX_OPS_PER_SESSION:
                log(f"🛑 操作数已达上限，停止")
                break

            if cfg.SEARCH_NATIONWIDE:
                log(f"\n  同时搜索全国范围（含远程）...")
                nation_jobs = search_jobs(page, keyword, cfg.NATIONWIDE_CODE, cfg.MAX_PAGES)
                all_jobs.extend(nation_jobs)

                if _op_count >= cfg.MAX_OPS_PER_SESSION:
                    log(f"🛑 操作数已达上限，停止")
                    break

            random_delay(cfg.SEARCH_DELAY_MIN, cfg.SEARCH_DELAY_MAX)

        # --- 去重 ---
        seen = set()
        deduped = []
        for j in all_jobs:
            u = j.get("url", "")
            if u and u in seen:
                continue
            if u:
                seen.add(u)
            deduped.append(j)
        all_jobs = deduped

        # --- 保存 ---
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(cfg.OUTPUT_DIR, f"{cfg.OUTPUT_FILE_PREFIX}_{ts}.json")
        save_json(all_jobs, out)

        latest = os.path.join(cfg.OUTPUT_DIR, "latest.json")
        save_json(all_jobs, latest)

        log(f"\n{'='*50}")
        log(f"爬取完成!")
        log(f"  关键词: {', '.join(keywords)}")
        log(f"  城市: {cfg.CITY_CODE}" + (" + 全国" if cfg.SEARCH_NATIONWIDE else ""))
        log(f"  总岗位数（去重后）: {len(all_jobs)}")
        log(f"{'='*50}")

        browser.close()


if __name__ == "__main__":
    main()
