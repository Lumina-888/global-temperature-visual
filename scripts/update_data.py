"""
update_data.py — NASA 数据下载与更新脚本
==========================================
这个脚本好比一个"自动加油站"——定期从 NASA GISTEMP 官网下载最新温度数据，
自动转换格式后追加到项目的 CSV 文件中。

一句话概括：运行一次，数据就更新到最新。

数据更新流程（分 4 步）：
  1. 更新全球温度 CSV（GlobalTemperatures.csv）
     ↓ 从 NASA 下载 GLB.Ts+dSST.csv（全球月度距平）
     ↓ 距平值 + 基准均值 = 绝对温度
     ↓ 追加 2016~2026 年的数据

  2. 下载台站清单和温度数据
     ↓ v4.temperature.inv.txt（27,958 个气象台站的位置、名称）
     ↓ v4.mean_GISS_homogenized.txt.gz（35MB 压缩文件，所有台站的温度记录）

  3. 更新城市级 CSV
     ↓ 把台站按地理坐标匹配到城市（200km 以内算匹配）
     ↓ 聚合每个城市的所有台站数据 → 追加到 City CSV

  4. 更新国家 CSV
     ↓ 通过 FIPS 代码把台站归类到国家
     ↓ 聚合同一国所有台站 → 追加到 Country CSV

数据来源全部来自: https://data.giss.nasa.gov/gistemp/

使用方法：
    cd scripts/
    python update_data.py

运行时间约 1~3 分钟（取决于下载 35MB 台站数据的速度）。
"""

import csv
import gzip
import io
import math
from collections import defaultdict
from pathlib import Path

import requests  # 用来从网上下载数据的库（类似浏览器但用代码控制）

# ── 路径设置 ─────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent          # 本脚本所在目录（scripts/）
DATASET_DIR = SCRIPT_DIR.parent / "src" / "dataset"   # CSV 数据存放目录（src/dataset/）
GISS_BASE = "https://data.giss.nasa.gov/gistemp"     # NASA 数据的基础 URL

# ═══════════════════════════════════════════════════════════════
# FIPS 代码映射表 — 把 2 字母的地区代码转成国家全名
# ═══════════════════════════════════════════════════════════════
# FIPS = Federal Information Processing Standards（美国联邦信息处理标准）
# NASA 用 FIPS 10-4 代码来标记每个气象台站属于哪个国家/地区
# 比如 "CH" → "China"，"US" → "United States"

FIPS_TO_COUNTRY: dict[str, str] = {
    "AC": "Antigua and Barbuda", "AE": "United Arab Emirates", "AF": "Afghanistan",
    "AG": "Algeria", "AJ": "Azerbaijan", "AL": "Albania", "AM": "Armenia",
    "AO": "Angola", "AR": "Argentina", "AS": "Australia", "AU": "Austria",
    "AY": "Antarctica", "BA": "Bahrain", "BB": "Barbados", "BC": "Botswana",
    "BD": "Bermuda", "BE": "Belgium", "BF": "Bahamas", "BG": "Bangladesh",
    "BH": "Belize", "BK": "Bosnia and Herzegovina", "BL": "Bolivia",
    "BM": "Burma", "BN": "Benin", "BO": "Belarus", "BP": "Solomon Islands",
    "BR": "Brazil", "BT": "Bhutan", "BU": "Bulgaria", "BX": "Brunei",
    "BY": "Burundi", "CA": "Canada", "CB": "Cambodia", "CD": "Chad",
    "CE": "Sri Lanka", "CF": "Congo", "CG": "Congo (Democratic Republic of the)",
    "CH": "China", "CI": "Chile", "CJ": "Cayman Islands", "CK": "Cocos Islands",
    "CM": "Cameroon", "CN": "Comoros", "CO": "Colombia", "CR": "Costa Rica",
    "CS": "Costa Rica", "CT": "Central African Republic", "CU": "Cuba",
    "CV": "Cape Verde", "CW": "Cook Islands", "CY": "Cyprus",
    "CZ": "Czech Republic", "DA": "Denmark", "DJ": "Djibouti", "DO": "Dominica",
    "DR": "Dominican Republic", "EC": "Ecuador", "EG": "Egypt", "EI": "Ireland",
    "EK": "Equatorial Guinea", "EN": "Estonia", "ER": "Eritrea", "ES": "El Salvador",
    "ET": "Ethiopia", "EZ": "Czech Republic", "FG": "French Guiana", "FI": "Finland",
    "FJ": "Fiji", "FM": "Micronesia", "FP": "French Polynesia", "FR": "France",
    "FS": "French Southern Territories", "GA": "Gambia", "GB": "Gabon",
    "GG": "Georgia", "GH": "Ghana", "GI": "Gibraltar", "GJ": "Grenada",
    "GK": "Guernsey", "GL": "Greenland", "GM": "Germany", "GP": "Guadeloupe",
    "GR": "Greece", "GT": "Guatemala", "GV": "Guinea", "GY": "Guyana",
    "HA": "Haiti", "HK": "Hong Kong", "HO": "Honduras", "HR": "Croatia",
    "HU": "Hungary", "IC": "Iceland", "ID": "Indonesia", "IM": "Isle of Man",
    "IN": "India", "IO": "British Indian Ocean Territory", "IP": "Clipperton Island",
    "IR": "Iran", "IS": "Israel", "IT": "Italy", "IV": "Côte D'Ivoire",
    "IW": "Israel", "IZ": "Iraq", "JA": "Japan", "JE": "Jersey",
    "JM": "Jamaica", "JO": "Jordan", "KE": "Kenya", "KG": "Kyrgyzstan",
    "KN": "North Korea", "KR": "Kiribati", "KS": "South Korea", "KT": "Christmas Island",
    "KU": "Kuwait", "KZ": "Kazakhstan", "LA": "Laos", "LE": "Lebanon",
    "LG": "Latvia", "LH": "Lithuania", "LI": "Liberia", "LO": "Slovakia",
    "LS": "Liechtenstein", "LT": "Lesotho", "LU": "Luxembourg", "LY": "Libya",
    "MA": "Madagascar", "MB": "Martinique", "MC": "Macau", "MD": "Moldova",
    "MF": "Mayotte", "MG": "Mongolia", "MH": "Montserrat", "MI": "Malawi",
    "MJ": "Montenegro", "MK": "Macedonia", "ML": "Mali", "MN": "Monaco",
    "MO": "Morocco", "MP": "Mauritius", "MR": "Mauritania", "MS": "Malta",
    "MT": "Oman", "MU": "Oman", "MV": "Maldives", "MW": "Montenegro",
    "MX": "Mexico", "MY": "Malaysia", "MZ": "Mozambique", "NC": "New Caledonia",
    "NG": "Niger", "NH": "Vanuatu", "NI": "Nigeria", "NL": "Netherlands",
    "NN": "Netherlands Antilles", "NO": "Norway", "NP": "Nepal", "NR": "Nauru",
    "NS": "Suriname", "NT": "Netherlands Antilles", "NU": "Nicaragua",
    "NZ": "New Zealand", "OD": "South Sudan", "PA": "Paraguay", "PC": "Pitcairn Islands",
    "PE": "Peru", "PF": "Paracel Islands", "PG": "Spratly Islands", "PH": "Philippines",
    "PI": "Philippines", "PK": "Pakistan", "PL": "Poland", "PM": "Panama",
    "PO": "Portugal", "PP": "Papua New Guinea", "PS": "Palau",
    "PU": "Guinea-Bissau", "QA": "Qatar", "RE": "Reunion", "RI": "Serbia",
    "RM": "Marshall Islands", "RO": "Romania", "RP": "Philippines", "RQ": "Puerto Rico",
    "RS": "Russia", "RW": "Rwanda", "SA": "Saudi Arabia", "SB": "St. Pierre and Miquelon",
    "SC": "St. Kitts and Nevis", "SE": "Seychelles", "SF": "South Africa",
    "SG": "Senegal", "SH": "St. Helena", "SI": "Slovenia", "SL": "Sierra Leone",
    "SM": "San Marino", "SN": "Singapore", "SO": "Somalia", "SP": "Spain",
    "ST": "St. Lucia", "SU": "Sudan", "SV": "Svalbard", "SW": "Sweden",
    "SX": "South Georgia and South Sandwich Islands", "SY": "Syria",
    "SZ": "Switzerland", "TD": "Trinidad and Tobago", "TE": "Timor-Leste",
    "TH": "Thailand", "TI": "Tajikistan", "TK": "Turks and Caicos Islands",
    "TL": "Tokelau", "TN": "Tonga", "TO": "Togo", "TP": "Sao Tome and Principe",
    "TS": "Tunisia", "TU": "Turkey", "TV": "Tuvalu", "TW": "Taiwan",
    "TX": "Turkmenistan", "TZ": "Tanzania", "UG": "Uganda", "UK": "United Kingdom",
    "UP": "Ukraine", "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan",
    "VC": "St. Vincent and the Grenadines", "VE": "Venezuela", "VI": "British Virgin Islands",
    "VM": "Vietnam", "VQ": "United States Virgin Islands", "WA": "Namibia",
    "WE": "West Bank", "WF": "Wallis and Futuna", "WI": "Western Sahara",
    "WS": "Samoa", "WZ": "Swaziland", "YM": "Yemen", "ZA": "Zambia",
    "ZI": "Zimbabwe",
}

# 将 FIPS 映射出的国家名与项目现有数据中的国家名对齐（有些名字不完全一样）
# 比如 NASA 叫 "Congo (Democratic Republic of the)"，现有数据里叫 "Democratic Republic Of The Congo"
COUNTRY_NAME_ALIAS: dict[str, str] = {
    "Côte D'Ivoire": "Côte D'Ivoire",
    "Congo (Democratic Republic of the)": "Democratic Republic Of The Congo",
    "Burma": "Myanmar",
    "United States": "United States",
    "Russia": "Russia",
    "China": "China",
    "Iran": "Iran",
    "North Korea": "North Korea",
    "South Korea": "South Korea",
    "Libya": "Libya",
    "Vietnam": "Vietnam",
}


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def download(url: str) -> str:
    """
    下载文本文件，返回字符串内容。

    就像在浏览器里打开一个文本网址，然后把内容复制出来。
    设置了 120 秒超时（35MB 的压缩文件需要一些时间）。
    """
    print(f"  下载: {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()  # 如果 HTTP 状态码不是 200，抛出异常
    return resp.text


def download_binary(url: str) -> bytes:
    """
    下载二进制文件（比如 .gz 压缩文件），返回原始字节。
    文本文件用 download()，压缩文件用这个。
    """
    print(f"  下载: {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content  # .content = 原始字节，不做文本解码


def extract_country_from_sid(sid: str) -> str:
    """
    从台站 ID 中提取国家名。

    台站 ID 格式：前 2 个字符是 FIPS 国家代码。
    比如 "CH00012345" → 取 "CH" → 查表 → "China"

    如果代码不在映射表里，返回空字符串（表示"未知国家"）。
    找到后在 COUNTRY_NAME_ALIAS 里查一下有没有别名需要转换。
    """
    prefix = sid[0:2].upper()                    # 取前 2 个字符转大写
    if prefix in FIPS_TO_COUNTRY:
        name = FIPS_TO_COUNTRY[prefix]           # 查 FIPS 表
        return COUNTRY_NAME_ALIAS.get(name, name)  # 有别名就用别名，没有就用原名
    return ""


# ═══════════════════════════════════════════════════════════════
# 第 1 步：更新 GlobalTemperatures.csv（全球温度）
# ═══════════════════════════════════════════════════════════════

def update_global_temperatures():
    """
    更新全球温度 CSV 文件。

    详细步骤：
      1. 读现有的 GlobalTemperatures.csv
      2. 计算 1951-1980 的基线均值（这是 GISTEMP 距平的基准期）
      3. 从 NASA 下载 GLB.Ts+dSST.csv（全球月度距平数据）
      4. 距平值 + 基线均值 = 绝对温度
      5. 只追加 2016 年及之后的新数据（避免重复）
      6. 写回 CSV
    """
    print("\n=== 更新 GlobalTemperatures.csv ===")

    csv_path = DATASET_DIR / "GlobalTemperatures.csv"

    # 读取现有 CSV（保留原有数据不动）
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)           # 把每行读成 {列名: 值} 的字典
        fieldnames = reader.fieldnames       # 记住有哪些列（后面写回时用同样的列）
        existing_rows = list(reader)         # 把全部行读到内存

    print(f"  现有行数: {len(existing_rows)}")

    # ── 计算 1951-1980 年 LandAndOcean 基线均值 ──
    # GISTEMP 的距平值是以 1951-1980 为基准的
    # 比如距平 +0.5 表示比 1951-1980 的平均高了 0.5°C
    baseline_temps = []
    for row in existing_rows:
        year_str = row["dt"][:4]  # dt 格式 "1955-06-01"，取前 4 位 = 年份
        if not year_str.isdigit():
            continue
        year = int(year_str)
        if 1951 <= year <= 1980:  # 只取基准期范围内的数据
            val = row.get("LandAndOceanAverageTemperature", "").strip()
            if val:
                baseline_temps.append(float(val))

    # 基线均值 = 所有基准期温度的平均
    # 如果基准期数据不足（极端情况），用 14.0 兜底
    baseline_mean = sum(baseline_temps) / len(baseline_temps) if baseline_temps else 14.0
    print(f"  1951-1980 LandAndOcean 基线均值: {baseline_mean:.4f}°C  (共 {len(baseline_temps)} 月)")

    # ── 下载并解析 GISTEMP GLB.Ts+dSST ──
    # 这个文件结构：
    #   Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec
    #   1880,-0.18,-0.25,...,-0.11
    #   1881,-0.13,-0.17,...,-0.19

    glb_csv = download(f"{GISS_BASE}/tabledata_v4/GLB.Ts+dSST.csv")
    lines = glb_csv.strip().split("\n")

    # 找到标题行（以 "Year" 开头的那行）
    data_start = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("Year"):
            data_start = i
            break

    month_cols = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # 解析所有距平数据，存到字典：{"2024-01": 1.35, "2024-02": 1.42, ...}
    anomalies_by_month: dict[str, float] = {}
    for line in lines[data_start + 1:]:  # 跳过标题行
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 13:              # 至少需要 年份 + 12 个月
            continue
        try:
            year = int(parts[0])
        except ValueError:
            continue
        for m_idx, _ in enumerate(month_cols):
            raw = parts[m_idx + 1]
            # "***" 表示该月无数据
            if raw in ("***", ""):
                continue
            try:
                val = float(raw)
            except ValueError:
                continue
            anomalies_by_month[f"{year:04d}-{m_idx + 1:02d}"] = val
            # f"{year:04d}" = 把年份格式化为 4 位数（比如 2024）
            # f"{m_idx + 1:02d}" = 月份格式化为 2 位数（01, 02, ..., 12）

    # ── 生成新数据行（只追加 2016 年之后的）──
    # 原有数据到 2015-12，避免重复从 2016 开始
    new_rows = []
    for year in range(2016, 2027):  # 2016 ~ 2026
        for month in range(1, 13):
            key = f"{year:04d}-{month:02d}"
            anomaly = anomalies_by_month.get(key)
            if anomaly is None:
                continue  # 该月无数据就跳过

            # 距平 → 绝对温度：绝对温度 = 基准均值 + 距平
            # 比如基准均值 15.30°C，距平 +1.35 → 绝对温度 16.65°C
            land_ocean_temp = round(baseline_mean + anomaly, 3)

            new_rows.append({
                "dt": f"{year:04d}-{month:02d}-01",
                # 注意：新数据只填 LandAndOcean 温度，
                # 陆地温度（LandAverage/Max/Min）留空——NASA 的 GLB 文件只有海陆综合距平
                "LandAverageTemperature": "",
                "LandAverageTemperatureUncertainty": "",
                "LandMaxTemperature": "",
                "LandMaxTemperatureUncertainty": "",
                "LandMinTemperature": "",
                "LandMinTemperatureUncertainty": "",
                "LandAndOceanAverageTemperature": str(land_ocean_temp),
                "LandAndOceanAverageTemperatureUncertainty": "",
            })

    print(f"  新增行数: {len(new_rows)}  (2016 ~ {list(anomalies_by_month.keys())[-1] if anomalies_by_month else 'N/A'})")

    # ── 写回 CSV ──
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()          # 写列名那一行
        for row in existing_rows:     # 先写原有的
            writer.writerow(row)
        for row in new_rows:          # 再写新增的（追加在末尾）
            writer.writerow(row)

    print(f"  ✓ GlobalTemperatures.csv 已更新")


# ═══════════════════════════════════════════════════════════════
# 第 2 步：加载台站清单和温度数据
# ═══════════════════════════════════════════════════════════════

def load_station_inventory() -> dict[str, dict]:
    """
    下载并解析台站清单文件。

    台站清单文件格式（固定宽度）：
      位置  1-11: 台站 ID
      位置 12-20: 纬度
      位置 21-30: 经度
      位置 38-61: 台站名称

    Returns:
        {台站ID: {lat, lon, name, country}, ...}
        比如 {"CH00012345": {"lat": 39.9, "lon": 116.4, "name": "BEIJING", "country": "China"}}
    """
    print("\n  加载台站清单...")
    inv_text = download(f"{GISS_BASE}/station_data_v4_globe/v4.temperature.inv.txt")

    stations: dict[str, dict] = {}
    for line in inv_text.strip().split("\n"):
        if len(line) < 40:  # 有效行至少 40 个字符
            continue

        # 按固定宽度切分每行
        sid = line[0:11].strip()         # 台站 ID（如 "CHM00054511"）
        lat_str = line[11:20].strip()    # 纬度（如 "  39.93  "）
        lon_str = line[20:30].strip()    # 经度（如 " 116.28  "）
        name = line[37:60].strip()       # 台站名称

        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            continue  # 经纬度解析失败，跳过这个台站

        country = extract_country_from_sid(sid)  # 根据 ID 前两位查 FIPS 表
        stations[sid] = {"lat": lat, "lon": lon, "name": name, "country": country}

    print(f"    {len(stations)} 个台站")
    return stations


def load_station_temperatures(stations: dict) -> dict[str, list[tuple[int, int, float]]]:
    """
    下载、解压并解析台站温度数据文件（35MB gzip 压缩文件）。

    文件格式说明：
      每个台站的数据包含：
      - 一个台站头行（包含台站 ID）
      - 若干月度数据行，每行格式（按空白分词）：
        token[0]  = 年份
        token[1]  = 1 月温度
        token[2]  = 2 月温度
        ...
        token[12] = 12 月温度

      温度单位是 0.01°C，所以解析后要除以 100。
      缺失值标记为 -9999 或 9999。
      绝对值 > 8000 的值为异常，跳过。
      绝对值 > 60°C 的温度为极端异常，跳过。

    Args:
        stations: 台站清单字典（从 load_station_inventory() 返回）

    Returns:
        {台站ID: [(年, 月, 温度°C), ...], ...}
    """
    print("  下载台站温度数据 (35MB)...")
    raw = download_binary(
        f"{GISS_BASE}/station_data_v4_globe/v4.mean_GISS_homogenized.txt.gz"
    )
    print("  解压并解析...")

    station_temps: dict[str, list[tuple[int, int, float]]] = {}

    # gzip.open() 直接解压 gzip 数据流
    # io.BytesIO() 把 bytes 包装成"伪文件"供 gzip 读取
    # "rt" = 以文本模式读取（自动解码 UTF-8）
    with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as f:
        current_sid = None  # 当前正在处理的台站 ID
        for line in f:
            line = line.rstrip()  # 去掉行尾换行符
            if not line:
                continue

            # ── 判断是不是台站头行 ──
            # 台站头行的特征：长度 > 40，前 3 个字符是字母
            if len(line) > 40 and line[0:3].isalpha():
                first_token = line[0:11].strip()
                if first_token in stations:
                    current_sid = first_token
                    if current_sid not in station_temps:
                        station_temps[current_sid] = []
                else:
                    current_sid = None  # 不在清单里的台站，忽略
                continue

            # ── 判断是不是月度数据行 ──
            # 特征：有当前台站、长度够、开头 4 个字符是数字（年份）
            if current_sid and len(line) >= 48 and line[0:4].strip().isdigit():
                tokens = line.split()  # 按空白分词（比固定宽度更稳健）
                if len(tokens) < 13:   # 至少需要 年份 + 12 个月
                    continue
                try:
                    year = int(tokens[0])
                except ValueError:
                    continue

                # 解析 12 个月的温度值
                for m in range(12):
                    val_str = tokens[m + 1]
                    if val_str == "-9999" or val_str == "9999":
                        continue  # 缺失值
                    try:
                        val = int(val_str)
                    except ValueError:
                        continue
                    if abs(val) > 8000:  # 异常值过滤
                        continue
                    temp_c = val / 100.0  # 单位转换：0.01°C → °C
                    if abs(temp_c) > 60:  # 极端异常值（地球上不会有 60°C+ 的均温）
                        continue
                    station_temps[current_sid].append((year, m + 1, temp_c))

    print(f"    {len(station_temps)} 个台站有温度数据")
    return station_temps


# ═══════════════════════════════════════════════════════════════
# 第 3 步：更新城市级 CSV
# ═══════════════════════════════════════════════════════════════

def parse_lat_lon(raw_lat: str, raw_lon: str) -> tuple[float, float]:
    """
    解析经纬度字符串。

    输入格式例如:
      "57.05N", "10.33E" → (57.05, 10.33)
      "33.87S", "151.22E" → (-33.87, 151.22)
      "74.62W", "40.0N"  → (-74.62, 40.0)

    N/S 控制纬度的正负（N=正，S=负）
    E/W 控制经度的正负（E=正，W=负）
    """
    lat_str = raw_lat.strip().upper()
    lon_str = raw_lon.strip().upper()

    # 解析纬度
    try:
        if lat_str[-1] in "NS":  # 最后一个字符是 N 或 S
            lat = float(lat_str[:-1])  # 取去掉最后一个字符的部分
            if lat_str[-1] == "S":
                lat = -lat
        else:
            lat = float(lat_str)
    except (ValueError, IndexError):
        lat = 0.0

    # 解析经度
    try:
        if lon_str[-1] in "EW":
            lon = float(lon_str[:-1])
            if lon_str[-1] == "W":
                lon = -lon
        else:
            lon = float(lon_str)
    except (ValueError, IndexError):
        lon = 0.0

    return lat, lon


def update_city_like_csv(filename: str, stations, station_temps):
    """
    更新城市级 CSV 文件（City, MajorCity 等）。

    这个方法比较复杂，核心逻辑是"把台站匹配到城市"：

    匹配算法：
      1. 读现有 CSV，提取已有城市列表及其经纬度
      2. 对每个台站，计算它到所有城市的距离
         （近似公式：经纬度差的平方和开根号 × 111km/度）
      3. 取 200km 范围内最近的城市作为匹配
      4. 匹配到的台站温度按月聚合（同一城市有多个台站 → 取平均）
      5. 新数据追加到 CSV 末尾

    CSV 文件结构理解：
      - 每个城市每个月有一行数据
      - dt 列格式："2013-09-01"（每月 1 号代表该月）
    """
    csv_path = DATASET_DIR / filename
    if not csv_path.exists():
        print(f"  {filename} 不存在，跳过")
        return

    print(f"\n=== 更新 {filename} ===")

    # 读取现有数据
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        existing_rows = list(reader)

    # 找出最后一条数据的时间（避免重复）
    last_date = existing_rows[-1]["dt"] if existing_rows else "2013-09-01"
    last_year = int(last_date[:4])   # 取年份部分
    last_month = int(last_date[5:7]) # 取月份部分
    print(f"  现有数据到: {last_year}-{last_month:02d}")

    # ── 收集已有城市及其坐标 ──
    existing_cities: dict[str, tuple[float, float, str]] = {}
    for row in existing_rows:
        city = row.get("City", "").strip()
        if city and city not in existing_cities:
            lat, lon = parse_lat_lon(row.get("Latitude", "0"), row.get("Longitude", "0"))
            country = row.get("Country", "").strip()
            existing_cities[city] = (lat, lon, country)

    print(f"  已有 {len(existing_cities)} 个城市")

    # ── 台站 → 城市匹配（核心算法）──
    print("  匹配台站到城市...")
    city_to_stations: dict[str, list[str]] = {c: [] for c in existing_cities}

    for sid, info in stations.items():
        slat, slon = info["lat"], info["lon"]  # 台站坐标
        best_city = None
        best_dist = float("inf")               # 初始化为正无穷

        # 遍历所有城市，找最近的
        for city_name, (clat, clon, _) in existing_cities.items():
            dlat = slat - clat  # 纬度差（度）
            dlon = slon - clon  # 经度差（度）
            # 近似距离公式：欧氏距离 × 111km/度
            # （严格来说应该用球面距离公式，但 200km 范围内误差不大）
            dist = math.sqrt(dlat ** 2 + dlon ** 2) * 111.0
            if dist < best_dist and dist < 200:  # 200km 阈值
                best_dist = dist
                best_city = city_name

        if best_city:
            city_to_stations[best_city].append(sid)

    matched = sum(1 for v in city_to_stations.values() if v)  # 数有多少城市匹配到了台站
    print(f"  匹配到 {matched} 个城市有台站")

    # ── 聚合温度：按城市 + 年份 + 月份分组，取所有台站的平均 ──
    # defaultdict(list) 的值默认是空列表，省去初始化的麻烦
    city_monthly: dict[tuple[str, int, int], list[float]] = defaultdict(list)

    for city_name, sids in city_to_stations.items():
        for sid in sids:
            if sid not in station_temps:
                continue
            for year, month, temp in station_temps[sid]:
                if year >= last_year:  # 只要新数据（≥ 现有最新年份）
                    city_monthly[(city_name, year, month)].append(temp)

    # ── 生成新行 ──
    new_rows = []
    for (city_name, year, month), temps in sorted(city_monthly.items()):
        if year > 2024:  # 2025+ 年台站数据太少，不可靠，跳过
            continue
        if year == last_year and month <= last_month:  # 已有数据不重复
            continue

        # 同一城市多个台站取平均
        avg_temp = round(sum(temps) / len(temps), 3)

        # 从已有城市信息中拿经纬度和国家
        lat, lon, country = existing_cities.get(city_name, (0.0, 0.0, ""))

        # 格式化经纬度字符串（保持和原数据一致）
        lat_str = f"{abs(lat):.2f}{'N' if lat >= 0 else 'S'}"
        lon_str = f"{abs(lon):.2f}{'E' if lon >= 0 else 'W'}"

        dt = f"{year:04d}-{month:02d}-01"  # 每月 1 号代表该月
        new_rows.append({
            "dt": dt,
            "AverageTemperature": str(avg_temp),
            "AverageTemperatureUncertainty": "",  # 台站数据没有不确定度字段，留空
            "City": city_name,
            "Country": country,
            "Latitude": lat_str,
            "Longitude": lon_str,
        })

    print(f"  新行数: {len(new_rows)}")

    # ── 写回 CSV ──
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
        for row in new_rows:
            writer.writerow(row)

    print(f"  ✓ {filename} 已更新")


# ═══════════════════════════════════════════════════════════════
# 第 4 步：更新国家 CSV
# ═══════════════════════════════════════════════════════════════

def update_country_csv(stations, station_temps):
    """
    更新 GlobalLandTemperaturesByCountry.csv。

    逻辑比城市级简单：台站已经有 country 字段（从 FIPS 映射来的），
    直接按国家聚合就行，不需要地理距离匹配。

    步骤：
      1. 读现有国家 CSV
      2. 找到最后一条数据的时间
      3. 按国家 + 年月聚合所有台站的温度
      4. 追加新数据
    """
    print("\n=== 更新 GlobalLandTemperaturesByCountry.csv ===")

    csv_path = DATASET_DIR / "GlobalLandTemperaturesByCountry.csv"

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        existing_rows = list(reader)

    last_date = existing_rows[-1]["dt"] if existing_rows else "2013-09-01"
    last_year = int(last_date[:4])
    last_month = int(last_date[5:7])
    print(f"  现有数据到: {last_year}-{last_month:02d}")

    # 提取已有国家列表（只更新已有国家，不新增）
    existing_countries = {row.get("Country", "").strip() for row in existing_rows}
    print(f"  已有 {len(existing_countries)} 个国家")

    # 按国家 + 年月聚合
    country_monthly: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    for sid, info in stations.items():
        country = info.get("country", "")
        if country not in existing_countries:  # 只更新已有国家
            continue
        if sid not in station_temps:
            continue
        for year, month, temp in station_temps[sid]:
            if year >= last_year:  # 只要新数据
                country_monthly[(country, year, month)].append(temp)

    # 生成新行
    new_rows = []
    for (country, year, month), temps in sorted(country_monthly.items()):
        if year > 2024:  # 2025+ 台站太少，不可靠
            continue
        if year == last_year and month <= last_month:  # 不重复
            continue
        avg_temp = round(sum(temps) / len(temps), 3)
        dt = f"{year:04d}-{month:02d}-01"
        new_rows.append({
            "dt": dt,
            "AverageTemperature": str(avg_temp),
            "AverageTemperatureUncertainty": "",
            "Country": country,
        })

    print(f"  新行数: {len(new_rows)}")

    # 写回 CSV
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
        for row in new_rows:
            writer.writerow(row)

    print(f"  ✓ GlobalLandTemperaturesByCountry.csv 已更新")


# ═══════════════════════════════════════════════════════════════
# main — 脚本入口
# ═══════════════════════════════════════════════════════════════

def main():
    """
    总控函数，按顺序执行全部更新步骤。

    执行顺序：
      1. 更新全球温度（距平 → 绝对温度）
      2. 下载台站清单 + 温度数据
      3. 更新国家 CSV
      4. 更新城市 CSV（两个：全量城市 + 主要城市）
      5. State CSV 跳过（需要州级边界数据，当前不支持自动更新）
    """
    print("从 NASA GISTEMP v4 更新数据")
    print("=" * 60)

    # Step 1: 全球温度
    update_global_temperatures()

    # Step 2: 下载台站数据（这一步最慢，主要耗时在这里）
    print("\n--- 加载台站数据 ---")
    stations = load_station_inventory()
    station_temps = load_station_temperatures(stations)

    # Step 3: 更新各 CSV（国家 → 全量城市 → 主要城市）
    update_country_csv(stations, station_temps)
    update_city_like_csv("GlobalLandTemperaturesByCity.csv", stations, station_temps)
    update_city_like_csv("GlobalLandTemperaturesByMajorCity.csv", stations, station_temps)

    # State CSV 需要地理边界数据（判断哪个台站属于哪个省/州）
    # 这需要额外的 shapefile 数据，暂时跳过
    print("\n⚠ GlobalLandTemperaturesByState.csv 需要州级地理边界数据，跳过自动更新")

    print("\n" + "=" * 60)
    print("数据更新完成!")


if __name__ == "__main__":
    main()
