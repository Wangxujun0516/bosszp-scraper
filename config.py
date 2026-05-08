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
MAX_PAGES = 2          # 每个关键词最多爬取页数（安全值2，不超过3）
SKIP_KEYWORDS_RANDOMLY = True   # 随机跳过一部分关键词，避免每次都搜完全部

# ===== 输出 =====
OUTPUT_DIR = "data"
OUTPUT_FILE_PREFIX = "bosszp_jobs"

# ===== 浏览器设置 =====
HEADLESS = False       # 首次登录设为 False，登录成功后可以改成 True
BROWSER_TIMEOUT = 45000  # 毫秒
COOKIE_FILE = "cookies.json"

# ===== 🛡️ 反爬/防封设置 =====

# 页面操作间隔（秒）— 随机值在 min~max 之间
PAGE_DELAY_MIN = 3     # 翻页间隔最少秒数
PAGE_DELAY_MAX = 6     # 翻页间隔最多秒数
SEARCH_DELAY_MIN = 4   # 切换关键词最少间隔
SEARCH_DELAY_MAX = 8   # 切换关键词最多间隔

# 登录后等待时间（秒）— 登录后先"装一会儿"再开始搜
POST_LOGIN_IDLE_MIN = 3
POST_LOGIN_IDLE_MAX = 8

# 每次运行最大操作次数 — 到达后自动退出，避免单次会话过久
MAX_OPS_PER_SESSION = 60   # 约等于 60 次页面操作

# 防检测：每次运行随机化 viewport 尺寸
VIEWPORT_WIDTHS = [1200, 1280, 1366, 1400, 1440, 1536]
VIEWPORT_HEIGHTS = [700, 768, 800, 900]

# 检测到验证码/封禁提示后自动停止
CAPTCHA_KEYWORDS = [
    "安全验证",
    "您的IP地址存在异常行为",
    "访问受限",
    "请完成验证",
    "请输入验证码",
    "滑块验证",
    "verify",
    "captcha",
]

# ⏰ 时段限制：只在合理时段运行（北京时间 8:00~22:00）
# 防止凌晨/半夜操作被标记为异常
HOUR_START = 8
HOUR_END = 22
