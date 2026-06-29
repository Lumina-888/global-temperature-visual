/**
 * city_temp_chart.js（遗留文件 — 未被 index.html 引用）
 * =====================================================
 * 这个文件目前没有被页面加载，是早期版本的城市温度图表代码。
 * 它引用的 DOM 元素（cityTempChart, cityMsg, cityYear, cityLimit, reloadCityBtn）
 * 在 index.html 中不存在。
 *
 * 与当前在用的 city.js 的区别：
 *   - city.js 按国家筛选（有国家下拉菜单），用的是 /api/city-temp 接口
 *   - 本文件不做国家筛选，用的是旧接口 /api/city-temp?year=...&limit=...
 */

(function () {
  // 找到 HTML 里的元素
  const chartDom = document.getElementById("cityTempChart");
  const msgDom = document.getElementById("cityMsg");
  const yearInput = document.getElementById("cityYear");
  const limitInput = document.getElementById("cityLimit");
  const reloadBtn = document.getElementById("reloadCityBtn");

  // 创建 ECharts 实例（画板）
  const chart = echarts.init(chartDom);

  // 设置状态提示文字
  function setMessage(text, isError) {
    msgDom.textContent = text || "";
    msgDom.style.color = isError ? "#d9534f" : "#666";
  }

  // 加载数据并画图
  async function load() {
    const year = Number(yearInput.value || 2013);     // 年份，默认 2013
    const limit = Number(limitInput.value || 20);      // 最多显示几个城市
    setMessage("加载中...", false);

    try {
      // 请求后端 API
      const resp = await fetch(`/api/city-temp?year=${year}&limit=${limit}`);
      const data = await resp.json();  // 把 JSON 字符串转成对象

      if (!resp.ok) {
        throw new Error(data.error || "请求失败");
      }

      // 配置并渲染图表
      chart.setOption({
        title: {
          text: `${year} 年城市平均温度（按温度排序）`,
          left: "center",
        },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },  // 阴影指示器
        },
        grid: { left: 60, right: 20, top: 60, bottom: 80 },

        // X 轴 = 城市名（竖向排列，所以要旋转 30 度才不会重叠）
        xAxis: {
          type: "category",
          name: "城市",
          data: data.cities,
          axisLabel: { interval: 0, rotate: 30 },
        },

        // Y 轴 = 温度数值
        yAxis: {
          type: "value",
          name: "温度 (°C)",
          axisLabel: { formatter: "{value} °C" },
          scale: true,  // 自动调整范围，不强制从 0 开始
        },

        // 数据系列
        series: [{
          name: "平均温度",
          type: "bar",       // 柱状图
          data: data.temps,  // 温度数组
          itemStyle: { color: "#5470C6" },  // 柱子颜色
        }],
      }, true);  // true = 完全替换旧配置

      setMessage("加载完成，共 " + data.count + " 个城市。", false);
    } catch (err) {
      // 网络错误或服务器报错
      setMessage("加载失败：" + err.message, true);
    }
  }

  // 点刷新按钮 → 重新加载
  reloadBtn.addEventListener("click", load);

  // 窗口缩放 → 图表跟着缩放
  window.addEventListener("resize", function () { chart.resize(); });

  // 页面加载完立刻画图
  load();
})();
