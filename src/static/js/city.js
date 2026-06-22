;(function () {
  "use strict";

  const stateChartDom = document.getElementById("stateTempChart");
  const stateMsgDom = document.getElementById("stateMsg");
  const stateYearInput = document.getElementById("stateYear");
  const countrySelect = document.getElementById("countrySelect");
  const reloadStateBtn = document.getElementById("reloadStateBtn");

  if (!stateChartDom) {
    console.error("[city.js] 找不到 stateTempChart 容器");
    return;
  }

  const stateChart = echarts.init(stateChartDom, null, {
    devicePixelRatio: 2,
  });

  function setMessage(dom, text, isError) {
    dom.textContent = text || "";
    dom.style.color = isError ? "#d9534f" : "#8a9bb5";
  }

  async function loadCityTemp() {
    const year = Number(stateYearInput.value || 2024);
    const country = countrySelect.value;
    const limit = 15;
    setMessage(stateMsgDom, "加载中...", false);
    stateChart.showLoading({
      text: "加载中...",
      color: "#4fc3f7",
      textColor: "#c8d6e5",
      maskColor: "rgba(15,25,35,0.8)",
    });

    try {
      const resp = await fetch(
        "/api/city-temp?year=" +
          year +
          "&country=" +
          encodeURIComponent(country) +
          "&limit=" +
          limit
      );
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || "请求失败");
      }

      // 水平条形图：反转数组使温度最高的显示在最上方
      const cities = data.cities.slice().reverse();
      const temps = data.temps.slice().reverse();

      const option = {
        backgroundColor: "#152238",
        title: {
          text: year + " 年 " + country + " 城市平均温度排名（前 " + limit + "）",
          left: "center",
          textStyle: { color: "#c8d6e5", fontSize: 15 },
        },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "shadow" },
          backgroundColor: "rgba(21,34,56,0.95)",
          borderColor: "#1e3a5f",
          formatter: function (p) {
            return (
              "<b>" +
              p[0].name +
              "</b><br/>年均温: <b>" +
              p[0].value.toFixed(1) +
              " °C</b>"
            );
          },
        },
        grid: { left: 110, right: 50, top: 55, bottom: 30 },
        xAxis: {
          type: "value",
          name: "温度 (°C)",
          nameTextStyle: { color: "#8a9bb5" },
          axisLabel: { color: "#8a9bb5", formatter: "{value} °C" },
          splitLine: {
            lineStyle: { color: "#1a2d42", type: "dashed" },
          },
        },
        yAxis: {
          type: "category",
          data: cities,
          axisLabel: { color: "#8a9bb5", fontSize: 11 },
          axisLine: { lineStyle: { color: "#1e3a5f" } },
        },
        series: [
          {
            name: "年均温",
            type: "bar",
            barMaxWidth: 26,
            data: temps.map(function (v) {
              return {
                value: v,
                itemStyle: {
                  color:
                    v > 20 ? "#d9534f" : v > 10 ? "#ffab40" : "#4fc3f7",
                },
              };
            }),
          },
        ],
      };

      stateChart.setOption(option, true);
      stateChart.hideLoading();
      setMessage(
        stateMsgDom,
        "加载完成，共 " + data.count + " 个城市。",
        false
      );
    } catch (err) {
      stateChart.hideLoading();
      setMessage(stateMsgDom, "加载失败：" + err.message, true);
    }
  }

  reloadStateBtn.addEventListener("click", loadCityTemp);
  countrySelect.addEventListener("change", loadCityTemp);

  window.addEventListener("resize", function () {
    if (stateChart && !stateChart.isDisposed()) {
      stateChart.resize();
    }
  });

  loadCityTemp();
})();
