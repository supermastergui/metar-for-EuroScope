import requests, json
from flask import Flask
# import logging
import time
import random
import re
from threading import Lock
# import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging.handlers
# import os

# 配置日志 - 只记录我们自己的日志，不记录werkzeug的访问日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 关闭werkzeug的访问日志
logging.getLogger('werkzeug').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# 缓存机制
metar_cache = {}
cache_lock = Lock()
CACHE_TIMEOUT = 300  # 5分钟缓存

# VATSIM数据缓存
vatsim_all_cache = None
vatsim_cache_time = 0
vatsim_cache_timeout = 60  # 1分钟VATSIM缓存

# 用户代理列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
]

# 正则表达式模式 - 允许大写字母
VALID_AIRPORT_PATTERN = re.compile(r'^[A-Z]{4}$')
AIRPORT_LIST_PATTERN = re.compile(r'^[A-Z]{4}(?:,[A-Z]{4})*$')

# 添加允许小写和大写混合的模式
VALID_AIRPORT_PATTERN_CASE_INSENSITIVE = re.compile(r'^[A-Za-z]{4}$')
AIRPORT_LIST_PATTERN_CASE_INSENSITIVE = re.compile(r'^[A-Za-z]{4}(?:,[A-Za-z]{4})*$')


def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/plain,application/json',
    }


def clean_metar(metar_text):
    """清理METAR文本"""
    if not metar_text:
        return metar_text

    metar_text = metar_text.strip()

    # 移除METAR/TAF/SPECI前缀
    prefixes = ["METAR ", "TAF ", "SPECI "]
    for prefix in prefixes:
        if metar_text.startswith(prefix):
            return metar_text[len(prefix):]

    # 移除尾部多余空格和=
    metar_text = metar_text.rstrip('= ')

    return metar_text


def fetch_vatsim_all_cached():
    """获取缓存的VATSIM ALL数据"""
    global vatsim_all_cache, vatsim_cache_time

    current_time = time.time()
    # 如果缓存有效，直接返回
    if vatsim_all_cache and (current_time - vatsim_cache_time) < vatsim_cache_timeout:
        logger.debug("使用缓存的VATSIM ALL数据")
        return vatsim_all_cache

    try:
        logger.debug("重新获取VATSIM ALL数据")
        res = requests.get(
            "https://metar.vatsim.net/all",
            headers=get_headers(),
            timeout=5
        )

        if res.status_code == 200:
            vatsim_all_cache = res.text
            vatsim_cache_time = current_time
            logger.info(f"获取VATSIM ALL数据成功，长度: {len(vatsim_all_cache)}")
            return vatsim_all_cache
        else:
            logger.warning(f"VATSIM ALL返回状态码: {res.status_code}")
            return None
    except Exception as e:
        logger.error(f"从VATSIM获取数据时出错: {e}")
        return vatsim_all_cache  # 返回旧的缓存数据


def parse_metar_from_vatsim_all(text, airport_codes):
    """从VATSIM ALL数据中提取特定机场的METAR"""
    results = {}
    try:
        if not text:
            return results

        # 创建机场代码集合用于快速查找
        airport_set = set(airport_codes)
        found_airports = set()

        # 分割行并查找
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否以机场代码开头
            for airport in airport_set - found_airports:
                # 检查格式：机场代码开头或者METAR/SPECI后跟机场代码
                if (line.startswith(airport + ' ') or
                        line.startswith('METAR ' + airport + ' ') or
                        line.startswith('SPECI ' + airport + ' ')):
                    results[airport] = clean_metar(line)
                    found_airports.add(airport)
                    break

            # 如果所有机场都已找到，提前退出
            if found_airports == airport_set:
                break

        return results
    except Exception as e:
        logger.error(f"解析VATSIM ALL数据时出错: {e}")
        return {}


def fetch_aviationweather_gov_bulk(airports_list):
    """从aviationweather.gov批量获取METAR数据"""
    if not airports_list:
        return {}

    try:
        airports_str = ','.join(airports_list)

        res = requests.get(
            f"https://aviationweather.gov/api/data/metar?ids={airports_str}",
            headers=get_headers(),
            timeout=3
        )

        results = {}
        if res.status_code == 200 and res.text.strip():
            metars = res.text.strip().split('\n')

            for i, airport in enumerate(airports_list):
                if i < len(metars):
                    metar_text = metars[i].strip()
                    if metar_text and "not found" not in metar_text.lower():
                        results[airport] = clean_metar(metar_text)
                    else:
                        results[airport] = ""
                else:
                    results[airport] = ""

            if results:
                valid_count = len([v for v in results.values() if v])
                if valid_count > 0:
                    logger.info(f"aviationweather.gov获取成功: {valid_count}个机场")
            return results
        elif res.status_code == 204:
            logger.debug("aviationweather.gov返回204 - 无内容")
            return {airport: "" for airport in airports_list}
        else:
            logger.debug(f"aviationweather.gov返回状态码: {res.status_code}")
            return {}

    except Exception as e:
        logger.debug(f"aviationweather.gov请求出错: {e}")
        return {}


def fetch_apocfly_bulk(airports_list):
    """从apocfly.com批量获取METAR数据"""
    if not airports_list:
        return {}

    try:
        airports_str = ','.join(airports_list)

        res = requests.get(
            f"https://www.apocfly.com/api/metar?icao={airports_str}",
            headers=get_headers(),
            timeout=3
        )

        results = {}
        if res.status_code == 200:
            try:
                data = res.json()
                if data.get("code") == "GET_METAR" and data.get("data"):
                    metars = data["data"]

                    for i, airport in enumerate(airports_list):
                        if i < len(metars) and metars[i]:
                            results[airport] = clean_metar(metars[i])
                        else:
                            results[airport] = ""

                    if results:
                        valid_count = len([v for v in results.values() if v])
                        if valid_count > 0:
                            logger.info(f"apocfly.com获取成功: {valid_count}个机场")
                    return results
                else:
                    logger.debug("apocfly.com返回数据格式异常")
                    return {}
            except json.JSONDecodeError:
                logger.debug("apocfly.com返回非JSON数据")
                return {}
        elif res.status_code == 404:
            logger.debug("apocfly.com返回404 - 未找到")
            return {airport: "" for airport in airports_list}
        else:
            logger.debug(f"apocfly.com返回状态码: {res.status_code}")
            return {}

    except Exception as e:
        logger.debug(f"apocfly.com请求出错: {e}")
        return {}

def get_cached_metar(airport):
    """获取缓存的METAR数据"""
    with cache_lock:
        if airport in metar_cache:
            data, timestamp = metar_cache[airport]
            if time.time() - timestamp < CACHE_TIMEOUT:
                return data
            else:
                del metar_cache[airport]
    return None


def set_cached_metar(airport, metar_data):
    """设置缓存的METAR数据"""
    if metar_data:  # 只缓存有效数据
        with cache_lock:
            metar_cache[airport] = (metar_data, time.time())


def normalize_airport_codes(airports_str):
    """标准化机场代码，转换为大写并验证格式"""
    # 转换为大写
    airports_upper = airports_str.upper()

    # 检查是否是多个机场
    if ',' in airports_upper:
        # 验证机场代码列表格式
        if not AIRPORT_LIST_PATTERN.match(airports_upper):
            raise ValueError(f"无效的机场代码列表: {airports_str}")

        airports_list = airports_upper.split(',')
        # 去重
        airports_list = list(dict.fromkeys(airports_list))
        return airports_list
    else:
        # 单个机场处理
        if not VALID_AIRPORT_PATTERN.match(airports_upper):
            raise ValueError(f"无效的机场代码: {airports_str}")
        return [airports_upper]


def fetch_metar_for_airports(airports_list):
    """获取多个机场的METAR数据（优化版本）"""
    if not airports_list:
        return {}

    results = {}

    # 第1步：检查缓存
    cached_airports = []
    for airport in airports_list:
        cached = get_cached_metar(airport)
        if cached:
            results[airport] = cached
            cached_airports.append(airport)

    remaining_airports = [a for a in airports_list if a not in cached_airports]
    if not remaining_airports:
        return results

    logger.info(f"需要从网络获取的机场: {remaining_airports}")

    # 第2步：并发请求所有数据源
    with ThreadPoolExecutor(max_workers=10) as executor:
        # 准备所有任务
        future_to_source = {}

        # 获取缓存的VATSIM数据（快速）
        vatsim_data = fetch_vatsim_all_cached()
        if vatsim_data:
            future = executor.submit(parse_metar_from_vatsim_all, vatsim_data, remaining_airports)
            future_to_source[future] = "vatsim"

        # aviationweather.gov批量请求
        if remaining_airports:
            future = executor.submit(fetch_aviationweather_gov_bulk, remaining_airports)
            future_to_source[future] = "aviationweather"

        # apocfly.com批量请求
        if remaining_airports:
            future = executor.submit(fetch_apocfly_bulk, remaining_airports)
            future_to_source[future] = "apocfly"


        # 处理结果，按照优先级
        source_priority = {
            "vatsim": 1,
            "aviationweather": 2,
            "apocfly": 3,
        }

        # 按照优先级顺序处理已完成的任务
        completed_results = {}

        for future in as_completed(future_to_source.keys(), timeout=3):
            source = future_to_source[future]
            try:
                data = future.result(timeout=1)
                if data:
                    completed_results[source] = data

                    # 根据数据类型处理
                    if source in ["vatsim", "aviationweather", "apocfly"]:
                        # 批量数据
                        if isinstance(data, dict):
                            for airport in remaining_airports:
                                if airport in data and data[airport] and airport not in results:
                                    results[airport] = data[airport]
                                    set_cached_metar(airport, data[airport])
                        if airport and airport not in results and data:
                            results[airport] = data
                            set_cached_metar(airport, data)

            except Exception as e:
                logger.debug(f"处理{source}结果时出错: {e}")

    # 确保所有请求的机场都有结果
    for airport in airports_list:
        if airport not in results:
            results[airport] = ""

    return results


@app.route('/<string:airports>', methods=['GET'])
def handle_airports(airports):
    try:
        # 处理空请求
        if not airports:
            return json.dumps({"error": "No airport codes provided"}), 400

        # 标准化机场代码（自动转换为大写）
        try:
            airports_list = normalize_airport_codes(airports)
        except ValueError as e:
            logger.warning(str(e))
            return json.dumps({"error": str(e)}), 400

        # 检查是否是多个机场
        if len(airports_list) > 1:
            logger.info(f"收到批量机场代码请求: {airports_list}")

            # 获取METAR数据
            start_time = time.time()
            results = fetch_metar_for_airports(airports_list)
            elapsed_time = time.time() - start_time

            logger.info(f"批量请求完成，耗时: {elapsed_time:.2f}秒")

            # 返回JSON格式结果
            response = {
                "success": True,
                "timestamp": time.time(),
                "response_time": f"{elapsed_time:.2f}s",
                "data": results
            }
            return json.dumps(response, ensure_ascii=False)
        else:
            # 单个机场处理
            airport_code = airports_list[0]
            logger.info(f"收到机场代码请求: {airport_code}")

            # 检查缓存
            cached = get_cached_metar(airport_code)
            if cached:
                logger.info(f"返回缓存的METAR数据: {cached}")
                return cached

            # 获取METAR数据
            start_time = time.time()
            results = fetch_metar_for_airports([airport_code])
            elapsed_time = time.time() - start_time

            logger.info(f"请求完成，耗时: {elapsed_time:.2f}秒")

            metar = results.get(airport_code, "")

            if metar:
                return metar
            else:
                logger.warning(f"无法获取 {airport_code} 的METAR数据")
                return ""
    except Exception as e:
        logger.error(f"处理请求时发生错误: {e}")
        return json.dumps({"error": "Internal server error"}), 500


@app.route('/')
def index():
    return """
    <html>
        <head>
            <title>METAR 服务</title>
            <meta charset="utf-8">
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #333; }
                code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
                .example { background: #f8f9fa; padding: 10px; border-left: 3px solid #007bff; margin: 10px 0; }
                .endpoint { font-weight: bold; color: #007bff; }
                .priority { background: #e9ecef; padding: 5px 10px; border-radius: 4px; margin: 5px 0; }
                .note { background: #fff3cd; padding: 10px; border-radius: 4px; margin: 10px 0; border: 1px solid #ffeaa7; }
            </style>
        </head>
        <body>
            <h1>METAR 服务</h1>

            <div class="note">
                <strong>注意：</strong>机场代码不区分大小写，会自动转换为大写。
            </div>

            <p>使用方式：</p>

            <div class="example">
                <p><strong>单个机场：</strong></p>
                <p><span class="endpoint">GET /机场代码</span></p>
                <p>示例：</p>
                <ul>
                    <li><a href="/ZSSS" target="_blank">/ZSSS</a> (大写)</li>
                    <li><a href="/zsss" target="_blank">/zsss</a> (小写)</li>
                    <li><a href="/zBaA" target="_blank">/zBaA</a> (混合大小写)</li>
                </ul>
            </div>

            <div class="example">
                <p><strong>多个机场：</strong></p>
                <p><span class="endpoint">GET /机场代码1,机场代码2,机场代码3</span></p>
                <p>示例：</p>
                <ul>
                    <li><a href="/ZSSS,ZBAA" target="_blank">/ZSSS,ZBAA</a> (大写)</li>
                    <li><a href="/zsss,zbaa" target="_blank">/zsss,zbaa</a> (小写)</li>
                    <li><a href="/ZSSS,zbaa,RJTT" target="_blank">/ZSSS,zbaa,RJTT</a> (混合大小写)</li>
                </ul>
            </div>

            <p><strong>数据源优先级：</strong></p>
            <ol>
                <li class="priority">缓存 (5分钟有效期)</li>
                <li class="priority">VATSIM ALL (缓存60秒)</li>
                <li class="priority">aviationweather.gov</li>
                <li class="priority">apocfly.com</li>
            </ol>

            <p><strong>返回格式：</strong></p>
            <ul>
                <li>单个机场：纯文本METAR报文</li>
                <li>多个机场：JSON格式，包含所有请求机场的数据</li>
            </ul>

            <p><strong>其他端点：</strong></p>
            <ul>
                <li><a href="/health" target="_blank">/health</a> - 健康检查</li>
                <li><a href="/cache/clear" target="_blank">/cache/clear</a> - 清空缓存</li>
            </ul>
        </body>
    </html>
    """


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/health')
def health_check():
    """健康检查端点"""
    return json.dumps({
        "status": "healthy",
        "timestamp": time.time(),
        "cache_size": len(metar_cache),
        "vatsim_cache": "available" if vatsim_all_cache else "none",
        "version": "1.0.0"
    })


@app.route('/cache/clear')
def clear_cache():
    """清空缓存"""
    global vatsim_all_cache, vatsim_cache_time

    with cache_lock:
        metar_cache.clear()
        vatsim_all_cache = None
        vatsim_cache_time = 0

    return json.dumps({
        "status": "success",
        "message": "All caches cleared",
        "timestamp": time.time()
    })


if __name__ == '__main__':
    # 设置werkzeug日志级别为WARNING，减少访问日志输出
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    # 预加载VATSIM数据
    logger.info("预加载VATSIM数据...")
    fetch_vatsim_all_cached()

    # 运行应用
    logger.info("METAR服务启动中...")
    logger.info(f"服务地址: http://localhost:8000")
    logger.info("按 Ctrl+C 停止服务")

    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)