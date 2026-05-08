#!/usr/bin/env python3
"""
BOSS 直聘岗位爬虫
=================
基于 Playwright 的招聘数据采集工具。

使用方法:
  1. 首次运行: python scraper.py        # 会打开浏览器让你扫码登录
  2. 后续运行: python scraper.py        # 自动复用已保存的 Cookie

输出: data/bosszp_jobs_YYYYMMDD_HHMMSS.json
"""

import json, os, sys, time, random
from datetime import datetime
from pathlib import Path

import config as cfg

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


# ---------- 浏览器管理 ----------

def get_browser_context(playwright):
    """启动浏览器并加载已保存的 Cookie（如果有的话）"""
    browser = playwright.chromium.launch(
        headless=cfg.HEADLESS,
        timeout=cfg.BROWSER_TIMEOUT,
    )

    # 创建一个持久化的浏览器上下文（用于更好的 Cookie 管理）
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
            with open(cfg.COOKIE_FILE, "r") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            log(f"已加载 {len(cookies)} 个 Cookie")
        except Exception as e:
            log(f"Cookie 加载失败: {e}")

    return browser, context


def save_cookies(context):
    """保存当前浏览器的 Cookie"""
    cookies = context.cookies()
    with open(cfg.COOKIE_FILE, "w") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    log(f"已保存 {len(cookies)} 个 Cookie → {cfg.COOKIE_FILE}")


def wait_for_login(page, timeout_seconds=300):
    """
    等待用户在浏览器中完成扫码登录。
    检测到页面跳转到招聘列表页即认为登录成功。
    """
    # 先输出当前页面信息，方便调试
    current_url = page.url
    log(f"当前页面: {current_url}")

    # 尝试检查页面上是否有二维码或登录表单
    try:
        page_title = page.title()
        body_preview = page.inner_text("body")[:200] if page.query_selector("body") else "(空)"
        log(f"页面标题: {page_title}")
        log(f"页面内容预览: {body_preview[:100]}...")
    except Exception as e:
        log(f"页面分析失败: {e}")

    log("=" * 50)
    log("请在弹出的浏览器窗口中完成扫码登录")
    log("（用微信或 BOSS 直聘 App 扫二维码）")
    log(f"等待登录，最长等待 {timeout_seconds} 秒...")
    log("=" * 50)

    last_status_log = time.time()
    start = time.time()
    while time.time() - start < timeout_seconds:
        current_url = page.url

        # 每30秒输出一次状态，避免干等
        elapsed = int(time.time() - start)
        if time.time() - last_status_log >= 30:
            log(f"仍在等待... (已等待 {elapsed} 秒，当前页面: {current_url[:100]})")
            last_status_log = time.time()

        # 登录成功的检测条件
        if "/web/geek/" in current_url:
            log("登录成功！")
            return True
        if "/web/chat" in current_url:
            log("登录成功！")
            return True

        time.sleep(2)

    log("登录超时。请重新运行脚本再次尝试。")
    return False


# ---------- 核心爬取逻辑 ----------

def safe_goto(page, url):
    """安全导航，处理登录重定向和中断"""
    try:
        resp = page.goto(url, wait_until="commit", timeout=cfg.BROWSER_TIMEOUT)
        # 等待页面稳定
        page.wait_for_load_state("networkidle", timeout=15000)
        return resp
    except Exception as e:
        log(f"  导航异常: {type(e).__name__}")
        return None


def is_logged_out(page):
    """检测是否被重定向到登录页"""
    current = page.url
    if "passport" in current or "login" in current or "user" in current:
        return True
    # 检查是否有登录表单元素
    try:
        if page.query_selector(".passport-form"):
            return True
    except:
        pass
    return False


def handle_login_if_needed(page, context):
    """检测登录状态，需要时引导用户扫码"""
    if not is_logged_out(page):
        return True

    log("检测到未登录，引导扫码...")

    # 如果已经在登录页，直接等扫码；否则导航过去
    current = page.url
    if "passport" not in current and "login" not in current:
        try:
            page.goto(
                "https://www.zhipin.com/web/user/?ka=header-login",
                wait_until="domcontentloaded",
                timeout=cfg.BROWSER_TIMEOUT,
            )
        except Exception as e:
            log(f"  导航到登录页异常: {type(e).__name__}，检查当前页面...")

    # 再检查一次当前页面状态
    time.sleep(3)

    if wait_for_login(page):
        save_cookies(context)
        return True
    return False


def search_jobs(page, keyword, city_code, max_pages):
    """搜索指定关键词和城市的岗位，返回岗位列表"""
    jobs = []

    url = (
        f"https://www.zhipin.com/web/geek/job"
        f"?city={city_code}&query={keyword}"
    )
    log(f"搜索: [{keyword}] 城市码: {city_code}")
    safe_goto(page, url)

    # 如果被重定向到登录页
    if is_logged_out(page):
        log(f"  登录态已失效，跳过该搜索")
        return jobs

    # 等待搜索结果容器加载
    try:
        page.wait_for_selector(".job-list-box", timeout=15000)
    except:
        try:
            page.wait_for_selector(".job-card-wrapper", timeout=10000)
        except:
            log(f"  [警告] 搜索结果未加载，可能无结果或被反爬")
            return jobs

    for page_num in range(1, max_pages + 1):
        log(f"  第 {page_num} 页...")
        random_delay(cfg.PAGE_DELAY_MIN, cfg.PAGE_DELAY_MAX)

        # 解析当前页面的岗位列表
        page_jobs = parse_job_cards(page, keyword, city_code)
        jobs.extend(page_jobs)
        log(f"    本页获取 {len(page_jobs)} 条，累计 {len(jobs)} 条")

        # 尝试翻页
        if page_num < max_pages:
            if not go_next_page(page, page_num):
                log(f"  没有更多页了")
                break

    return jobs


def parse_job_cards(page, keyword, city_code):
    """从当前页面提取岗位卡片信息"""
    jobs = []

    try:
        cards = page.query_selector_all(".job-card-wrapper")
        if not cards:
            cards = page.query_selector_all(".job-list-box .job-primary")
        if not cards:
            # 更通用的选择器
            cards = page.query_selector_all("[class*='job-card']")
    except:
        cards = []

    for card in cards:
        try:
            job = extract_job_info(card, keyword, city_code)
            if job:
                jobs.append(job)
        except Exception as e:
            continue

    return jobs


def extract_job_info(card, keyword, city_code):
    """从单个岗位卡片提取信息"""
    job = {
        "keyword": keyword,
        "city_code": city_code,
        "scraped_at": datetime.now().isoformat(),
    }

    # 岗位名称
    try:
        el = card.query_selector(".job-name")
        if not el:
            el = card.query_selector("[class*='job-name']")
        if el:
            job["title"] = el.inner_text().strip()
    except:
        job["title"] = ""

    # 公司名称
    try:
        el = card.query_selector(".company-name")
        if not el:
            el = card.query_selector("[class*='company-name']")
        if el:
            job["company"] = el.inner_text().strip()
    except:
        job["company"] = ""

    # 薪资
    try:
        el = card.query_selector(".salary")
        if not el:
            el = card.query_selector("[class*='salary']")
        if el:
            job["salary"] = el.inner_text().strip()
    except:
        job["salary"] = ""

    # 工作地点
    try:
        el = card.query_selector(".job-area")
        if not el:
            el = card.query_selector("[class*='job-area']")
        if el:
            job["location"] = el.inner_text().strip()
    except:
        job["location"] = ""

    # 经验/学历标签
    try:
        tags = []
        els = card.query_selector_all(".job-limit .tag-item")
        for t in els:
            tags.append(t.inner_text().strip())
        if tags:
            job["tags"] = tags
    except:
        job["tags"] = []

    # 技能标签
    try:
        skills = []
        els = card.query_selector_all(".job-card-footer .tag-item, [class*='tag-item']")
        for t in els:
            text = t.inner_text().strip()
            if text and text not in tags:
                skills.append(text)
        if skills:
            job["skills"] = skills
    except:
        pass

    # 跳转链接
    try:
        el = card.query_selector("a.job-card-left")
        if el:
            href = el.get_attribute("href")
            if href:
                job["url"] = f"https://www.zhipin.com{href}" if href.startswith("/") else href
    except:
        pass

    return job


def go_next_page(page, current_page):
    """翻到下一页"""
    try:
        # 查找下一页按钮
        next_btn = page.query_selector(".page-next")
        if not next_btn:
            next_btn = page.query_selector("[class*='next']")
        if not next_btn:
            # 通过页码按钮跳转
            pagers = page.query_selector_all(".page-item")
            for p in pagers:
                text = p.inner_text().strip()
                if text == str(current_page + 1):
                    next_btn = p
                    break
        if next_btn and next_btn.is_enabled():
            next_btn.click()
            time.sleep(2)
            return True
        return False
    except:
        return False


# ---------- JD 详情爬取（可选） ----------

def scrape_jd_detail(page, job_url, timeout=15):
    """打开岗位详情页，爬取完整的职位描述"""
    try:
        page.goto(job_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        time.sleep(2)

        # 等待职位描述加载
        jd_text = ""
        selectors = [
            ".job-sec-text",
            ".job-detail",
            "[class*='job-detail']",
            ".detail-content",
        ]
        for sel in selectors:
            try:
                el = page.wait_for_selector(sel, timeout=5000)
                if el:
                    jd_text = el.inner_text().strip()
                    break
            except:
                continue

        return jd_text
    except Exception as e:
        return ""


# ---------- 主流程 ----------

def main():
    ensure_dir(cfg.OUTPUT_DIR)

    # 导入 Playwright（在函数内部导入，避免无头环境报错）
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, context = get_browser_context(pw)
        page = context.new_page()

        # --- 第一步：检查登录状态 ---
        log("检查登录状态...")
        safe_goto(page, "https://www.zhipin.com/web/geek/job")
        time.sleep(3)

        if not handle_login_if_needed(page, context):
            browser.close()
            sys.exit(1)

        # --- 第二步：执行搜索 ---
        all_jobs = []

        for keyword in cfg.SEARCH_KEYWORDS:
            log(f"\n{'='*50}")
            log(f"搜索关键词: {keyword}")
            log(f"{'='*50}")

            # 搜索指定城市
            jobs = search_jobs(page, keyword, cfg.CITY_CODE, cfg.MAX_PAGES)
            all_jobs.extend(jobs)

            # 如果开启了全国搜索，额外搜一次全国范围（远程岗位）
            if cfg.SEARCH_NATIONWIDE:
                log(f"\n  同时搜索全国范围（含远程）...")
                nation_jobs = search_jobs(page, keyword, cfg.NATIONWIDE_CODE, cfg.MAX_PAGES)
                all_jobs.extend(nation_jobs)

            # 关键词间隔
            random_delay(cfg.SEARCH_DELAY, cfg.SEARCH_DELAY + 2)

        # --- 第三步：去重（按 url 去重） ---
        seen_urls = set()
        deduped = []
        for j in all_jobs:
            url = j.get("url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            deduped.append(j)
        all_jobs = deduped

        # --- 第四步：保存结果 ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(cfg.OUTPUT_DIR, f"{cfg.OUTPUT_FILE_PREFIX}_{timestamp}.json")
        save_json(all_jobs, output_path)

        # 同时保存一份 latest.json 方便后续分析脚本读取
        latest_path = os.path.join(cfg.OUTPUT_DIR, "latest.json")
        save_json(all_jobs, latest_path)

        # 汇总
        log(f"\n{'='*50}")
        log(f"爬取完成!")
        log(f"  关键词: {', '.join(cfg.SEARCH_KEYWORDS)}")
        log(f"  城市: {cfg.CITY_CODE}" + (" + 全国" if cfg.SEARCH_NATIONWIDE else ""))
        log(f"  总岗位数（去重后）: {len(all_jobs)}")
        log(f"{'='*50}")

        browser.close()


if __name__ == "__main__":
    main()
