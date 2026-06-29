"""
app.py — FastAPI 后端入口（网站的"接线员"）
============================================
这个文件是网站的后端核心，负责：
  1. 创建 FastAPI 应用（Web 服务器）
  2. 定义 7 个 API 接口（前端通过 URL 访问这些接口拿数据）
  3. 挂载静态文件（HTML、CSS、JS、GeoJSON）让浏览器能访问
  4. 处理异常（文件找不到 → 404，其他错误 → 500）

一个 API 接口的完整旅程（以"全球年均温"为例）：
  浏览器 JS 代码:
    fetch("/api/global/annual?min_year=1900")
      ↓ HTTP GET 请求
  app.py 的 api_global_annual() 函数:
    1. 调用 engine.get_global_annual(min_year=1900)
    2. engine 去读 CSV、清洗、聚合
    3. 返回 DataFrame
    4. 把 DataFrame 转成 dict（字典）
    5. FastAPI 自动把 dict 转成 JSON 字符串
      ↓ HTTP Response (JSON)
  浏览器 JS 代码收到 JSON，喂给 ECharts 画图

URL 路由一览：
  GET /                         → 返回 index.html 页面
  GET /api/global/annual        → 全球年均温（多线图数据）
  GET /api/global/anomaly       → 全球温度距平（柱状图数据）
  GET /api/global/monthly       → 月均温季节周期
  GET /api/global/seasonal-anomaly → 季节距平热力图（当前前端未使用）
  GET /api/country/annual       → 某年各国温度（地图数据）
  GET /api/city-temp            → 城市温度排名
  GET /api/city/latband         → 纬度带温度趋势
  GET /api/state-temp           → 省/州温度排名
"""

import math
from pathlib import Path
from typing import Union

import uvicorn               # ASGI 服务器——真正"跑起来"的工具
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .data_engine import DataEngine  # 导入我们自己的数据引擎类


def _nan_to_none(vals):
    """
    把列表里的 NaN 转成 None。

    为什么需要这个？
      NaN（Not a Number）是 IEEE 浮点数标准里的特殊值，pandas 用 NaN 表示"空值"。
      但 JSON 标准不认 NaN——Python 的 json.dumps() 遇到 NaN 会报错。
      所以必须在转 JSON 之前，把 NaN 挨个替换成 None（JSON 里的 null）。

    示例：
      输入: [1.5, NaN, 3.2, NaN]
      输出: [1.5, None, 3.2, None]

    Args:
        vals: 一个列表，可能包含 float NaN

    Returns:
        新列表，NaN 全变成 None
    """
    return [None if (isinstance(v, float) and math.isnan(v)) else v for v in vals]


# ═══════════════════════════════════════════════════════════════
# 创建 FastAPI 应用实例
# ═══════════════════════════════════════════════════════════════
# FastAPI() 创建一个 Web 应用对象。后面的 @app.get() 装饰器
# 就是在给这个应用添加"路由"（URL 和处理函数的对应关系）

app = FastAPI(title="全球气温可视化")  # title 会出现在自动生成的 API 文档里

# ═══════════════════════════════════════════════════════════════
# 路径配置 — 告诉程序文件都在哪里
# ═══════════════════════════════════════════════════════════════

# BASE_DIR = 本文件所在的目录（即 src/）
BASE_DIR = Path(__file__).resolve().parent

# 静态文件目录：src/static/（CSS、JS、图片、GeoJSON 都在这里）
STATIC_DIR = BASE_DIR / "static"

# 首页 HTML 文件：src/templates/index.html
INDEX_PATH = BASE_DIR / "templates" / "index.html"

# ═══════════════════════════════════════════════════════════════
# 挂载静态文件
# ═══════════════════════════════════════════════════════════════
# 这行代码的作用：当浏览器请求 /static/xxx 时，FastAPI 自动去 STATIC_DIR 里找 xxx 文件。
# 比如：浏览器请求 /static/js/dashboard.js → 返回 src/static/js/dashboard.js 的内容
# 不用为每个静态文件单独写一个路由。

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ═══════════════════════════════════════════════════════════════
# 创建数据引擎实例（全局单例，整个应用共用一个）
# ═══════════════════════════════════════════════════════════════

engine = DataEngine()


# ═══════════════════════════════════════════════════════════════
# 路由：首页
# ═══════════════════════════════════════════════════════════════

@app.get("/")
async def index():
    """
    访问 http://localhost:5000/ 时返回 index.html 页面。
    FileResponse = 把文件内容作为 HTTP 响应发给浏览器。
    """
    return FileResponse(str(INDEX_PATH))


# ═══════════════════════════════════════════════════════════════
# API 1：全球年均温
# ═══════════════════════════════════════════════════════════════

@app.get("/api/global/annual")
async def api_global_annual(min_year: int = Query(1850, ge=0)):
    """
    获取全球年均温数据（多条折线）。

    Query(1850, ge=0) 的含义：
      - 默认值 = 1850（前端不传这个参数时就用 1850）
      - ge=0 表示"必须大于等于 0"（FastAPI 会自动校验，不合法就返回 422 错误）

    URL 示例: /api/global/annual?min_year=1950

    返回 JSON 格式:
      {
        "min_year": 1950,
        "years": [1950, 1951, ...],
        "land_avg": [13.5, 13.7, ...],
        "land_max": [25.1, 25.3, ...],
        "land_min": [-2.1, -1.9, ...],
        "land_ocean_avg": [14.0, 14.1, ...],
        "count": 74
      }
    """
    try:
        df = engine.get_global_annual(min_year=min_year)
    except FileNotFoundError as e:
        # CSV 文件不存在 → 返回 404 状态码
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 其他任何异常 → 返回 500 状态码（服务器内部错误）
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "min_year": min_year,
        "years": df["year"].astype(int).tolist(),                # DataFrame 列 → Python 列表
        "land_avg": _nan_to_none(df["land_avg"].round(1).tolist()),
        "land_uncertainty": _nan_to_none(df["land_uncertainty"].round(3).tolist()),
        "land_max": _nan_to_none(df["land_max"].round(1).tolist()),
        "land_min": _nan_to_none(df["land_min"].round(1).tolist()),
        "land_ocean_avg": _nan_to_none(df["land_ocean_avg"].round(1).tolist()),
        "land_ocean_uncertainty": _nan_to_none(df["land_ocean_uncertainty"].round(3).tolist()),
        "count": len(df),
    }


# ═══════════════════════════════════════════════════════════════
# API 2：全球温度距平
# ═══════════════════════════════════════════════════════════════

@app.get("/api/global/anomaly")
async def api_global_anomaly(
    baseline_start: int = Query(1951, ge=0),
    baseline_end: int = Query(1980, ge=0),
):
    """
    获取全球温度距平数据（柱状图）。

    可以自定义基准期（比如改成 1961-1990），默认使用 1951-1980。

    URL 示例: /api/global/anomaly?baseline_start=1951&baseline_end=1980
    """
    try:
        # DataEngine 已经返回了字典格式，直接返回即可
        return engine.get_global_anomaly(
            baseline_start=baseline_start, baseline_end=baseline_end
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# API 3：月均温季节周期
# ═══════════════════════════════════════════════════════════════

@app.get("/api/global/monthly")
async def api_global_monthly():
    """
    获取各月平均温度（1~12 月）。

    不需要任何参数——直接返回所有年份的逐月平均值。

    URL 示例: /api/global/monthly
    """
    try:
        df = engine.get_global_monthly()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    temps = df["temperature"].tolist()
    return {
        "months": df["month"].astype(int).tolist(),
        # 同样要处理 NaN → None
        "temps": [
            round(t, 1) if not (isinstance(t, float) and math.isnan(t)) else None
            for t in temps
        ],
    }


# ═══════════════════════════════════════════════════════════════
# API 4：季节距平热力图数据（当前前端未使用）
# ═══════════════════════════════════════════════════════════════

@app.get("/api/global/seasonal-anomaly")
async def api_global_seasonal_anomaly(min_year: int = Query(1900, ge=0)):
    """
    获取季节距平矩阵数据（年份 × 月份）。

    注意：当前前端页面没有使用这个 API，但它是可用的。
    """
    try:
        return engine.get_seasonal_anomaly(min_year=min_year)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# API 5：国家年均温（地图用）
# ═══════════════════════════════════════════════════════════════

@app.get("/api/country/annual")
async def api_country_annual(year: int = Query(..., ge=0)):
    """
    获取某一年所有国家的平均温度。

    Query(...) 的含义：
      ...（省略号）= 必填参数，前端必须传这个参数。
      不传的话 FastAPI 直接返回 422 错误。

    URL 示例: /api/country/annual?year=2024
    """
    try:
        df = engine.get_country_annual(year=year)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "year": year,
        "countries": df["Country"].tolist(),
        "temps": df["temperature"].round(1).tolist(),
        "count": len(df),
    }


# ═══════════════════════════════════════════════════════════════
# API 6：城市温度排名
# ═══════════════════════════════════════════════════════════════

@app.get("/api/city-temp")
async def api_city_temp(
    year: int = Query(..., ge=0),
    limit: int = Query(20, ge=1, le=100),           # 最少 1 个，最多 100 个
    country: Union[str, None] = Query(None),         # 可选参数，不传 = None
):
    """
    获取某年某国的城市温度排名（前 N 名）。

    URL 示例:
      /api/city-temp?year=2024&country=China&limit=15
      /api/city-temp?year=2023&limit=10  （不传 country = 全球排名）
    """
    try:
        df = engine.get_city_temp_by_year(year=year, limit=limit, country=country)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "year": year,
        "cities": df["City"].astype(str).tolist(),
        "temps": df["temperature"].astype(float).round(1).tolist(),
        "count": len(df),
    }


# ═══════════════════════════════════════════════════════════════
# API 7：纬度带温度趋势
# ═══════════════════════════════════════════════════════════════

@app.get("/api/city/latband")
async def api_city_latband(min_year: int = Query(1850, ge=0)):
    """
    获取热带/温带/寒带的温度趋势数据。

    返回的数据结构比较特殊：3 条线各有自己的数组。
    前端用 3 个 ECharts series 分别画。

    URL 示例: /api/city/latband?min_year=1900
    """
    try:
        df = engine.get_city_latband(min_year=min_year)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 三个纬度带的顺序和中文名
    bands = ["tropical", "temperate", "polar"]
    band_labels = {"tropical": "热带", "temperate": "温带", "polar": "寒带"}

    # 年份列表（去重 + 排序 + 转整数）
    years = sorted(df["year"].unique().astype(int).tolist())

    result: dict = {"min_year": min_year, "years": years}

    for band in bands:
        # 从 DataFrame 中筛出这个纬度带的全部行
        subset = df[df["band"] == band]

        # 构造一个字典：{年份: 温度}，方便查找
        temp_map = dict(zip(subset["year"], subset["temperature"]))
        # zip() 把两个列表配对：[(2020, 25.3), (2021, 25.6), ...]
        # dict() 转成 {2020: 25.3, 2021: 25.6, ...}

        # 对每个年份，去 temp_map 里找对应的温度值
        result[band] = [
            round(float(temp_map[y]), 1)
            if y in temp_map and not (isinstance(temp_map[y], float) and math.isnan(temp_map[y]))
            else None
            for y in years
        ]
        # 加上中文标签
        result[f"{band}_label"] = band_labels[band]

    result["count"] = len(years)
    return result


# ═══════════════════════════════════════════════════════════════
# API 8：省/州温度排名
# ═══════════════════════════════════════════════════════════════

@app.get("/api/state-temp")
async def api_state_temp(
    year: int = Query(..., ge=0),
    country: str = Query("United States"),           # 默认查美国
    limit: int = Query(15, ge=1, le=100),
):
    """
    获取某年某国省/州级温度排名。

    URL 示例: /api/state-temp?year=2024&country=China&limit=15
    """
    try:
        df = engine.get_state_temp_by_year(year=year, country=country, limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "year": year,
        "country": country,
        "states": df["State"].astype(str).tolist(),
        "temps": df["temperature"].astype(float).round(1).tolist(),
        "count": len(df),
    }


# ═══════════════════════════════════════════════════════════════
# 程序入口 — 直接运行 python app.py 时启动服务器
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # uvicorn 是一个高性能的 ASGI 服务器（跑 Python Web 应用的通用方案）
    # "src.app:app" = 模块路径:变量名（告诉 uvicorn 去哪里找 app 对象）
    # host="0.0.0.0" = 监听所有网络接口（局域网其他设备也能访问）
    # port=5000 = 端口号
    # reload=True = 开发模式：检测到代码变化自动重启（生产环境应该关掉）
    uvicorn.run("src.app:app", host="0.0.0.0", port=5000, reload=True)
