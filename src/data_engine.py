import os
from pathlib import Path

import pandas as pd


class DataEngine:
    def __init__(self, data_path: str | Path | None = None) -> None:
        if data_path is None:
            data_path = Path(__file__).resolve().parent / "dataset"
        self.path = Path(data_path)

    def _load_csv(self, filename: str) -> pd.DataFrame:
        file_path = self.path / filename
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        df = pd.read_csv(file_path)
        df["year"] = pd.to_datetime(df["dt"], errors="coerce").dt.year
        return df

    # ── 全球年均温（含不确定度 + 极值 + 海陆总温）────────────────────

    def get_global_annual(self, min_year: int = 1850) -> pd.DataFrame:
        cols = [
            "year",
            "LandAverageTemperature",
            "LandAverageTemperatureUncertainty",
            "LandMaxTemperature",
            "LandMaxTemperatureUncertainty",
            "LandMinTemperature",
            "LandMinTemperatureUncertainty",
            "LandAndOceanAverageTemperature",
            "LandAndOceanAverageTemperatureUncertainty",
        ]
        df = self._load_csv("GlobalTemperatures.csv")
        filtered = df.loc[df["year"] >= min_year, cols]
        # 只丢弃完全没有 LandAndOcean 数据的行，允许 2016+ 仅有海陆综合温
        filtered = filtered.dropna(subset=["LandAndOceanAverageTemperature"]).copy()
        grouped = (
            filtered.groupby("year", as_index=False)
            .mean()
            .rename(
                columns={
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
            .sort_values("year")
            .reset_index(drop=True)
        )
        grouped["year"] = grouped["year"].astype("int32")
        for col in grouped.columns:
            if col != "year":
                grouped[col] = grouped[col].astype("float64").round(3)
        return grouped

    # ── 全球温度距平（相对于基准期）─────────────────────────────────

    def get_global_anomaly(
        self, baseline_start: int = 1951, baseline_end: int = 1980
    ) -> dict:
        df = self._load_csv("GlobalTemperatures.csv")
        yearly = (
            df.dropna(subset=["LandAndOceanAverageTemperature"])
            .groupby("year", as_index=False)["LandAndOceanAverageTemperature"]
            .mean()
        )
        mask = (yearly["year"] >= baseline_start) & (yearly["year"] <= baseline_end)
        baseline_avg = yearly.loc[mask, "LandAndOceanAverageTemperature"].mean()

        yearly["anomaly"] = (yearly["LandAndOceanAverageTemperature"] - baseline_avg).round(3)

        return {
            "baseline_start": baseline_start,
            "baseline_end": baseline_end,
            "baseline_avg": round(float(baseline_avg), 3),
            "years": yearly["year"].astype(int).tolist(),
            "anomalies": yearly["anomaly"].round(3).tolist(),
        }

    # ── 月度季节周期 ───────────────────────────────────────────────

    def get_global_monthly(self) -> pd.DataFrame:
        df = self._load_csv("GlobalTemperatures.csv")
        df["month"] = pd.to_datetime(df["dt"], errors="coerce").dt.month
        grouped = (
            df.dropna(subset=["LandAverageTemperature", "month"])
            .groupby("month", as_index=False)["LandAverageTemperature"]
            .mean()
            .rename(columns={"LandAverageTemperature": "temperature"})
        )
        full = pd.DataFrame({"month": range(1, 13)})
        merged = (
            full.merge(grouped, on="month", how="left")
            .sort_values("month")
            .reset_index(drop=True)
        )
        merged["month"] = merged["month"].astype("int32")
        merged["temperature"] = merged["temperature"].astype("float64").round(3)
        return merged

    # ── 季节距平热力图数据 ──────────────────────────────────────────

    def get_seasonal_anomaly(self, min_year: int = 1900) -> dict:
        df = self._load_csv("GlobalTemperatures.csv")
        df["month"] = pd.to_datetime(df["dt"], errors="coerce").dt.month
        subset = df.dropna(subset=["LandAverageTemperature", "year", "month"])
        subset = subset[subset["year"] >= min_year]

        monthly_avg = subset.groupby("month")["LandAverageTemperature"].mean()
        merged = subset.merge(monthly_avg.rename("monthly_avg"), on="month")
        merged["anomaly"] = (merged["LandAverageTemperature"] - merged["monthly_avg"]).round(3)

        pivot = merged.pivot_table(
            index="year", columns="month", values="anomaly", aggfunc="mean"
        ).sort_index()

        return {
            "min_year": min_year,
            "years": pivot.index.astype(int).tolist(),
            "months": [int(m) for m in pivot.columns],
            "data": [
                [float(v) if pd.notna(v) else None for v in row]
                for row in pivot.values
            ],
        }

    # ── 国家年均温 ─────────────────────────────────────────────────

    def get_country_annual(self, year: int) -> pd.DataFrame:
        df = self._load_csv("GlobalLandTemperaturesByCountry.csv")
        filtered = df.loc[
            (df["year"] == year) & df["AverageTemperature"].notna(),
            ["Country", "AverageTemperature"],
        ]
        grouped = (
            filtered.groupby("Country", as_index=False)["AverageTemperature"]
            .mean()
            .rename(columns={"AverageTemperature": "temperature"})
            .sort_values("temperature", ascending=False)
            .reset_index(drop=True)
        )
        grouped["temperature"] = grouped["temperature"].astype("float64").round(3)
        return grouped

    # ── 纬度带温度趋势 ─────────────────────────────────────────────

    @staticmethod
    def _parse_latitude(lat: object) -> float:
        s = str(lat).strip().upper()
        if s.endswith("S"):
            return -float(s[:-1])
        if s.endswith("N"):
            return float(s[:-1])
        return float(s)

    @staticmethod
    def _latband(lat_raw: object) -> str:
        lat_abs = abs(DataEngine._parse_latitude(lat_raw))
        if lat_abs <= 23.5:
            return "tropical"
        if lat_abs <= 66.5:
            return "temperate"
        return "polar"

    def get_city_latband(self, min_year: int = 1850) -> pd.DataFrame:
        df = self._load_csv("GlobalLandTemperaturesByCity.csv")
        filtered = df.loc[
            (df["year"] >= min_year)
            & df["AverageTemperature"].notna()
            & df["Latitude"].notna(),
            ["year", "Latitude", "AverageTemperature"],
        ].copy()
        filtered["band"] = filtered["Latitude"].apply(self._latband)
        grouped = (
            filtered.groupby(["year", "band"], as_index=False)["AverageTemperature"]
            .mean()
            .rename(columns={"AverageTemperature": "temperature"})
            .sort_values(["band", "year"])
            .reset_index(drop=True)
        )
        grouped["temperature"] = grouped["temperature"].astype("float64").round(3)
        grouped["year"] = grouped["year"].astype("int32")
        return grouped

    # ── 城市年均温排名 ────────────────────────────────────────────

    def get_city_temp_by_year(self, year: int, limit: int = 20) -> pd.DataFrame:
        df = self._load_csv("GlobalLandTemperaturesByCity.csv")
        filtered = df.loc[
            (df["year"] == year) & df["AverageTemperature"].notna(),
            ["City", "AverageTemperature"],
        ]
        if filtered.empty:
            return pd.DataFrame({"City": pd.Series(dtype="str"), "temperature": pd.Series(dtype="float64")})

        grouped = (
            filtered.groupby("City", as_index=False)["AverageTemperature"]
            .mean()
            .rename(columns={"AverageTemperature": "temperature"})
            .sort_values("temperature", ascending=False)
            .head(limit)
            .reset_index(drop=True)
        )
        grouped["temperature"] = grouped["temperature"].astype("float64")
        return grouped
