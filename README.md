# BOSS 直聘岗位爬虫 & JD 分析工具

基于 Playwright 的 BOSS 直聘招聘数据采集 + 技能需求分析工具。

## 两种使用方式

### 方式一：书签脚本（最简单，推荐新手）

[点这里查看详细安装步骤](./BOOKMARKLET.md)

> 拖一个书签到浏览器 → 在 BOSS 页面点一下 → 自动下载 JSON

无需安装 Python，无需任何配置。

### 方式二：Python 爬虫（自动翻页）

```bash
pip install -r requirements.txt
playwright install chromium
python scraper.py
```

浏览器打开后，**手动登录 BOSS 直聘**，回到终端按 Enter，脚本自动爬取所有关键词和页数。

---

## 功能

- **爬取**：自动搜索多个关键词 + 多城市 + 多页的岗位信息
- **分析**：提取 JD 中的技能关键词，生成词云和技能需求排行榜
- **对比**：跨期对比技能需求变化（新增/消失的技能）

## 快速开始

### 1. 环境准备

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 运行爬虫

```bash
python scraper.py
```

脚本会弹出一个浏览器窗口，**你自己手动登录 BOSS 直聘**：
1. 在浏览器里打开 https://www.zhipin.com
2. 用微信或 App 扫码登录
3. 登录成功后，回到终端按 **Enter 键**

之后脚本会自动搜索所有关键词并保存数据。

> 首次运行后 Cookie 会被保存，下次可以直接扫码登录或者继续使用已有登录态。

### 4. 查看结果

```bash
# 爬取结果
ls data/bosszp_jobs_*.json

# 技能词云
open data/skill_wordcloud.png    # Mac
start data/skill_wordcloud.png   # Windows
```

## 配置

编辑 `config.py` 定制你的搜索条件：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `SEARCH_KEYWORDS` | 搜索关键词列表 | 技术文档、TW、外贸等 |
| `CITY_CODE` | 城市代码 | 101210100（杭州） |
| `SEARCH_NATIONWIDE` | 是否同时搜全国 | True |
| `MAX_PAGES` | 每个关键词爬取页数 | 3 |
| `HEADLESS` | 无头模式（不显示浏览器） | False |
| `PAGE_DELAY_MIN/MAX` | 翻页间隔（秒） | 2~4 |

### 城市代码表

| 城市 | 代码 |
|------|------|
| 全国 | 100010000 |
| 北京 | 101010100 |
| 上海 | 101020100 |
| 杭州 | 101210100 |
| 深圳 | 101280600 |
| 广州 | 101280100 |
| 成都 | 101270100 |
| 南京 | 101190100 |

## 输出格式

爬取结果保存为 JSON，每条记录包含：

```json
{
  "title": "技术文档工程师",
  "company": "某科技有限公司",
  "salary": "15K-25K",
  "location": "杭州",
  "tags": ["3-5年", "本科"],
  "skills": ["Python", "Git", "API文档"],
  "url": "https://www.zhipin.com/job_detail/xxx.html",
  "keyword": "技术文档工程师",
  "scraped_at": "2025-01-01T10:30:00"
}
```

## 数据分析

```bash
# 分析最新数据
python analyze.py

# 分析指定文件
python analyze.py data/bosszp_jobs_20250101_103000.json

# 跳过错云生成（如果字体有问题）
python analyze.py --no-wordcloud
```

分析报告包含：
- 📊 基础统计（总岗位数、关键词分布）
- 💰 薪资范围分布
- 🏆 技能需求 Top 20（含占比柱状图）
- 📈 与上次对比的新增/消失技能

## 设置定时任务（Windows）

在 Windows 上使用 **任务计划程序**（Task Scheduler）实现每周自动运行：

1. 按 `Win + R`，输入 `taskschd.msc`
2. 右侧点击 "创建基本任务"
3. 名称：BOSS直聘爬虫，触发器选 "每周"
4. 操作选 "启动程序"：
   - 程序：`C:\path\to\python.exe`
   - 参数：`C:\path\to\bosszp-scraper\scraper.py`
5. 完成

## 项目结构

```
bosszp-scraper/
├── config.py         # 配置文件（关键词、城市等）
├── scraper.py        # 爬虫主程序
├── analyze.py        # JD 分析工具
├── run.sh            # 一键运行脚本
├── requirements.txt  # Python 依赖
├── data/             # 爬取结果 + 词云图片
│   ├── latest.json
│   └── bosszp_jobs_*.json
└── cookies.json      # 登录 Cookie（不要提交到 Git）
```

## 注意事项

1. **网络环境**：BOSS 直聘对数据中心的 IP 有限制，建议在家庭/公司网络下运行
2. **频率控制**：爬虫内置随机延迟（2~4秒），建议每天不要超过 2 次
3. **Cookie 有效期**：BOSS 登录状态通常持续几天到一周，过期后重新扫码即可
4. **页面变化**：如果 BOSS 直聘改版导致选择器失效，可以提 Issue
