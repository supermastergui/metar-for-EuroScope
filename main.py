import requests, json
from flask import Flask
import logging
import time
import random
import re

SPECIAL_METAR_API_URL = "!ENV SPECIAL_MATER_API"  # 让它易于替换

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 简单的缓存机制
metar_cache = {}
cache_lock = Lock()
CACHE_TIMEOUT = 300  # 5分钟缓存

# 用户代理列表，模拟不同浏览器
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]

# 有效的机场代码模式（4位字母，如ZSSS）
VALID_AIRPORT_PATTERN = re.compile(r'^[A-Z]{4}$')

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS)
    }

def clean_metar(metar_text):
    """清理METAR/TAF/SPECI文本，移除开头的'METAR '、'TAF '或'SPECI '前缀"""
    if not metar_text:
        return metar_text
    
    # 定义要移除的前缀
    prefixes = ["METAR ", "TAF ", "SPECI "]
    
    for prefix in prefixes:
        if metar_text.startswith(prefix):
            # 移除前缀
            return metar_text[len(prefix):]
    
    return metar_text

def parse_SPECIAL_METAR_API_URL_metar(html_content):
    """从厦航API的HTML响应中提取METAR数据"""
    try:
        # 使用正则表达式匹配METAR行
        metar_pattern = r'METAR\s+[A-Z]{4}\s+\d{6}Z\s+[^=]+='
        matches = re.findall(metar_pattern, html_content)
        
        if matches:
            # 返回第一个METAR
            return matches[0]
        else:
            logger.warning("未在厦航API响应中找到METAR数据")
            return None
    except Exception as e:
        logger.error(f"解析厦航API响应时出错: {e}")
        return None

def is_valid_airport_code(airport):
    """检查是否为有效的机场代码"""
    return bool(VALID_AIRPORT_PATTERN.match(airport))

def get_cached_metar(airport):
    """获取缓存的METAR数据"""
    with cache_lock:
        if airport in metar_cache:
            data, timestamp = metar_cache[airport]
            if time.time() - timestamp < CACHE_TIMEOUT:
                return data
            else:
                # 缓存过期，删除
                del metar_cache[airport]
    return None

def set_cached_metar(airport, metar_data):
    """设置缓存的METAR数据"""
    with cache_lock:
        metar_cache[airport] = (metar_data, time.time())

@app.route('/<string:airport>', methods=['GET'])
def handle_airports(airport):
    # 检查机场代码是否有效
    if not is_valid_airport_code(airport):
        logger.warning(f"无效的机场代码: {airport}")
        return ""
    
    logger.info(f"收到机场代码请求: {airport}")
    
    # 首先检查缓存
    cached_metar = get_cached_metar(airport)
    if cached_metar:
        logger.info(f"返回缓存的METAR数据: {cached_metar}")
        return cached_metar
    
    # 首先尝试主源 aviationweather.gov
    try:
        logger.info(f"尝试从 aviationweather.gov 获取 {airport} 的METAR数据")
        res = requests.get(
            f"https://aviationweather.gov/api/data/metar?ids={airport}", 
            headers=get_headers(),
            timeout=5  # 减少超时时间
        )
        logger.info(f"aviationweather.gov 响应状态码: {res.status_code}")
        
        if res.status_code == 200 and res.text.strip():
            metar_text = res.text.strip()
            logger.info(f"aviationweather.gov 返回原始数据: {metar_text}")
            
            if metar_text and "not found" not in metar_text.lower():
                cleaned_metar = clean_metar(metar_text)
                logger.info(f"返回清理后的METAR: {cleaned_metar}")
                # 缓存结果
                set_cached_metar(airport, cleaned_metar)
                return cleaned_metar
        elif res.status_code == 204:
            logger.info(f"aviationweather.gov 无数据 (204) 对于 {airport}")
        else:
            logger.warning(f"aviationweather.gov 响应异常: {res.status_code}")
    except Exception as e:
        logger.error(f"从 aviationweather.gov 获取数据时出错: {e}")
    
    # 第二优先级：厦航API
    try:
        # 添加随机延迟，避免请求过于频繁
        time.sleep(random.uniform(0.5, 1.0))
        
        logger.info(f"尝试从 SPECIAL_METAR_API_URL 获取 {airport} 的METAR数据")
        res = requests.get(
            f"SPECIAL_METAR_API_URL", 
            headers=get_headers(),
            timeout=5
        )
        logger.info(f"SPECIAL_METAR_API_URL 响应状态码: {res.status_code}")
        
        if res.status_code == 200:
            # 从HTML中提取METAR数据
            metar_text = parse_SPECIAL_METAR_API_URL_metar(res.text)
            if metar_text:
                logger.info(f"SPECIAL_METAR_API_URL 返回原始METAR: {metar_text}")
                cleaned_metar = clean_metar(metar_text)
                logger.info(f"返回清理后的METAR: {cleaned_metar}")
                # 缓存结果
                set_cached_metar(airport, cleaned_metar)
                return cleaned_metar
            else:
                logger.warning(f"SPECIAL_METAR_API_URL 返回的数据中未找到METAR")
        elif res.status_code == 500:
            logger.warning(f"SPECIAL_METAR_API_URL 服务器错误 (500) 对于 {airport}")
        else:
            logger.warning(f"SPECIAL_METAR_API_URL 响应异常: {res.status_code}")
    except Exception as e:
        logger.error(f"从 SPECIAL_METAR_API_URL 获取数据时出错: {e}")
    
    # 第三优先级：apocfly.com
    try:
        # 添加随机延迟，避免请求过于频繁
        time.sleep(random.uniform(0.5, 1.0))
        
        logger.info(f"尝试从 apocfly.com 获取 {airport} 的METAR数据")
        res = requests.get(
            f"https://www.apocfly.com/api/metar?icao={airport}", 
            headers=get_headers(),
            timeout=5
        )
        logger.info(f"apocfly.com 响应状态码: {res.status_code}")
        
        if res.status_code == 200:
            data = json.loads(res.text)
            logger.info(f"apocfly.com 返回数据: {data}")
            
            if data.get("code") == "GET_METAR" and data.get("data") and len(data["data"]) > 0:
                metar_text = data["data"][0]
                logger.info(f"apocfly.com 返回原始METAR: {metar_text}")
                cleaned_metar = clean_metar(metar_text)
                logger.info(f"返回清理后的METAR: {cleaned_metar}")
                # 缓存结果
                set_cached_metar(airport, cleaned_metar)
                return cleaned_metar
            else:
                logger.warning(f"apocfly.com 返回数据格式异常或无数据")
        elif res.status_code == 429:
            logger.warning(f"apocfly.com 返回429，请求过于频繁")
        elif res.status_code == 404:
            logger.info(f"apocfly.com 未找到数据 (404) 对于 {airport}")
        else:
            logger.warning(f"apocfly.com 响应异常: {res.status_code}")
    except Exception as e:
        logger.error(f"从 apocfly.com 获取数据时出错: {e}")
    
    # 如果上述源都失败，尝试其他备用源
    backup_apis = [
        f"https://metar.vatsim.net/{airport}",
        f"https://avwx.rest/api/metar/{airport}",
        f"https://aviationweather.gov/cgi-bin/data/metar.php?ids={airport}",
    ]
    
    for api_url in backup_apis:
        try:
            # 添加随机延迟
            time.sleep(random.uniform(0.3, 0.7))
            
            logger.info(f"尝试从备用源 {api_url} 获取 {airport} 的METAR数据")
            res = requests.get(api_url, headers=get_headers(), timeout=5)
            logger.info(f"备用源 {api_url} 响应状态码: {res.status_code}")
            
            if res.status_code == 200:
                metar_text = res.text.strip()
                if metar_text and "not found" not in metar_text.lower() and "error" not in metar_text.lower():
                    logger.info(f"备用源 {api_url} 返回原始数据: {metar_text}")
                    cleaned_metar = clean_metar(metar_text)
                    logger.info(f"返回清理后的METAR: {cleaned_metar}")
                    # 缓存结果
                    set_cached_metar(airport, cleaned_metar)
                    return cleaned_metar
        except Exception as e:
            logger.error(f"从备用源 {api_url} 获取数据时出错: {e}")
            continue
    
    # 如果所有源都失败，返回空字符串
    logger.warning(f"无法获取 {airport} 的METAR数据")
    return ""

@app.route('/')
def index():
    return "METAR服务正在运行，请使用 /机场代码 访问，例如 /ZSSS"

@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)