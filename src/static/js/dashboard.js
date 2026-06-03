(function () {
  "use strict";

  const DBG = document.getElementById("debugBar");
  const dbg = (msg, color) => {
    if (DBG) DBG.textContent = "[Dashboard] " + msg;
    if (color && DBG) DBG.style.color = color;
    console.log("[Dashboard]", msg);
  };

  if (typeof echarts === "undefined") {
    dbg("FATAL: ECharts 库未加载！", "#d9534f");
    return;
  }
  dbg("ECharts v" + (echarts.version || "?") + " 就绪", "#ff9800");

  // ── 状态 ──────────────────────────────────────────
  let startYear = 1900;
  let worldGeoJson = null;
  let mapYear = 2024;
  const countryDataCache = {};
  let mapLoading = false;

  // ── DOM 引用 ──────────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const setStatus = (id, text, cls) => {
    const d = $(id);
    if (d) { d.textContent = text; d.className = "card-status " + (cls || ""); }
  };

  const elStartYear = $("startYear");
  const elEndYear = $("endYear");
  const elApply = $("applyFilter");
  const elFilterMsg = $("filterMsg");
  const elMapSlider = $("mapYearInput");
  const elMapLabel = $("mapYearLabel");

  // ── 图表实例（initAllCharts 赋值）──────────────────
  let chartGlobal, chartAnomaly, chartMonthly, chartMap, chartLatband, chartCity;

  // ── 共用的深色主题配置 ────────────────────────────
  const DARK_BG = "#152238";
  const AXIS_COMMON = {
    type: "category",
    axisLabel: { color: "#8a9bb5" },
    axisLine: { lineStyle: { color: "#1e3a5f" } },
    axisTick: { lineStyle: { color: "#1e3a5f" } },
  };

  const valueAxis = (name) => ({
    type: "value", name, scale: true,
    nameTextStyle: { color: "#8a9bb5" },
    axisLabel: { color: "#8a9bb5", formatter: "{value} °C" },
    splitLine: { lineStyle: { color: "#1a2d42", type: "dashed" } },
  });

  const loadingOpts = {
    text: "加载中...", color: "#4fc3f7",
    textColor: "#c8d6e5", maskColor: "rgba(15,25,35,0.8)",
  };

  // ── 国家名映射（数据集 → GeoJSON）──────────────────
  const COUNTRY_NAME_MAP = {
    "United States": "United States of America",
    "Russia": "Russian Federation",
    "Congo": "Democratic Republic of the Congo",
    "Cote D'Ivoire": "Ivory Coast",
    "Tanzania": "United Republic of Tanzania",
    "South Korea": "Republic of Korea",
    "North Korea": "Dem. Rep. Korea",
    "Syria": "Syrian Arab Republic",
    "Vietnam": "Viet Nam",
    "Laos": "Lao PDR",
    "Brunei": "Brunei Darussalam",
    "Iran": "Iran (Islamic Republic of)",
    "Bolivia": "Bolivia (Plurinational State of)",
    "Venezuela": "Venezuela (Bolivarian Republic of)",
    "Moldova": "Republic of Moldova",
    "Bahamas": "The Bahamas",
    "Myanmar": "Myanmar",
    "Burma": "Myanmar",
  };
  const mapToGeoJsonName = (n) => COUNTRY_NAME_MAP[n] || n;

  // ── GeoJSON 加载 ──────────────────────────────────
  const loadWorldGeoJson = () => {
    dbg("加载世界地图 GeoJSON...");
    setStatus("statusMap", "正在加载地图数据...", "loading");

    const urls = [
      "/static/data/world.geo.json",
      "https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json",
    ];

    const tryUrl = (idx) => {
      if (idx >= urls.length) return Promise.reject(new Error("所有数据源失败"));
      dbg("尝试: " + urls[idx]);
      return fetch(urls[idx])
        .then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .catch(() => tryUrl(idx + 1));
    };

    return tryUrl(0).then(geo => {
      worldGeoJson = geo;
      dbg("GeoJSON 就绪 (" + (geo.features || []).length + " 个区域)");
      echarts.registerMap("world", geo);
      setStatus("statusMap", "地图数据就绪", "ok");
    });
  };

  // ── 初始化图表实例 ────────────────────────────────
  const initAllCharts = () => {
    const containers = [
      ["chartGlobalAnnual", "chartGlobalAnnual"],
      ["chartAnomaly", "chartAnomaly"],
      ["chartMonthly", "chartMonthly"],
      ["chartWorldMap", "chartWorldMap"],
      ["chartLatband", "chartLatband"],
    ];
    const results = [];
    containers.forEach(([id, name]) => {
      try {
        results.push(echarts.init($(id), null, { devicePixelRatio: 2 }));
        dbg("✓ " + name);
      } catch (e) {
        results.push(null);
        dbg("✗ " + name + ": " + e.message, "#d9534f");
      }
    });
    [chartGlobal, chartAnomaly, chartMonthly, chartMap, chartLatband] = results;
    dbg(results.filter(Boolean).length + "/5 图表实例已创建", "#81c784");
  };

  // ── 1. 全球温度多线对比 ───────────────────────────
  const loadGlobalAnnual = () => {
    if (!chartGlobal) return;
    setStatus("statusGlobal", "正在加载...", "loading");
    chartGlobal.showLoading(loadingOpts);

    fetch("/api/global/annual?min_year=" + startYear)
      .then(r => r.json())
      .then(d => {
        dbg("全球年均温: " + d.count + " 条记录");
        // 动态更新结束年份
        if (d.years && d.years.length > 0) {
          const maxYr = d.years[d.years.length - 1];
          if (elEndYear) elEndYear.value = maxYr;
        }
        chartGlobal.setOption({
          backgroundColor: DARK_BG,
          title: { text: "全球温度变化趋势", left: "center", textStyle: { color: "#e0e0e0", fontSize: 16, fontWeight: "bold" } },
          tooltip: {
            trigger: "axis", backgroundColor: "rgba(21,34,56,0.95)", borderColor: "#1e3a5f",
            formatter: params => {
              let s = "<b>" + params[0].axisValue + " 年</b><br/>";
              params.forEach(p => {
                if (p.value != null) s += p.marker + " " + p.seriesName + ": <b>" + p.value.toFixed(2) + " °C</b><br/>";
              });
              return s;
            },
          },
          legend: { bottom: 4, textStyle: { color: "#8a9bb5", fontSize: 11 } },
          grid: { left: 60, right: 30, top: 55, bottom: 45 },
          xAxis: [{ ...AXIS_COMMON, data: d.years }],
          yAxis: [valueAxis("温度 (°C)")],
          dataZoom: [{ type: "inside" }, { type: "slider", bottom: 20, height: 18, textStyle: { color: "#8a9bb5" } }],
          series: [
            { name: "陆地最高温", type: "line", data: d.land_max, smooth: true, symbol: "none",
              lineStyle: { color: "#ef9a9a", width: 1.5, type: "dashed" } },
            { name: "陆地平均温", type: "line", data: d.land_avg, smooth: true, symbol: "none",
              lineStyle: { color: "#ef5350", width: 2.5 } },
            { name: "海陆综合温", type: "line", data: d.land_ocean_avg, smooth: true, symbol: "none",
              lineStyle: { color: "#42a5f5", width: 2.5 },
              areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1,
                colorStops: [{ offset: 0, color: "rgba(66,165,245,0.1)" }, { offset: 1, color: "rgba(66,165,245,0.0)" }] } },
            },
            { name: "陆地最低温", type: "line", data: d.land_min, smooth: true, symbol: "none",
              lineStyle: { color: "#90caf9", width: 1.5, type: "dashed" } },
          ],
        }, true);
        chartGlobal.hideLoading();
        setStatus("statusGlobal", "加载完成（" + d.count + " 年）", "ok");
      })
      .catch(err => {
        chartGlobal.hideLoading();
        setStatus("statusGlobal", "加载失败: " + err.message, "error");
      });
  };

  // ── 2. 温度距平柱状图 ───────────────────────────────
  const loadAnomaly = () => {
    if (!chartAnomaly) return;
    setStatus("statusAnomaly", "正在加载...", "loading");
    chartAnomaly.showLoading(loadingOpts);

    fetch("/api/global/anomaly")
      .then(r => r.json())
      .then(d => {
        dbg("距平数据: 基准均值 " + d.baseline_avg + "°C");
        const idx = Math.max(0, d.years.indexOf(startYear));
        const years = d.years.slice(idx);
        const anomalies = d.anomalies.slice(idx);

        chartAnomaly.setOption({
          backgroundColor: DARK_BG,
          title: { text: "全球温度距平（基准: " + d.baseline_start + "-" + d.baseline_end + "）", left: "center", textStyle: { color: "#c8d6e5", fontSize: 15 } },
          tooltip: { trigger: "axis", formatter: p => p[0].axisValue + " 年<br/>距平: " + (p[0].value >= 0 ? "+" : "") + p[0].value.toFixed(2) + " °C" },
          grid: { left: 55, right: 20, top: 50, bottom: 40 },
          xAxis: [{ ...AXIS_COMMON, data: years }],
          yAxis: [valueAxis("距平 (°C)")],
          series: [{
            type: "bar",
            data: anomalies.map(v => ({ value: v, itemStyle: { color: v >= 0 ? "#d9534f" : "#4fc3f7" } })),
          }],
        }, true);
        chartAnomaly.hideLoading();
        setStatus("statusAnomaly", "加载完成（" + years.length + " 年）", "ok");
      })
      .catch(err => {
        chartAnomaly.hideLoading();
        setStatus("statusAnomaly", "加载失败: " + err.message, "error");
      });
  };

  // ── 3. 月均温季节周期 ───────────────────────────────
  const loadMonthly = () => {
    if (!chartMonthly) return;
    setStatus("statusMonthly", "正在加载...", "loading");
    chartMonthly.showLoading(loadingOpts);
    const MONTHS = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];

    fetch("/api/global/monthly")
      .then(r => r.json())
      .then(d => {
        const valid = d.temps.filter(t => t != null);
        const avgTemp = valid.length > 0 ? +(valid.reduce((a, b) => a + b, 0) / valid.length).toFixed(1) : 0;
        dbg("月均温: " + valid.length + "/12 月有效");

        chartMonthly.setOption({
          backgroundColor: DARK_BG,
          title: { text: "全球月均温季节周期（多年平均）", left: "center", textStyle: { color: "#c8d6e5", fontSize: 15 } },
          tooltip: { trigger: "axis", formatter: p => MONTHS[p[0].dataIndex] + " 均温: " + (p[0].value != null ? p[0].value.toFixed(1) + " °C" : "无数据") },
          grid: { left: 55, right: 20, top: 50, bottom: 30 },
          xAxis: [{ ...AXIS_COMMON, data: MONTHS }],
          yAxis: [valueAxis("温度 (°C)")],
          series: [{
            type: "line", data: d.temps, smooth: true, connectNulls: true,
            symbol: "circle", symbolSize: 6,
            lineStyle: { color: "#81c784", width: 2 },
            areaStyle: { color: "rgba(129,199,132,0.15)" },
            markLine: {
              silent: true,
              data: [{ yAxis: avgTemp, name: "年均", label: { formatter: "年均\n{c}°C", color: "#ff9800" } }],
              lineStyle: { color: "#ff9800", type: "dashed", width: 1.5 },
              symbol: "none",
            },
          }],
        }, true);
        chartMonthly.hideLoading();
        setStatus("statusMonthly", "加载完成", "ok");
      })
      .catch(err => {
        chartMonthly.hideLoading();
        setStatus("statusMonthly", "加载失败: " + err.message, "error");
      });
  };

  // ── 4. 世界地图 ────────────────────────────────────
  const loadMapData = (year, callback) => {
    if (countryDataCache[year]) { callback(countryDataCache[year]); return; }
    dbg("请求国家数据 (year=" + year + ")");
    fetch("/api/country/annual?year=" + year)
      .then(r => r.json())
      .then(d => {
        const data = d.countries.map((c, i) => ({ name: mapToGeoJsonName(c), value: d.temps[i] }));
        dbg("国家数据就绪: " + d.count + " 国 (year=" + year + ")");
        countryDataCache[year] = data;
        callback(data);
      })
      .catch(err => {
        dbg("ERROR: 国家数据加载失败 " + err.message, "#d9534f");
        callback([]);
      });
  };

  const renderMap = (year, data) => {
    if (!chartMap) return;
    dbg("渲染地图: " + year + " 年, " + data.length + " 个数据点");
    chartMap.setOption({
      backgroundColor: DARK_BG,
      title: { text: year + " 年全球各国平均温度", left: "center", textStyle: { color: "#c8d6e5", fontSize: 15 } },
      tooltip: {
        trigger: "item",
        formatter: p => p.name + "<br/>年均温: " + (p.value != null ? p.value.toFixed(1) + " °C" : "无数据"),
      },
      visualMap: {
        min: -10, max: 30,
        inRange: { color: ["#4fc3f7", "#e8f5e9", "#fff176", "#ffab40", "#d9534f"] },
        text: ["30°C", "-10°C"], textStyle: { color: "#8a9bb5" },
        left: 8, bottom: 16,
      },
      geo: {
        map: "world", roam: true, zoom: 1.15, center: [15, 10],
        itemStyle: { areaColor: "#1a2d42", borderColor: "#2a4a6b", borderWidth: 0.5 },
        emphasis: { label: { show: false }, itemStyle: { areaColor: "#3a5a7b" } },
      },
      series: [{ type: "map", map: "world", geoIndex: 0, data }],
    }, true);
    setStatus("statusMap", "加载完成（" + year + " 年, " + data.length + " 国）", "ok");
  };

  const updateMap = (year) => {
    if (mapLoading) return;
    mapYear = year;
    elMapLabel.textContent = year;
    if (!worldGeoJson) { setStatus("statusMap", "等待地图数据...", "loading"); return; }
    mapLoading = true;
    setStatus("statusMap", "正在加载 " + year + " 年数据...", "loading");
    loadMapData(year, data => { renderMap(year, data); mapLoading = false; });
  };

  const initMap = () => {
    dbg("初始化地图模块");
    updateMap(mapYear);
    elMapSlider.addEventListener("change", () => updateMap(parseInt(elMapSlider.value, 10)));
  };

  // ── 5. 纬度带 ──────────────────────────────────────
  const loadLatband = () => {
    if (!chartLatband) return;
    setStatus("statusLatband", "正在加载...", "loading");
    chartLatband.showLoading(loadingOpts);

    fetch("/api/city/latband?min_year=" + startYear)
      .then(r => r.json())
      .then(d => {
        dbg("纬度带数据: " + d.count + " 年");
        chartLatband.setOption({
          backgroundColor: DARK_BG,
          title: { text: "纬度带温度变化趋势对比", left: "center", textStyle: { color: "#c8d6e5", fontSize: 15 } },
          tooltip: { trigger: "axis",
            formatter: params => {
              let s = params[0].axisValue + " 年<br/>";
              params.forEach(p => { if (p.value != null) s += p.marker + " " + p.seriesName + ": " + p.value.toFixed(1) + " °C<br/>"; });
              return s;
            },
          },
          legend: { bottom: 0, textStyle: { color: "#8a9bb5" } },
          grid: { left: 55, right: 20, top: 50, bottom: 40 },
          xAxis: [{ ...AXIS_COMMON, data: d.years }],
          yAxis: [valueAxis("温度 (°C)")],
          series: [
            { name: d.tropical_label || "热带", type: "line", data: d.tropical, smooth: true, symbol: "none", lineStyle: { color: "#d9534f", width: 2 } },
            { name: d.temperate_label || "温带", type: "line", data: d.temperate, smooth: true, symbol: "none", lineStyle: { color: "#81c784", width: 2 } },
            { name: d.polar_label || "寒带", type: "line", data: d.polar, smooth: true, symbol: "none", lineStyle: { color: "#4fc3f7", width: 2 } },
          ],
        }, true);
        chartLatband.hideLoading();
        setStatus("statusLatband", "加载完成（" + d.count + " 年）", "ok");
      })
      .catch(err => {
        chartLatband.hideLoading();
        setStatus("statusLatband", "加载失败: " + err.message, "error");
      });
  };

  // 城市图表逻辑已迁移到独立脚本 `city-temp-chart.js`

  // ── 全局筛选 ──────────────────────────────────────
  const applyGlobalFilter = () => {
    const s = parseInt(elStartYear.value, 10);
    const e = parseInt(elEndYear.value, 10);
    if (isNaN(s) || isNaN(e) || s >= e) {
      elFilterMsg.textContent = "请输入有效年份范围（起始 < 结束）";
      return;
    }
    startYear = s;
    elFilterMsg.textContent = "已更新: " + s + "–" + e;
    dbg("全局筛选: " + s + "–" + e);
    loadGlobalAnnual();
    loadAnomaly();
    loadLatband();
  };

  // ── resize ────────────────────────────────────────
  window.addEventListener("resize", () => {
    [chartGlobal, chartAnomaly, chartMonthly, chartMap, chartLatband, chartCity]
      .forEach(c => { try { if (c) c.resize(); } catch (e) { /* ignore */ } });
  });

  // ── 启动 ─────────────────────────────────────────
  const start = () => {
    dbg("══════ 启动仪表板 ══════", "#4fc3f7");
    initAllCharts();

    if (!chartGlobal && !chartAnomaly && !chartMonthly && !chartLatband && !chartCity) {
      dbg("FATAL: 所有图表容器初始化失败", "#d9534f");
      return;
    }

    elApply.addEventListener("click", applyGlobalFilter);

    loadGlobalAnnual();
    loadAnomaly();
    loadMonthly();
    loadLatband();

    loadWorldGeoJson()
      .then(() => initMap())
      .catch(err => {
        dbg("地图模块失败: " + err.message, "#d9534f");
        setStatus("statusMap", "地图不可用", "error");
        if (chartMap) chartMap.setOption({
          backgroundColor: DARK_BG,
          title: { text: "地图加载失败\n请检查网络连接", left: "center", top: "center", textStyle: { color: "#d9534f", fontSize: 14 } },
        });
      });
  };

  // 确保 CSS 布局完成后初始化（避免容器尺寸为 0）
  if (document.readyState === "complete") {
    setTimeout(start, 100);
  } else {
    window.addEventListener("load", () => setTimeout(start, 100));
  }
})();
