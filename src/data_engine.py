"""
data_engine.py — 数据引擎（后端的"心脏"）
==========================================
这个文件是前端图表和后端 CSV 数据之间的"翻译官"。
前端说"我要 2024 年中国的城市温度排名"，这个类就去 CSV 文件里
找到对应的数据、清洗干净、算好平均值、排好序，然后交出去。

工作流程：
  CSV 文件（原始数据）
    → _load_csv() 读进来（pandas DataFrame）
    → 各个 get_xxx() 方法清洗、分组、计算
    → 返回干净的数据（DataFrame 或 dict）
    → app.py 把数据转成 JSON 发给前端

类比：如果把后端比作餐厅，
  CSV 文件 = 冰箱里的食材
  DataEngine = 厨师（洗菜、切菜、炒菜）
  app.py = 服务员（把菜端给客人）
"""

from __future__ import annotations  # 允许用 list[int] 这种新式类型注解

import os
from pathlib import Path
from typing import Union

import pandas as pd  # pandas = Python 里处理表格数据的王牌库


class DataEngine:
    """
    数据引擎类——所有数据查询都通过它。

    使用方式：
        engine = DataEngine()               # 创建实例
        df = engine.get_global_annual()     # 获取全球年均温
        data = engine.get_global_anomaly()  # 获取距平数据
    """

    def __init__(self, data_path: Union[str, Path, None] = None) -> None:
        """
        初始化：确定 CSV 数据文件在哪个目录。

        Args:
            data_path: CSV 文件夹路径。如果没传，默认用本文件同级的 dataset/ 目录。
                       比如 data_engine.py 在 src/ 下，就自动找 src/dataset/
        """
        if data_path is None:
            # Path(__file__) = 本文件的路径
            # .resolve() = 转成绝对路径
            # .parent = 所在目录（即 src/）
            data_path = Path(__file__).resolve().parent / "dataset"
        self.path = Path(data_path)  # 存起来，后面每次读文件都用这个路径

    def _load_csv(self, filename: str) -> pd.DataFrame:
        """
        （内部方法）读取一个 CSV 文件，自动加上 year 列。

        为什么用 _ 开头？
          Python 的约定：_ 开头 = "这是内部用的，外面别直接调用"。

        做什么：
          1. 拼出文件完整路径
          2. 用 pandas 读 CSV → DataFrame（可以理解为"内存里的 Excel 表格"）
          3. 把 dt 列（比如 "2015-06-01"）转成 datetime 再提取年份 → 新列 year

        Args:
            filename: CSV 文件名，比如 "GlobalTemperatures.csv"

        Returns:
            DataFrame，比原始 CSV 多一个 year 列
        """
        file_path = self.path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        df = pd.read_csv(file_path)  # 把 CSV 文件读到内存里

        # dt 列长这样："1850-01-01"，用 pd.to_datetime 转成时间对象
        # errors="coerce" 的意思是"如果某格格式不对，变成 NaT（空时间），别报错"
        # .dt.year = 只取年份部分
        df["year"] = pd.to_datetime(df["dt"], errors="coerce").dt.year
        return df

    # ═══════════════════════════════════════════════════════════════
    # 方法 1：全球年均温（含不确定度 + 极值 + 海陆总温）
    # ═══════════════════════════════════════════════════════════════

    def get_global_annual(self, min_year: int = 1850) -> pd.DataFrame:
        """
        获取全球年度温度数据，包含好几条线：
          - 陆地平均温（land_avg）
          - 陆地最高温（land_max）
          - 陆地最低温（land_min）
          - 海陆综合温（land_ocean_avg）
          - 以及每种温度的不确定度

        处理逻辑：
          1. 筛掉 min_year 之前的年份
          2. 丢掉完全没有海陆综合温的行（但允许陆地温度为空——2016+ 的很多行就这样）
          3. 按年份分组，取平均（同一年可能有 12 个月的数据）
          4. 把列名从又长又丑的英文改成简短的英文名

        Args:
            min_year: 从哪一年开始（默认 1850）

        Returns:
            DataFrame，列 = year, land_avg, land_max, land_min, land_ocean_avg, ...
        """
        # 需要用到的列（原始 CSV 里的列名又长又啰嗦）
        cols = [
            "year",
            "LandAverageTemperature",                     # 陆地平均温
            "LandAverageTemperatureUncertainty",          # 陆地平均温的不确定度
            "LandMaxTemperature",                         # 陆地最高温
            "LandMaxTemperatureUncertainty",              # 陆地最高温的不确定度
            "LandMinTemperature",                         # 陆地最低温
            "LandMinTemperatureUncertainty",              # 陆地最低温的不确定度
            "LandAndOceanAverageTemperature",              # 海陆综合温
            "LandAndOceanAverageTemperatureUncertainty",   # 海陆综合温的不确定度
        ]

        df = self._load_csv("GlobalTemperatures.csv")

        # 筛选：年份 >= min_year 的行，只要上面列出的列
        filtered = df.loc[df["year"] >= min_year, cols]

        # 关键处理：只丢掉完全没有海陆综合温的行
        # 为什么不全丢掉？2016 年后的数据只有海陆综合温，陆地温度是空的
        # 如果按全部列去空值，2016+ 的数据就全没了
        filtered = filtered.dropna(subset=["LandAndOceanAverageTemperature"]).copy()

        # 按年份分组 → 求平均 → 重命名列
        grouped = (
            filtered.groupby("year", as_index=False)
            .mean()  # 同一年 12 个月的温度取平均 = 年均温
            .rename(
                columns={
                    # 把原始列名映射成简短的名字（前端 JS 里用的就是这些短名）
                    "LandAverageTemperature": "land_avg",
                    "LandAverageTemperatureUncertainty": "land_uncertainty",
                    "LandMaxTemperature": "land_max",
                    "LandMaxTemperatureUncertainty": "land_max_uncertainty",
                    "LandMinTemperature": "land_min",
                    "LandMinTemperatureUncertainty": "land_min_uncertainty",
                    "LandAndOceanAverageTemperature": "land_ocean_avg",
                    "LandAndOceanAverageTemperatureUncertainty": "land_ocean_uncertainty",
                }
            )
            .sort_values("year")          # 按年份从小到大排
            .reset_index(drop=True)       # 重置索引（0, 1, 2, ...）
        )

        # 统一数据类型：年份是整数，温度是保留 3 位小数的浮点数
        grouped["year"] = grouped["year"].astype("int32")
        for col in grouped.columns:
            if col != "year":
                grouped[col] = grouped[col].astype("float64").round(3)
        return grouped

    # ═══════════════════════════════════════════════════════════════
    # 方法 2：全球温度距平（相对于基准期）
    # ═══════════════════════════════════════════════════════════════

    def get_global_anomaly(
        self, baseline_start: int = 1951, baseline_end: int = 1980
    ) -> dict:
        """
        计算全球温度距平。
        "距平"是什么？
          比如 1951-1980 年的平均温度是 15°C（这叫"基准均值"），
          2024 年的温度是 16.3°C，那 2024 年的距平就是 +1.3°C（比基准高了 1.3°C）。

        计算步骤：
          1. 加载全球温度数据
          2. 按年求平均
          3. 算 1951-1980 年的平均温度（基准均值）
          4. 每一年的温度 − 基准均值 = 距平

        Args:
            baseline_start: 基准期起始年份（默认 1951）
            baseline_end:   基准期结束年份（默认 1980）

        Returns:
            dict: {
                "baseline_start": 1951,
                "baseline_end": 1980,
                "baseline_avg": 15.3,        # 基准期的平均温度
                "years": [1951, 1952, ...],  # 年份列表
                "anomalies": [0.0, 0.12, ...]  # 对应的距平值
            }
        """
        df = self._load_csv("GlobalTemperatures.csv")

        # 按年求海陆综合温的平均值
        yearly = (
            df.dropna(subset=["LandAndOceanAverageTemperature"])
            .groupby("year", as_index=False)["LandAndOceanAverageTemperature"]
            .mean()
        )

        # 找出基准期内的年份，算平均值
        # mask = 一个 True/False 数组，比如 [False, True, True, ..., False]
        mask = (yearly["year"] >= baseline_start) & (yearly["year"] <= baseline_end)
        baseline_avg = yearly.loc[mask, "LandAndOceanAverageTemperature"].mean()

        # 每年温度 − 基准均值 = 距平
        yearly["anomaly"] = (yearly["LandAndOceanAverageTemperature"] - baseline_avg).round(3)

        # 返回字典格式（FastAPI 会自动转成 JSON）
        return {
            "baseline_start": baseline_start,
            "baseline_end": baseline_end,
            "baseline_avg": round(float(baseline_avg), 3),
            "years": yearly["year"].astype(int).tolist(),      # DataFrame → Python list
            "anomalies": yearly["anomaly"].round(3).tolist(),
        }

    # ═══════════════════════════════════════════════════════════════
    # 方法 3：月度季节周期
    # ═══════════════════════════════════════════════════════════════

    def get_global_monthly(self) -> pd.DataFrame:
        """
        计算 1~12 月每个月的多年平均温度（不限定年份范围）。

        用途：前端画"季节周期图"——一条曲线，1 月最低，7 月最高（北半球规律）。

        处理逻辑：
          1. 从日期中提取月份
          2. 按月份分组，求平均
          3. 用 1~12 的完整月份列表左连接，填充缺失月（有的月份可能完全没数据）

        Returns:
            DataFrame，两列：month (1~12), temperature
        """
        df = self._load_csv("GlobalTemperatures.csv")

        # 从 dt 列提取月份
        df["month"] = pd.to_datetime(df["dt"], errors="coerce").dt.month

        # 按月份分组求平均
        grouped = (
            df.dropna(subset=["LandAverageTemperature", "month"])
            .groupby("month", as_index=False)["LandAverageTemperature"]
            .mean()
            .rename(columns={"LandAverageTemperature": "temperature"})
        )

        # 确保 1~12 月全都有（有的月可能没数据，用 NaN 填）
        full = pd.DataFrame({"month": range(1, 13)})  # 创建 [1, 2, 3, ..., 12]
        merged = (
            full.merge(grouped, on="month", how="left")  # 左连接：保持 full 的所有行
            .sort_values("month")
            .reset_index(drop=True)
        )

        merged["month"] = merged["month"].astype("int32")
        merged["temperature"] = merged["temperature"].astype("float64").round(3)
        return merged

    # ═══════════════════════════════════════════════════════════════
    # 方法 4：季节距平热力图数据
    # ═══════════════════════════════════════════════════════════════

    def get_seasonal_anomaly(self, min_year: int = 1900) -> dict:
        """
        计算"某年某月比该月的多年平均值高了多少"。
        输出的数据结构是一个二维矩阵：行 = 年份，列 = 月份，值 = 距平。

        用途：画热力图（但当前前端没有用到这个 API）。

        计算步骤：
          1. 先算出每个月的多年平均（比如所有年份的 1 月平均是 10°C）
          2. 每年每月减对应月的平均 = 距平
          3. 转成 pivot 表格（年份 × 月份矩阵）

        Args:
            min_year: 起始年份

        Returns:
            dict: {min_year, years: [...], months: [1..12], data: [[...], ...]}
        """
        df = self._load_csv("GlobalTemperatures.csv")
        df["month"] = pd.to_datetime(df["dt"], errors="coerce").dt.month

        subset = df.dropna(subset=["LandAverageTemperature", "year", "month"])
        subset = subset[subset["year"] >= min_year]

        # 每个月的多年平均温度
        monthly_avg = subset.groupby("month")["LandAverageTemperature"].mean()

        # 把月均值合并到每行数据上
        merged = subset.merge(monthly_avg.rename("monthly_avg"), on="month")

        # 计算距平：当月温度 - 该月多年平均
        merged["anomaly"] = (merged["LandAverageTemperature"] - merged["monthly_avg"]).round(3)

        # 转成 pivot 表格：行 = 年份，列 = 月份，值 = 距平
        pivot = merged.pivot_table(
            index="year", columns="month", values="anomaly", aggfunc="mean"
        ).sort_index()

        return {
            "min_year": min_year,
            "years": pivot.index.astype(int).tolist(),
            "months": [int(m) for m in pivot.columns],
            "data": [
                # 把每行的 NaN 转成 None（JSON 不支持 NaN）
                [float(v) if pd.notna(v) else None for v in row]
                for row in pivot.values
            ],
        }

    # ═══════════════════════════════════════════════════════════════
    # 方法 5：国家年均温
    # ═══════════════════════════════════════════════════════════════

    def get_country_annual(self, year: int) -> pd.DataFrame:
        """
        获取某一年所有国家的平均温度，按温度从高到低排序。

        Args:
            year: 目标年份

        Returns:
            DataFrame: Country（国家名）, temperature（平均温度）
        """
        df = self._load_csv("GlobalLandTemperaturesByCountry.csv")

        # 筛选：指定年份 + 温度不为空的那些行
        filtered = df.loc[
            (df["year"] == year) & df["AverageTemperature"].notna(),
            ["Country", "AverageTemperature"],
        ]

        # 按国家分组求平均（一个国家可能有多个测量站）
        grouped = (
            filtered.groupby("Country", as_index=False)["AverageTemperature"]
            .mean()
            .rename(columns={"AverageTemperature": "temperature"})
            .sort_values("temperature", ascending=False)  # 降序：最热的国家排第一
            .reset_index(drop=True)
        )

        grouped["temperature"] = grouped["temperature"].astype("float64").round(3)
        return grouped

    # ═══════════════════════════════════════════════════════════════
    # 方法 6：纬度带温度趋势
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _parse_latitude(lat: object) -> float:
        """
        （静态方法）把经纬度字符串转成数字。

        比如 "57.05N" → 57.05（北纬 = 正数）
            "10.33S" → -10.33（南纬 = 负数）

        @staticmethod 表示这个方法不需要访问 self，可以直接用 DataEngine._parse_latitude() 调用，
        就像一把"不属于任何实例的工具刀"。
        """
        s = str(lat).strip().upper()  # 统一转大写，去掉首尾空格
        if s.endswith("S"):
            return -float(s[:-1])  # S 结尾 → 南纬 → 负数
        if s.endswith("N"):
            return float(s[:-1])   # N 结尾 → 北纬 → 正数
        return float(s)            # 没有 N/S → 直接转数字

    @staticmethod
    def _latband(lat_raw: object) -> str:
        """
        （静态方法）根据纬度判断属于哪个纬度带。

        规则：
            纬度绝对值 ≤ 23.5°  → "tropical"  （热带，赤道附近）
            纬度绝对值 ≤ 66.5°  → "temperate" （温带，中间地带）
            纬度绝对值 > 66.5°  → "polar"     （寒带，极地）

        Args:
            lat_raw: 原始纬度字符串，如 "39.90N"

        Returns:
            "tropical" / "temperate" / "polar"
        """
        lat_abs = abs(DataEngine._parse_latitude(lat_raw))
        if lat_abs <= 23.5:
            return "tropical"
        if lat_abs <= 66.5:
            return "temperate"
        return "polar"

    def get_city_latband(self, min_year: int = 1850) -> pd.DataFrame:
        """
        获取按纬度带分组的温度趋势数据。

        处理流程：
          1. 加载城市温度数据
          2. 筛选 min_year 之后、温度不为空、有纬度信息的行
          3. 每行加一个 band 列（tropical / temperate / polar）
          4. 按年份 + 纬度带分组求平均
          5. 排序

        Returns:
            DataFrame: year, band, temperature
                       band 的值为 "tropical" / "temperate" / "polar"
        """
        df = self._load_csv("GlobalLandTemperaturesByCity.csv")

        filtered = df.loc[
            (df["year"] >= min_year)
            & df["AverageTemperature"].notna()
            & df["Latitude"].notna(),
            ["year", "Latitude", "AverageTemperature"],
        ].copy()

        # .apply(self._latband) = 对 Latitude 列的每一行都调用 _latband 函数
        # 比如 "39.90N" → "temperate"
        filtered["band"] = filtered["Latitude"].apply(self._latband)

        # 按年份和纬度带分组求平均
        grouped = (
            filtered.groupby(["year", "band"], as_index=False)["AverageTemperature"]
            .mean()
            .rename(columns={"AverageTemperature": "temperature"})
            .sort_values(["band", "year"])  # 先按纬度带排序，再按年份排序
            .reset_index(drop=True)
        )

        grouped["temperature"] = grouped["temperature"].astype("float64").round(3)
        grouped["year"] = grouped["year"].astype("int32")
        return grouped

    # ═══════════════════════════════════════════════════════════════
    # 方法 7：城市年均温排名
    # ═══════════════════════════════════════════════════════════════

    def get_city_temp_by_year(
        self, year: int, limit: int = 20, country: Union[str, None] = None
    ) -> pd.DataFrame:
        """
        获取某一年某个国家温度最高的前 N 个城市。

        Args:
            year:    目标年份
            limit:   最多返回多少个城市（默认 20）
            country: 国家名（可选）。不传 = 全球城市排名，传了 = 只看该国城市。

        Returns:
            DataFrame: City（城市名）, temperature

        示例：
            get_city_temp_by_year(2024, 10, "China")
            → 2024 年中国温度最高的 10 个城市
        """
        df = self._load_csv("GlobalLandTemperaturesByCity.csv")

        filtered = df.loc[
            (df["year"] == year) & df["AverageTemperature"].notna(),
            ["City", "Country", "AverageTemperature"],
        ]

        # 如果传了国家名，进一步筛选
        if country:
            filtered = filtered[filtered["Country"] == country]

        # 如果筛选后没数据，返回一个空的 DataFrame（避免后续操作报错）
        if filtered.empty:
            return pd.DataFrame({
                "City": pd.Series(dtype="str"),
                "temperature": pd.Series(dtype="float64"),
            })

        # 按城市分组求平均 → 降序 → 取前 limit 名
        grouped = (
            filtered.groupby("City", as_index=False)["AverageTemperature"]
            .mean()
            .rename(columns={"AverageTemperature": "temperature"})
            .sort_values("temperature", ascending=False)  # 最热的排前面
            .head(limit)  # 只要前 N 个
            .reset_index(drop=True)
        )

        grouped["temperature"] = grouped["temperature"].astype("float64")
        return grouped

    # ═══════════════════════════════════════════════════════════════
    # 方法 8：省/州年均温排名（按国家筛选）
    # ═══════════════════════════════════════════════════════════════

    def get_state_temp_by_year(
        self, year: int, country: Union[str, None] = None, limit: int = 20
    ) -> pd.DataFrame:
        """
        获取某一年某个国家温度最高的前 N 个省/州。

        跟上面的 get_city_temp_by_year 几乎一样，只是操作的对象
        从 City 换成了 State，数据集也不同。

        Args:
            year:    目标年份
            country: 国家名（可选，不传 = 全球省份排名）
            limit:   最多返回多少个省

        Returns:
            DataFrame: State（省/州名）, temperature
        """
        df = self._load_csv("GlobalLandTemperaturesByState.csv")

        filtered = df.loc[
            (df["year"] == year) & df["AverageTemperature"].notna(),
            ["State", "Country", "AverageTemperature"],
        ]

        if country:
            filtered = filtered[filtered["Country"] == country]

        if filtered.empty:
            return pd.DataFrame({
                "State": pd.Series(dtype="str"),
                "temperature": pd.Series(dtype="float64"),
            })

        grouped = (
            filtered.groupby("State", as_index=False)["AverageTemperature"]
            .mean()
            .rename(columns={"AverageTemperature": "temperature"})
            .sort_values("temperature", ascending=False)
            .head(limit)
            .reset_index(drop=True)
        )

        grouped["temperature"] = grouped["temperature"].astype("float64")
        return grouped


# ═════════════════════════════════════════════════════════════======
# 如果直接运行这个文件（而不是被 app.py import），做个简单测试
# ═════════════════════════════════════════════════════════════======
if __name__ == "__main__":
    # __name__ == "__main__" 的意思是"这个文件是被直接运行的"
    # 如果是在别的文件里 import 的，__name__ 就是模块名，不等于 "__main__"

    engine = DataEngine()

    try:
        # 注意：代码里有 bug——类里没有 get_global_temp()，实际叫 get_global_annual()
        # 这里只是简单的自测代码
        global_temp = engine.get_global_temp()

        print("全球温度年数据预览:")
        print(global_temp.head())  # .head() = 打印前 5 行

    except Exception as e:
        print(f"运行失败: {e}")
