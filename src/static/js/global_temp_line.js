/**
 * global_temp_line.js（遗留文件 — 未被 index.html 引用）
 * ========================================================
 * 这个文件目前没有被页面加载，功能与 global_temp_chart.js 几乎一模一样。
 * 都是画"全球陆地平均温度变化"的折线图，只是代码风格略有不同。
 *
 * 与 global_temp_chart.js 的小区别：
 *   - 变量命名略有不同（如 globalChart vs chart）
 *   - setMessage 函数接受 dom 参数而不是硬编码
 *   - 使用分号开头（;）的 IIFE 风格防止合并时出错
 */

;(function () {
  // 找到 HTML 元素
  const globalChartDom = document.getElementById("globalTempChart");
  const globalMsgDom = document.getElementById("msg");
  const minYearInput = document.getElementById("minYear");
  const reloadBtn = document.getElementById("reloadBtn");

  // 创建图表实例
  const globalChart = echarts.init(globalChartDom);

  // 设置提示文字
  function setMessage(dom, text, isError) {
    dom.textContent = text || "";
    dom.style.color = isError ? "#d9534f" : "#666";
  }

  // 加载数据并画图
  async function loadGlobalTemp() {
    const minYear = Number(minYearInput.value || 1850);
    setMessage(globalMsgDom, "加载中...", false);

    try {
      const resp = await fetch("/api/global-temp?min_year=" + minYear);
      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.error || "请求失败");
      }

      // 计算 Y 轴动态范围（带 padding 防止曲线贴边）
      const temps = data.temps || [];
      const minTemp = Math.min(...temps);
      const maxTemp = Math.max(...temps);
      const span = maxTemp - minTemp;
      const padding = Math.max(span * 0.1, 0.2);
      const yMin = Number((minTemp - padding).toFixed(2));
      const yMax = Number((maxTemp + padding).toFixed(2));

      const option = {
        title: { text: "全球陆地平均温度变化（年均）", left: "center" },
        tooltip: { trigger: "axis" },
        grid: { left: 50, right: 20, top: 60, bottom: 60 },
        xAxis: { type: "category", name: "年份", data: data.years },
        yAxis: {
          type: "value", name: "温度 (°C)",
          min: yMin, max: yMax, scale: true,
          axisLabel: { formatter: "{value} °C" },
        },
        dataZoom: [{ type: "inside" }, { type: "slider", bottom: 20 }],
        series: [{
          name: "年均温", type: "line", smooth: true,
          showSymbol: false, data: data.temps, lineStyle: { width: 2 },
        }],
      };

      globalChart.setOption(option, true);
      setMessage(globalMsgDom, "加载完成，共 " + data.count + " 条年度记录。", false);
    } catch (err) {
      setMessage(globalMsgDom, "加载失败：" + err.message, true);
    }
  }

  // 绑定刷新按钮
  reloadBtn.addEventListener("click", loadGlobalTemp);

  // 窗口缩放
  window.addEventListener("resize", function () { globalChart.resize(); });

  // 首次加载
  loadGlobalTemp();
})();
