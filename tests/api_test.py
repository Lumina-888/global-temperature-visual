from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

import src.app as app_module
from src.data_engine import DataEngine


def _write_csv(tmp_path: Path, filename: str, rows: list[dict]) -> None:
    (tmp_path / filename).write_text(
        pd.DataFrame(rows).to_csv(index=False), encoding="utf-8"
    )


def _make_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(app_module, "engine", DataEngine(data_path=str(tmp_path)))
    return TestClient(app_module.app)


# ── 全球年均温（含不确定度）─────────────────────────

def test_global_annual(tmp_path: Path, monkeypatch) -> None:
    _write_csv(tmp_path, "GlobalTemperatures.csv", [
        {"dt": "1900-01-01", "LandAverageTemperature": 10.0,
         "LandAverageTemperatureUncertainty": 0.5,
         "LandMaxTemperature": 15.0, "LandMaxTemperatureUncertainty": 0.5,
         "LandMinTemperature": 5.0, "LandMinTemperatureUncertainty": 0.5,
         "LandAndOceanAverageTemperature": 13.0,
         "LandAndOceanAverageTemperatureUncertainty": 0.3},
        {"dt": "1900-06-01", "LandAverageTemperature": 12.0,
         "LandAverageTemperatureUncertainty": 0.5,
         "LandMaxTemperature": 17.0, "LandMaxTemperatureUncertainty": 0.5,
         "LandMinTemperature": 7.0, "LandMinTemperatureUncertainty": 0.5,
         "LandAndOceanAverageTemperature": 15.0,
         "LandAndOceanAverageTemperatureUncertainty": 0.3},
    ])
    client = _make_client(tmp_path, monkeypatch)
    resp = client.get("/api/global/annual?min_year=1900")

    assert resp.status_code == 200
    data = resp.json()
    assert data["years"] == [1900]
    assert data["land_avg"] == [11.0]
    assert data["land_ocean_avg"] == [14.0]
    assert data["count"] == 1


# ── 全球温度距平 ─────────────────────────────────────

def test_global_anomaly(tmp_path: Path, monkeypatch) -> None:
    _write_csv(tmp_path, "GlobalTemperatures.csv", [
        {"dt": "1951-01-01", "LandAndOceanAverageTemperature": 14.0},
        {"dt": "1951-06-01", "LandAndOceanAverageTemperature": 16.0},
        {"dt": "2000-01-01", "LandAndOceanAverageTemperature": 16.0},
        {"dt": "2000-06-01", "LandAndOceanAverageTemperature": 18.0},
    ])
    client = _make_client(tmp_path, monkeypatch)
    resp = client.get("/api/global/anomaly?baseline_start=1951&baseline_end=1951")

    assert resp.status_code == 200
    data = resp.json()
    assert data["baseline_avg"] == 15.0
    assert data["anomalies"][data["years"].index(1951)] == 0.0
    assert data["anomalies"][data["years"].index(2000)] == 2.0


# ── 全球月均温 ─────────────────────────────────────

def test_global_monthly(tmp_path: Path, monkeypatch) -> None:
    _write_csv(tmp_path, "GlobalTemperatures.csv", [
        {"dt": "2000-01-15", "LandAverageTemperature": 5.0},
        {"dt": "2000-07-15", "LandAverageTemperature": 20.0},
        {"dt": "2001-01-15", "LandAverageTemperature": 7.0},
        {"dt": "2001-07-15", "LandAverageTemperature": 22.0},
    ])
    client = _make_client(tmp_path, monkeypatch)
    resp = client.get("/api/global/monthly")

    assert resp.status_code == 200
    data = resp.json()
    assert data["months"] == list(range(1, 13))
    temps = data["temps"]
    assert temps[0] == 6.0   # 1月 = (5+7)/2
    assert temps[6] == 21.0  # 7月 = (20+22)/2
    assert temps[1] is None  # 2月无数据


# ── 国家年均温 ─────────────────────────────────────

def test_country_annual(tmp_path: Path, monkeypatch) -> None:
    _write_csv(tmp_path, "GlobalLandTemperaturesByCountry.csv", [
        {"dt": "2013-01-01", "AverageTemperature": 25.0, "Country": "China"},
        {"dt": "2013-06-01", "AverageTemperature": 27.0, "Country": "China"},
        {"dt": "2013-01-01", "AverageTemperature": 10.0, "Country": "Russia"},
    ])
    client = _make_client(tmp_path, monkeypatch)
    resp = client.get("/api/country/annual?year=2013")

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["countries"][0] == "China"
    assert data["temps"][0] == 26.0
    assert data["countries"][1] == "Russia"
    assert data["temps"][1] == 10.0


# ── 城市排名 ────────────────────────────────────────

def test_city_temp(tmp_path: Path, monkeypatch) -> None:
    _write_csv(tmp_path, "GlobalLandTemperaturesByCity.csv", [
        {"dt": "2013-01-01", "AverageTemperature": 28.0, "City": "Bangkok", "Country": "Thailand", "Latitude": "13.75N", "Longitude": "100.5E"},
        {"dt": "2013-06-01", "AverageTemperature": 30.0, "City": "Bangkok", "Country": "Thailand", "Latitude": "13.75N", "Longitude": "100.5E"},
        {"dt": "2013-01-01", "AverageTemperature": 5.0, "City": "Moscow", "Country": "Russia", "Latitude": "55.75N", "Longitude": "37.6E"},
    ])
    client = _make_client(tmp_path, monkeypatch)
    resp = client.get("/api/city-temp?year=2013&limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["cities"][0] == "Bangkok"
    assert data["temps"][0] == 29.0


# ── 纬度带 ────────────────────────────────────────

def test_city_latband(tmp_path: Path, monkeypatch) -> None:
    _write_csv(tmp_path, "GlobalLandTemperaturesByCity.csv", [
        {"dt": "2000-01-01", "AverageTemperature": 25.0, "Latitude": "10N", "City": "A", "Country": "X"},
        {"dt": "2000-06-01", "AverageTemperature": 27.0, "Latitude": "10N", "City": "A", "Country": "X"},
        {"dt": "2000-01-01", "AverageTemperature": 5.0, "Latitude": "57N", "City": "B", "Country": "Y"},
        {"dt": "2000-01-01", "AverageTemperature": -10.0, "Latitude": "80N", "City": "C", "Country": "Z"},
    ])
    client = _make_client(tmp_path, monkeypatch)
    resp = client.get("/api/city/latband?min_year=2000")

    assert resp.status_code == 200
    data = resp.json()
    assert data["years"] == [2000]
    assert data["tropical"] == [26.0]
    assert data["temperate"] == [5.0]
    assert data["polar"] == [-10.0]
    assert data["count"] == 1
