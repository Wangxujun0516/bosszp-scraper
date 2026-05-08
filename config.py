"""
BOSS 直聘爬虫 - 配置文件
==========================
修改这里的关键词和城市，定制你的搜索条件。
"""

# ===== 搜索关键词 =====
# 可以添加多个，爬虫会依次搜索每个关键词
SEARCH_KEYWORDS = [
    "技术文档工程师",
    "Technical Writer",
    "文档工程师",
    "技术写作",
    "技术传播",
    "外贸",
    "外贸专员",
    "外贸业务员",
]

# ===== 城市 =====
# BOSS 直聘城市代码，常见城市:
#   杭州: 101210100
#   北京: 101010100
#   上海: 101020100
#   深圳: 101280600
#   广州: 101280100
#   全国(不限): 100010000
CITY_CODE = "101210100"   # 杭州

# 是否搜索全国/远程岗位（会额外搜一次全国范围）
SEARCH_NATIONWIDE = True
NATIONWIDE_CODE = "100010000"  # 全国

# ===== 搜索参数 =====
PAGE_SIZE = 30         # 每页数量（最大30）
MAX_PAGES = 3          # 每个关键词最多爬取页数

# ===== 输出 =====
OUTPUT_DIR = "data"
OUTPUT_FILE_PREFIX = "bosszp_jobs"

# ===== 浏览器设置 =====
HEADLESS = False       # 首次登录设为 False，登录成功后可以改成 True
BROWSER_TIMEOUT = 30000  # 毫秒
COOKIE_FILE = "cookies.json"

# ===== 反爬设置 =====
PAGE_DELAY_MIN = 2     # 翻页间隔最少秒数
PAGE_DELAY_MAX = 4     # 翻页间隔最多秒数
SEARCH_DELAY = 3       # 切换关键词的间隔秒数
