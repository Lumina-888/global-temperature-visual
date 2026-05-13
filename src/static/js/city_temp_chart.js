(function () {
  const chartDom = document.getElementById("cityTempChart");
  const msgDom = document.getElementById("cityMsg");
  const yearInput = document.getElementById("cityYear");
  const limitInput = document.getElementById("cityLimit");
  const reloadBtn = document.getElementById("reloadCityBtn");
  const chart = echarts.init(chartDom);

  function setMessage(text, isError) {
    msgDom.textContent = text || "";
    msgDom.style.color = isError ? "#d9534f" : "#666";
  }

  async function load() {
    const year = Number(yearInput.value || 2013);
    const limit = Number(limitInput.value || 20);
    setMessage("加载中...", false);

    try {
      const resp = await fetch(`/api/city-temp?year=${year}&limit=${limit}`);
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "请求失败");
      }

      chart.setOption({
        title: { text: `${year} 年城市平均温度（按温度排序）`, left: "center" },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: 60, right: 20, top: 60, bottom: 80 },
        xAxis: {
          type: "category",
          name: "城市",
          data: data.cities,
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
      }, true);
      setMessage("加载完成，共 " + data.count + " 个城市。", false);
    } catch (err) {
      setMessage("加载失败：" + err.message, true);
    }
  }

  reloadBtn.addEventListener("click", load);
  window.addEventListener("resize", function () { chart.resize(); });
  load();
})();
