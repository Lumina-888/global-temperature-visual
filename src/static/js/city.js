;(function () {
  const stateChartDom = document.getElementById("stateTempChart");
  const stateMsgDom = document.getElementById("stateMsg");
  const stateYearInput = document.getElementById("stateYear");
  const countrySelect = document.getElementById("countrySelect");
  const reloadStateBtn = document.getElementById("reloadStateBtn");

  const stateChart = echarts.init(stateChartDom);

  function setMessage(dom, text, isError) {
    dom.textContent = text || "";
    dom.style.color = isError ? "#d9534f" : "#666";
  }

  async function loadStateTemp() {
    const year = Number(stateYearInput.value || 2013);
    const country = countrySelect.value;
    const limit = 15;
    setMessage(stateMsgDom, "加载中...", false);

    try {
      const resp = await fetch(`/api/state-temp?year=${year}&country=${encodeURIComponent(country)}&limit=${limit}`);
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "请求失败");
      }

      const option = {
        title: { text: `${year} 年 ${country} 州/省平均温度（按温度排序）`, left: "center" },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: 60, right: 20, top: 60, bottom: 80 },
        xAxis: {
          type: "category",
          name: "州/省",
          data: data.states,
          axisLabel: { interval: 0, rotate: 30 },
        },
        yAxis: {
          type: "value",
          name: "温度 (°C)",
          axisLabel: { formatter: "{value} °C" },
          scale: true,
        },
        series: [
          {
            name: "平均温度",
            type: "bar",
            data: data.temps,
            itemStyle: { color: "#5470C6" },
          },
        ],
      };

      stateChart.setOption(option, true);
      setMessage(stateMsgDom, "加载完成，共 " + data.count + " 个州/省。", false);
    } catch (err) {
      setMessage(stateMsgDom, "加载失败：" + err.message, true);
    }
  }

  reloadStateBtn.addEventListener("click", loadStateTemp);

  window.addEventListener("resize", function () {
    stateChart.resize();
  });

  loadStateTemp();
})();
