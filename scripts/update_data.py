"""
从 NASA GISTEMP v4 下载 2013 年至今的数据，更新到 dataset CSV 中。

数据来源: https://data.giss.nasa.gov/gistemp/
- GLB.Ts+dSST.csv: 全球月度 L-OTI 距平 -> GlobalTemperatures.csv
- v4.mean_GISS_homogenized.txt.gz: GHCN v4 homogenized 台站数据 -> City/Country CSVs
- v4.temperature.inv.txt: 台站清单
"""

import csv
import gzip
import io
import math
from collections import defaultdict
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_DIR = SCRIPT_DIR.parent / "src" / "dataset"
GISS_BASE = "https://data.giss.nasa.gov/gistemp"

# GHCN v4 台站 ID 前缀 (FIPS) -> 国家名称 映射
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

# 将 FIPS 国家名映射到现有数据中的国家名 (有些名字不同)
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


def download(url: str) -> str:
    print(f"  下载: {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.text


def download_binary(url: str) -> bytes:
    print(f"  下载: {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def extract_country_from_sid(sid: str) -> str:
    """从 GHCN v4 台站 ID 提取国家名称"""
    prefix = sid[0:2].upper()
    if prefix in FIPS_TO_COUNTRY:
        name = FIPS_TO_COUNTRY[prefix]
        return COUNTRY_NAME_ALIAS.get(name, name)
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 更新 GlobalTemperatures.csv
# ═══════════════════════════════════════════════════════════════════════════════

def update_global_temperatures():
    print("\n=== 更新 GlobalTemperatures.csv ===")

    csv_path = DATASET_DIR / "GlobalTemperatures.csv"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        existing_rows = list(reader)

    print(f"  现有行数: {len(existing_rows)}")

    # 计算 1951-1980 基线 (GISTEMP 距平基准期)
    baseline_temps = []
    for row in existing_rows:
        year_str = row["dt"][:4]
        if not year_str.isdigit():
            continue
        year = int(year_str)
        if 1951 <= year <= 1980:
            val = row.get("LandAndOceanAverageTemperature", "").strip()
            if val:
                baseline_temps.append(float(val))

    baseline_mean = sum(baseline_temps) / len(baseline_temps) if baseline_temps else 14.0
    print(f"  1951-1980 LandAndOcean 基线均值: {baseline_mean:.4f}°C  (共 {len(baseline_temps)} 月)")

    # 下载并解析 GISTEMP GLB.Ts+dSST
    glb_csv = download(f"{GISS_BASE}/tabledata_v4/GLB.Ts+dSST.csv")
    lines = glb_csv.strip().split("\n")

    data_start = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("Year"):
            data_start = i
            break

    month_cols = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    anomalies_by_month: dict[str, float] = {}
    for line in lines[data_start + 1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 13:
            continue
        try:
            year = int(parts[0])
        except ValueError:
            continue
        for m_idx, _ in enumerate(month_cols):
            raw = parts[m_idx + 1]
            if raw in ("***", ""):
                continue
            try:
                val = float(raw)
            except ValueError:
                continue
            anomalies_by_month[f"{year:04d}-{m_idx + 1:02d}"] = val

    # 新数据从 2016 年开始追加 (现有数据到 2015-12)
    new_rows = []
    for year in range(2016, 2027):
        for month in range(1, 13):
            key = f"{year:04d}-{month:02d}"
            anomaly = anomalies_by_month.get(key)
            if anomaly is None:
                continue
            land_ocean_temp = round(baseline_mean + anomaly, 3)
            new_rows.append({
                "dt": f"{year:04d}-{month:02d}-01",
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

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
        for row in new_rows:
            writer.writerow(row)

    print(f"  ✓ GlobalTemperatures.csv 已更新")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 台站数据加载
# ═══════════════════════════════════════════════════════════════════════════════

def load_station_inventory() -> dict[str, dict]:
    print("\n  加载台站清单...")
    inv_text = download(f"{GISS_BASE}/station_data_v4_globe/v4.temperature.inv.txt")
    stations: dict[str, dict] = {}
    for line in inv_text.strip().split("\n"):
        if len(line) < 40:
            continue
        sid = line[0:11].strip()
        lat_str = line[11:20].strip()
        lon_str = line[20:30].strip()
        name = line[37:60].strip()
        try:
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            continue
        country = extract_country_from_sid(sid)
        stations[sid] = {"lat": lat, "lon": lon, "name": name, "country": country}
    print(f"    {len(stations)} 个台站")
    return stations


def load_station_temperatures(stations: dict) -> dict[str, list[tuple[int, int, float]]]:
    print("  下载台站温度数据 (35MB)...")
    raw = download_binary(f"{GISS_BASE}/station_data_v4_globe/v4.mean_GISS_homogenized.txt.gz")
    print("  解压并解析...")

    station_temps: dict[str, list[tuple[int, int, float]]] = {}

    with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as f:
        current_sid = None
        for line in f:
            line = line.rstrip()
            if not line:
                continue
            # 台站头行
            if len(line) > 40 and line[0:3].isalpha() and any(c.isdigit() for c in line):
                pass
            if len(line) > 40 and line[0:3].isalpha():
                # 尝试提取台站ID
                first_token = line[0:11].strip()
                if first_token in stations:
                    current_sid = first_token
                    if current_sid not in station_temps:
                        station_temps[current_sid] = []
                else:
                    current_sid = None
                continue

            # 月度数据行: 按空白分词解析 (比固定宽度更稳健)
            if current_sid and len(line) >= 48 and line[0:4].strip().isdigit():
                tokens = line.split()
                if len(tokens) < 13:
                    continue
                try:
                    year = int(tokens[0])
                except ValueError:
                    continue
                for m in range(12):
                    val_str = tokens[m + 1]
                    if val_str == "-9999" or val_str == "9999":
                        continue
                    try:
                        val = int(val_str)
                    except ValueError:
                        continue
                    if abs(val) > 8000:
                        continue
                    temp_c = val / 100.0  # GISS homogenized 单位: 0.01°C
                    if abs(temp_c) > 60:
                        continue
                    station_temps[current_sid].append((year, m + 1, temp_c))

    print(f"    {len(station_temps)} 个台站有温度数据")
    return station_temps


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 更新城市级 CSV
# ═══════════════════════════════════════════════════════════════════════════════

def parse_lat_lon(raw_lat: str, raw_lon: str) -> tuple[float, float]:
    """解析经纬度字符串 (如 57.05N, 10.33E)"""
    lat_str = raw_lat.strip().upper()
    lon_str = raw_lon.strip().upper()
    try:
        lat = float(lat_str[:-1]) if lat_str[-1] in "NS" else float(lat_str)
        if lat_str[-1] == "S":
            lat = -lat
    except (ValueError, IndexError):
        lat = 0.0
    try:
        lon = float(lon_str[:-1]) if lon_str[-1] in "EW" else float(lon_str)
        if lon_str[-1] == "W":
            lon = -lon
    except (ValueError, IndexError):
        lon = 0.0
    return lat, lon


def update_city_like_csv(filename: str, stations, station_temps):
    """更新城市级 CSV (City, MajorCity 等)"""
    csv_path = DATASET_DIR / filename
    if not csv_path.exists():
        print(f"  {filename} 不存在，跳过")
        return

    print(f"\n=== 更新 {filename} ===")
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        existing_rows = list(reader)

    last_date = existing_rows[-1]["dt"] if existing_rows else "2013-09-01"
    last_year = int(last_date[:4])
    last_month = int(last_date[5:7])
    print(f"  现有数据到: {last_year}-{last_month:02d}")

    # 收集城市坐标
    existing_cities: dict[str, tuple[float, float, str]] = {}
    for row in existing_rows:
        city = row.get("City", "").strip()
        if city and city not in existing_cities:
            lat, lon = parse_lat_lon(row.get("Latitude", "0"), row.get("Longitude", "0"))
            country = row.get("Country", "").strip()
            existing_cities[city] = (lat, lon, country)

    print(f"  已有 {len(existing_cities)} 个城市")

    # 台站→城市匹配 (200km 以内)
    print("  匹配台站到城市...")
    city_to_stations: dict[str, list[str]] = {c: [] for c in existing_cities}
    for sid, info in stations.items():
        slat, slon = info["lat"], info["lon"]
        best_city = None
        best_dist = float("inf")
        for city_name, (clat, clon, _) in existing_cities.items():
            dlat = slat - clat
            dlon = slon - clon
            dist = math.sqrt(dlat ** 2 + dlon ** 2) * 111.0
            if dist < best_dist and dist < 200:
                best_dist = dist
                best_city = city_name
        if best_city:
            city_to_stations[best_city].append(sid)

    matched = sum(1 for v in city_to_stations.values() if v)
    print(f"  匹配到 {matched} 个城市有台站")

    # 聚合温度
    city_monthly: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    for city_name, sids in city_to_stations.items():
        for sid in sids:
            if sid not in station_temps:
                continue
            for year, month, temp in station_temps[sid]:
                if year >= last_year:
                    city_monthly[(city_name, year, month)].append(temp)

    # 生成新行
    new_rows = []
    for (city_name, year, month), temps in sorted(city_monthly.items()):
        if year > 2024:  # 2025+ 台站报告太少，数据不可靠
            continue
        if year == last_year and month <= last_month:
            continue
        avg_temp = round(sum(temps) / len(temps), 3)
        lat, lon, country = existing_cities.get(city_name, (0.0, 0.0, ""))
        lat_str = f"{abs(lat):.2f}{'N' if lat >= 0 else 'S'}"
        lon_str = f"{abs(lon):.2f}{'E' if lon >= 0 else 'W'}"
        dt = f"{year:04d}-{month:02d}-01"
        new_rows.append({
            "dt": dt,
            "AverageTemperature": str(avg_temp),
            "AverageTemperatureUncertainty": "",
            "City": city_name,
            "Country": country,
            "Latitude": lat_str,
            "Longitude": lon_str,
        })

    print(f"  新行数: {len(new_rows)}")

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
        for row in new_rows:
            writer.writerow(row)

    print(f"  ✓ {filename} 已更新")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 更新国家 CSV
# ═══════════════════════════════════════════════════════════════════════════════

def update_country_csv(stations, station_temps):
    """更新 GlobalLandTemperaturesByCountry.csv — 按台站国家聚合"""
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

    existing_countries = {row.get("Country", "").strip() for row in existing_rows}
    print(f"  已有 {len(existing_countries)} 个国家")

    # 按国家和年月聚合温度
    country_monthly: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    for sid, info in stations.items():
        country = info.get("country", "")
        if country not in existing_countries:
            continue
        if sid not in station_temps:
            continue
        for year, month, temp in station_temps[sid]:
            if year >= last_year:
                country_monthly[(country, year, month)].append(temp)

    new_rows = []
    for (country, year, month), temps in sorted(country_monthly.items()):
        if year > 2024:  # 2025+ 台站报告太少，数据不可靠
            continue
        if year == last_year and month <= last_month:
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

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow(row)
        for row in new_rows:
            writer.writerow(row)

    print(f"  ✓ GlobalLandTemperaturesByCountry.csv 已更新")


# ═══════════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("从 NASA GISTEMP v4 更新数据")
    print("=" * 60)

    # Step 1: 全球温度
    update_global_temperatures()

    # Step 2: 台站数据
    print("\n--- 加载台站数据 ---")
    stations = load_station_inventory()
    station_temps = load_station_temperatures(stations)

    # Step 3: 更新各 CSV
    update_country_csv(stations, station_temps)
    update_city_like_csv("GlobalLandTemperaturesByCity.csv", stations, station_temps)
    update_city_like_csv("GlobalLandTemperaturesByMajorCity.csv", stations, station_temps)

    # State CSV 需要地理边界数据，暂不处理
    print("\n⚠ GlobalLandTemperaturesByState.csv 需要州级地理边界数据，跳过自动更新")

    print("\n" + "=" * 60)
    print("数据更新完成!")


if __name__ == "__main__":
    main()
