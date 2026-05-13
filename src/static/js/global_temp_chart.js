(function () {
  const chartDom = document.getElementById("globalTempChart");
  const msgDom = document.getElementById("msg");
  const minYearInput = document.getElementById("minYear");
  const reloadBtn = document.getElementById("reloadBtn");
  const chart = echarts.init(chartDom);

  function setMessage(text, isError) {
    msgDom.textContent = text || "";
    msgDom.style.color = isError ? "#d9534f" : "#666";
  }

  async function load() {
    const minYear = Number(minYearInput.value || 1850);
    setMessage("加载中...", false);

    try {
      const resp = await fetch("/api/global-temp?min_year=" + minYear);
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "请求失败");
      }

      const temps = data.temps || [];
      const minTemp = Math.min(...temps);
      const maxTemp = Math.max(...temps);
      const span = maxTemp - minTemp;
      const padding = Math.max(span * 0.1, 0.2);
      const yMin = Number((minTemp - padding).toFixed(2));
      const yMax = Number((maxTemp + padding).toFixed(2));

      chart.setOption({
        title: { text: "全球陆地平均温度变化（年均）", left: "center" },
        tooltip: { trigger: "axis" },
        grid: { left: 50, right: 20, top: 60, bottom: 60 },
        xAxis: {
          type: "category",
          name: "年份",
          data: data.years,
        },
        yAxis: {
          type: "value",
          name: "温度 (°C)",
          min: yMin,
          max: yMax,
          scale: true,
          axisLabel: { formatter: "{value} °C" },
        },
        dataZoom: [{ type: "inside" }, { type: "slider", bottom: 20 }],
        series: [
          {
            name: "年均温",
            type: "line",
            smooth: true,
            showSymbol: false,
            data: data.temps,
            lineStyle: { width: 2 },
          },
        ],
      }, true);
      setMessage("加载完成，共 " + data.count + " 条年度记录。", false);
    } catch (err) {
      setMessage("加载失败：" + err.message, true);
    }
  }

  reloadBtn.addEventListener("click", load);
  window.addEventListener("resize", function () { chart.resize(); });
  load();
})();
