import requests, json
from flask import Flask
import logging
import time
import random
import re

SPECIAL_METAR_API_URL = "!ENV SPECIAL_MATER_API"  # 让它易于替换

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 用户代理列表，模拟不同浏览器
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS)
    }

def clean_metar(metar_text):
    """清理METAR文本，移除开头的'METAR '前缀"""
    if metar_text and metar_text.startswith("METAR "):
        return metar_text[6:]  # 移除前6个字符 ("METAR ")
    return metar_text

def parse_special_metar(html_content):
    """从API的HTML响应中提取METAR数据"""
    try:
        # 使用正则表达式匹配METAR行
        metar_pattern = r'METAR\s+[A-Z]{4}\s+\d{6}Z\s+[^=]+='
        matches = re.findall(metar_pattern, html_content)
        
        if matches:
            # 返回第一个METAR
            return matches[0]
        else:
            logger.warning("未在API响应中找到METAR数据")
            return None
    except Exception as e:
        logger.error(f"解析API响应时出错: {e}")
        return None

@app.route('/<string:airport>', methods=['GET'])
def handle_airports(airport):
    logger.info(f"收到机场代码请求: {airport}")
    
    # 首先尝试主源 aviationweather.gov
    try:
        logger.info(f"尝试从 aviationweather.gov 获取 {airport} 的METAR数据")
        res = requests.get(
            f"https://aviationweather.gov/api/data/metar?ids={airport}", 
            headers=get_headers(),
            timeout=10
        )
        logger.info(f"aviationweather.gov 响应状态码: {res.status_code}")
        
        if res.status_code == 200 and res.text.strip():
            metar_text = res.text.strip()
            logger.info(f"aviationweather.gov 返回原始数据: {metar_text}")
            
            if metar_text and "not found" not in metar_text.lower():
                cleaned_metar = clean_metar(metar_text)
                logger.info(f"返回清理后的METAR: {cleaned_metar}")
                return cleaned_metar
        else:
            logger.warning(f"aviationweather.gov 响应异常: {res.status_code}")
    except Exception as e:
        logger.error(f"从 aviationweather.gov 获取数据时出错: {e}")
    
    # 第二优先级：API
    try:
        # 添加随机延迟，避免请求过于频繁
        time.sleep(random.uniform(0.5, 1.5))
        
        logger.info(f"尝试从 SPECIAL_MATER_API 获取 {airport} 的METAR数据")
        res = requests.get(
		SPECIAL_METAR_API_URL, 
		headers=get_headers(),
		timeout=10
		)

        logger.info(f"SPECIAL_MATER_API 响应状态码: {res.status_code}")
        
        if res.status_code == 200:
            # 从HTML中提取METAR数据
            metar_text = parse_special_metar(res.text)
            if metar_text:
                logger.info(f"SPECIAL_MATER_API 返回原始METAR: {metar_text}")
                cleaned_metar = clean_metar(metar_text)
                logger.info(f"返回清理后的METAR: {cleaned_metar}")
                return cleaned_metar
            else:
                logger.warning(f"SPECIAL_MATER_API 返回的数据中未找到METAR")
        else:
            logger.warning(f"SPECIAL_MATER_API 响应异常: {res.status_code}")
    except Exception as e:
        logger.error(f"从 SPECIAL_MATER_API 获取数据时出错: {e}")
    
    # 第三优先级：apocfly.com
    try:
        # 添加随机延迟，避免请求过于频繁
        time.sleep(random.uniform(0.5, 1.5))
        
        logger.info(f"尝试从 apocfly.com 获取 {airport} 的METAR数据")
        res = requests.get(
            f"https://www.apocfly.com/api/metar?icao={airport}", 
            headers=get_headers(),
            timeout=10
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
                return cleaned_metar
            else:
                logger.warning(f"apocfly.com 返回数据格式异常或无数据")
        elif res.status_code == 429:
            logger.warning(f"apocfly.com 返回429，请求过于频繁")
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
            time.sleep(random.uniform(0.5, 1.0))
            
            logger.info(f"尝试从备用源 {api_url} 获取 {airport} 的METAR数据")
            res = requests.get(api_url, headers=get_headers(), timeout=10)
            logger.info(f"备用源 {api_url} 响应状态码: {res.status_code}")
            
            if res.status_code == 200:
                metar_text = res.text.strip()
                if metar_text and "not found" not in metar_text.lower() and "error" not in metar_text.lower():
                    logger.info(f"备用源 {api_url} 返回原始数据: {metar_text}")
                    cleaned_metar = clean_metar(metar_text)
                    logger.info(f"返回清理后的METAR: {cleaned_metar}")
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
    app.run(host='0.0.0.0', port=8000, debug=True)