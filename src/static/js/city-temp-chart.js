/**
 * city-temp-chart.js（遗留文件 — 未被 index.html 引用）
 * ======================================================
 * 这个文件目前没有被页面加载，可能是早期版本的代码或者备用模块。
 * 它的功能是画一个"省平均温度排名"的条形图，
 * 引用了一些在 index.html 中不存在的 DOM 元素（chartCityRanking 等）。
 *
 * 如果将来需要在页面上恢复此功能，需要：
 * 1. 在 index.html 里添加对应的 HTML 元素
 * 2. 在 index.html 底部加上 <script src="/static/js/city-temp-chart.js"></script>
 */

(function () {
  "use strict";

  // 找 DOM 元素的快捷方式
  const $ = (id) => document.getElementById(id);

  // 设置卡片状态文字
  const setStatus = (id, text, cls) => {
    const d = $(id);
    if (d) { d.textContent = text; d.className = "card-status " + (cls || ""); }
  };

  // 加载动画的通用配置
  const loadingOpts = {
    text: "加载中...",
    color: "#4fc3f7",
    textColor: "#c8d6e5",
    maskColor: "rgba(15,25,35,0.8)",
  };

  let chartCity = null;  // 图表实例，初始为空

  // 确保图表实例已创建（如果还没创建就创建）
  const ensureChart = () => {
    const container = $("chartCityRanking");
    if (!container) return null;
    try {
      if (!chartCity) chartCity = echarts.init(container, null, { devicePixelRatio: 2 });
      return chartCity;
    } catch (e) {
      console.error("初始化城市图表失败", e);
      return null;
    }
  };

  // 加载并渲染省份温度排名
  const loadCityRanking = () => {
    const chart = ensureChart();
    if (!chart) return;  // 容器不存在，直接返回

    // 读取用户输入的年份和国家
    const elYear = $("cityYearInput");
    const elCountry = $("cityCountrySelect");
    const year = parseInt(elYear && elYear.value, 10) || 2013;
    const country = (elCountry && elCountry.value) || "United States";
    const limit = 15;  // 最多显示 15 个省/州

    setStatus("statusCity", "正在加载...", "loading");
    chart.showLoading(loadingOpts);

    // 请求后端 API
    fetch(`/api/state-temp?year=${year}&limit=${limit}&country=${encodeURIComponent(country)}`)
      .then(r => r.json())  // 解析 JSON
      .then(d => {
        // 翻转数组：高温的排最上面
        const regions = d.states.slice().reverse();
        const temps = d.temps.slice().reverse();

        chart.setOption({
          backgroundColor: "#152238",
          title: {
            text: year + " 年省平均温度排名（前 " + limit + "）",
            left: "center",
            textStyle: { color: "#c8d6e5", fontSize: 15 },
          },
          tooltip: {
            trigger: "axis",
            axisPointer: { type: "shadow" },
            formatter: p => p[0].name + "<br/>温度: " + p[0].value.toFixed(1) + " °C",
          },
          grid: { left: 100, right: 50, top: 50, bottom: 30 },
          xAxis: [{
            type: "value",
            name: "温度 (°C)",
            axisLabel: { color: "#8a9bb5", formatter: "{value} °C" },
          }],
          yAxis: [{
            type: "category",
            data: regions,
            axisLabel: { color: "#8a9bb5", fontSize: 11 },
          }],
          series: [{
            type: "bar",
            barMaxWidth: 26,
            data: temps.map(v => ({
              value: v,
              itemStyle: {
                // 按温度着色：>20°红, 10-20°橙, <10°蓝
                color: v > 20 ? "#d9534f" : v > 10 ? "#ffab40" : "#4fc3f7",
              },
            })),
          }],
        }, true);

        chart.hideLoading();
        setStatus("statusCity", "加载完成（" + year + " 年, " + d.count + " 省）", "ok");
      })
      .catch(err => {
        chart.hideLoading();
        setStatus("statusCity", "加载失败: " + (err && err.message ? err.message : err), "error");
      });
  };

  // 启动函数：创建实例 + 绑定事件 + 首次加载
  const start = () => {
    ensureChart();

    // 绑定刷新按钮
    const btn = $("reloadCityBtn");
    if (btn) btn.addEventListener("click", loadCityRanking);

    // 下拉菜单切换时自动刷新
    const sel = $("cityCountrySelect");
    if (sel) sel.addEventListener("change", loadCityRanking);

    loadCityRanking();  // 首次加载

    // 窗口缩放时图表跟着缩放
    window.addEventListener("resize", () => {
      try { if (chartCity) chartCity.resize(); } catch (e) {}
    });
  };

  // 等页面就绪后启动
  if (document.readyState === "complete") setTimeout(start, 100);
  else window.addEventListener("load", () => setTimeout(start, 100));
})();
