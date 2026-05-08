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

# ---------- 操作计数器 ----------

_op_count = 0

def count_op():
    """每次页面操作 +1，超过上限自动退出"""
    global _op_count
    _op_count += 1
    if _op_count > cfg.MAX_OPS_PER_SESSION:
        log(f"🛑 已达单次最大操作数 ({cfg.MAX_OPS_PER_SESSION})，自动退出")
        return False
    return True


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
    """时段限制：非合理时段直接退出"""
    now = datetime.now()
    hour = now.hour
    if hour < cfg.HOUR_START or hour >= cfg.HOUR_END:
        log(f"🛑 当前时间 {now.strftime('%H:%M')} 不在允许的时段内 ({cfg.HOUR_START}:00~{cfg.HOUR_END}:00)")
        log("   修改 config.py 中的 HOUR_START / HOUR_END 可调整")
        return False
    return True


def is_captcha_page(page):
    """检测是否遇到验证码/封禁页面"""
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


# ---------- 🛡️ 模拟真人操作 ----------

def human_scroll(page):
    """模拟真人滚动页面（随机滚动一段）"""
    try:
        # 随机滚 1~3 次
        for _ in range(random.randint(1, 3)):
            scroll_y = random.randint(200, 600)
            page.evaluate(f"window.scrollBy(0, {scroll_y})")
            time.sleep(random.uniform(0.3, 1.0))
        # 滚回到顶部附近（模拟看完往下翻后又回去）
        page.evaluate(f"window.scrollTo(0, {random.randint(0, 100)})")
    except:
        pass


def random_mouse_move(page):
    """模拟鼠标随机移动（在页面不同位置）"""
    try:
        w, h = 1400, 900
        for _ in range(random.randint(1, 2)):
            x = random.randint(100, w - 100)
            y = random.randint(100, h - 100)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.1, 0.4))
    except:
        pass


def behave_like_human(page):
    """执行一系列模拟真人操作"""
    if random.random() < 0.7:  # 70% 概率滚动
        human_scroll(page)
    if random.random() < 0.4:  # 40% 概率移动鼠标
        random_mouse_move(page)


# ---------- 浏览器管理 ----------

def get_browser_context(playwright):
    """启动浏览器并加载已保存的 Cookie（如果有的话）"""
    browser = playwright.chromium.launch(
        headless=cfg.HEADLESS,
        timeout=cfg.BROWSER_TIMEOUT,
    )

    # 随机化 viewport 尺寸
    vw = random.choice(cfg.VIEWPORT_WIDTHS)
    vh = random.choice(cfg.VIEWPORT_HEIGHTS)
    log(f"Viewport: {vw}x{vh}")

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
        log(f"页面标题: {page_title}")
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
    if not count_op():
        return jobs

    # 如果被重定向到登录页
    if is_logged_out(page):
        log(f"  登录态已失效，跳过该搜索")
        return jobs

    # 🛡️ 检测验证码/封禁
    if is_captcha_page(page):
        log(f"  🛑 遇到验证码，跳过后续搜索")
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

    # 🛡️ 模拟真人操作
    behave_like_human(page)

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
            if not count_op():
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
            # 🛡️ 翻页前模拟一下鼠标移动和滚动
            behave_like_human(page)
            next_btn.click()
            time.sleep(random.uniform(2, 4))
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


# ---------- 🛡️ 关键词调度 ----------

def get_filtered_keywords():
    """
    返回本次要搜索的关键词列表。
    安全策略：
    - 随机跳过部分关键词（如果 SKIP_KEYWORDS_RANDOMLY 开启）
    - 每次运行只搜一部分，避免每次都是完全相同的搜索模式
    """
    keywords = cfg.SEARCH_KEYWORDS.copy()

    if cfg.SKIP_KEYWORDS_RANDOMLY:
        # 随机跳过 20%~40% 的关键词
        skip_ratio = random.uniform(0.2, 0.4)
        skip_count = max(1, int(len(keywords) * skip_ratio))
        skip_indices = set(random.sample(range(len(keywords)), skip_count))
        filtered = [k for i, k in enumerate(keywords) if i not in skip_indices]

        skipped = [k for i, k in enumerate(keywords) if i in skip_indices]
        log(f"🛡️ 本次随机跳过 {len(skipped)} 个关键词: {', '.join(skipped)}")
        log(f"   实际搜索 {len(filtered)} 个: {', '.join(filtered)}")
        keywords = filtered

    # 随机打乱顺序（让搜索模式不固定）
    random.shuffle(keywords)
    return keywords


# ---------- 主流程 ----------

def main():
    # 🛡️ 检查时段
    if not check_time_of_day():
        sys.exit(1)

    ensure_dir(cfg.OUTPUT_DIR)

    # 导入 Playwright
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser, context = get_browser_context(pw)
        page = context.new_page()

        # --- 第一步：检查登录状态（直接打开登录稳定页，避免安全检测重定向） ---
        log("检查登录状态...")

        # 先直接去登录页，如果已经登录会自动跳转到首页
        try:
            page.goto(
                "https://www.zhipin.com/web/user/?ka=header-login",
                wait_until="networkidle",
                timeout=cfg.BROWSER_TIMEOUT,
            )
        except Exception as e:
            log(f"导航异常: {type(e).__name__}，检查当前页面...")

        # 等页面稳定
        time.sleep(5)

        # 看一下最终到了哪个页面
        log(f"当前页面: {page.url}")

        if is_logged_out(page):
            log("检测到未登录，请在浏览器中完成扫码登录")
            if wait_for_login(page):
                save_cookies(context)
            else:
                browser.close()
                sys.exit(1)
        else:
            log("Cookie 有效，已登录！")

        # 🛡️ 登录后模拟"装一会儿"再开始搜
        idle_time = random.uniform(cfg.POST_LOGIN_IDLE_MIN, cfg.POST_LOGIN_IDLE_MAX)
        log(f"🛡️ 登录后等待 {idle_time:.0f} 秒再开始搜索...")
        time.sleep(idle_time)

        # 🛡️ 在首页随便滚一滚，看起来像真人在浏览
        behave_like_human(page)
        random_delay(1, 3)

        # --- 第二步：执行搜索 ---
        all_jobs = []

        # 🛡️ 用过滤后的关键词列表（随机跳过 + 打乱）
        keywords = get_filtered_keywords()

        for keyword in keywords:
            log(f"\n{'='*50}")
            log(f"搜索关键词: {keyword}")
            log(f"{'='*50}")

            # 搜索指定城市
            jobs = search_jobs(page, keyword, cfg.CITY_CODE, cfg.MAX_PAGES)
            all_jobs.extend(jobs)

            # 如果操作数已超限，提前退出
            if _op_count >= cfg.MAX_OPS_PER_SESSION:
                log(f"🛑 操作数已达上限，停止搜索")
                break

            # 如果开启了全国搜索，额外搜一次全国范围（远程岗位）
            if cfg.SEARCH_NATIONWIDE:
                log(f"\n  同时搜索全国范围（含远程）...")
                nation_jobs = search_jobs(page, keyword, cfg.NATIONWIDE_CODE, cfg.MAX_PAGES)
                all_jobs.extend(nation_jobs)

                if _op_count >= cfg.MAX_OPS_PER_SESSION:
                    log(f"🛑 操作数已达上限，停止搜索")
                    break

            # 🛡️ 切换关键词的间隔
            random_delay(cfg.SEARCH_DELAY_MIN, cfg.SEARCH_DELAY_MAX)

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
        log(f"  本次搜索关键词: {', '.join(keywords)}")
        log(f"  城市: {cfg.CITY_CODE}" + (" + 全国" if cfg.SEARCH_NATIONWIDE else ""))
        log(f"  总岗位数（去重后）: {len(all_jobs)}")
        log(f"  总操作次数: {_op_count}")
        log(f"{'='*50}")

        browser.close()


if __name__ == "__main__":
    main()
