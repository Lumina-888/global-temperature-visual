/**
 * global_temp_chart.js（遗留文件 — 未被 index.html 引用）
 * ========================================================
 * 这个文件目前没有被页面加载，是早期版本的全球温度折线图代码。
 * 它引用的 DOM 元素（globalTempChart, msg, minYear, reloadBtn）
 * 在 index.html 中不存在。
 *
 * 功能：画一条"全球陆地平均温度变化"的折线图，带年份筛选和缩放控件。
 * 与当前 dashboard.js 中的 loadGlobalAnnual() 功能类似但更简单（只有一条线）。
 */

(function () {
  // 找到 HTML 元素
  const chartDom = document.getElementById("globalTempChart");
  const msgDom = document.getElementById("msg");
  const minYearInput = document.getElementById("minYear");
  const reloadBtn = document.getElementById("reloadBtn");

  // 创建图表实例
  const chart = echarts.init(chartDom);

  // 设置提示文字
  function setMessage(text, isError) {
    msgDom.textContent = text || "";
    msgDom.style.color = isError ? "#d9534f" : "#666";
  }

  // 加载数据并画图
  async function load() {
    const minYear = Number(minYearInput.value || 1850);  // 起始年份，默认 1850
    setMessage("加载中...", false);

    try {
      // 请求后端 API
      const resp = await fetch("/api/global-temp?min_year=" + minYear);
      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(data.error || "请求失败");
      }

      // 计算 Y 轴范围：让图表上下留一点空白（10% 或至少 0.2°C）
      const temps = data.temps || [];
      const minTemp = Math.min(...temps);  // 展开运算符 ... = 把数组拆成单个参数
      const maxTemp = Math.max(...temps);
      const span = maxTemp - minTemp;       // 温度跨度
      const padding = Math.max(span * 0.1, 0.2);  // 留白 = 跨度的 10%，至少 0.2°C
      const yMin = Number((minTemp - padding).toFixed(2));
      const yMax = Number((maxTemp + padding).toFixed(2));

      chart.setOption({
        title: {
          text: "全球陆地平均温度变化（年均）",
          left: "center",
        },
        tooltip: {
          trigger: "axis",  // 坐标轴触发
        },
        grid: { left: 50, right: 20, top: 60, bottom: 60 },

        // X 轴 = 年份
        xAxis: {
          type: "category",
          name: "年份",
          data: data.years,
        },

        // Y 轴 = 温度（动态范围）
        yAxis: {
          type: "value",
          name: "温度 (°C)",
          min: yMin,
          max: yMax,
          scale: true,
          axisLabel: { formatter: "{value} °C" },
        },

        // 缩放控件
        dataZoom: [
          { type: "inside" },                    // 鼠标滚轮缩放
          { type: "slider", bottom: 20 },        // 底部滑动条
        ],

        series: [{
          name: "年均温",
          type: "line",         // 折线图
          smooth: true,          // 平滑曲线
          showSymbol: false,     // 不显示数据点
          data: data.temps,
          lineStyle: { width: 2 },
        }],
      }, true);

      setMessage("加载完成，共 " + data.count + " 条年度记录。", false);
    } catch (err) {
      setMessage("加载失败：" + err.message, true);
    }
  }

  // 绑定按钮
  reloadBtn.addEventListener("click", load);

  // 响应窗口缩放
  window.addEventListener("resize", function () { chart.resize(); });

  // 首次加载
  load();
})();
