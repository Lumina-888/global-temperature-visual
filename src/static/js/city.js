/**
 * city.js — 城市温度排名图表
 * ============================
 * 这个脚本负责页面右下角的"城市平均温度排名"卡片。
 *
 * 它做的事情（按顺序）：
 * 1. 找到 HTML 里的图表容器和控件（年份输入框、国家下拉菜单、刷新按钮）
 * 2. 创建一个 ECharts 实例（= 一个能画图的画板）
 * 3. 向后端请求某个国家、某个年份的城市温度数据
 * 4. 把数据画成水平条形图（温度最高的城市排在最上面）
 * 5. 当用户切换年份/国家或点"刷新"时，重新加载数据并重画图表
 *
 * 数据来源：后端 API  /api/city-temp?year=2024&country=China&limit=15
 *           返回 { cities: ["北京","上海",...], temps: [12.5, 16.2,...], count: 15 }
 */

;(function () {
  "use strict";  // 严格模式：禁止写不规范的 JS 代码（比如用未声明的变量）

  // ──────────────────────────────────────────
  // 第一步：找到页面上需要的 DOM 元素
  // ──────────────────────────────────────────
  // DOM = Document Object Model，可以理解为"HTML 元素的 JS 表示"
  // document.getElementById("xxx") = 按 id 找到对应的 HTML 元素
  // 如果找不到（比如 HTML 里没有这个 id），返回 null

  const stateChartDom = document.getElementById("stateTempChart");
  // ↑ 图表画布——ECharts 会在这个 div 里画条形图

  const stateMsgDom = document.getElementById("stateMsg");
  // ↑ 状态提示文字——显示"加载中..."或"加载完成"或报错

  const stateYearInput = document.getElementById("stateYear");
  // ↑ 年份输入框——用户输入想查看的年份

  const countrySelect = document.getElementById("countrySelect");
  // ↑ 国家下拉菜单——用户选择要看哪个国家

  const reloadStateBtn = document.getElementById("reloadStateBtn");
  // ↑ 刷新按钮——用户点它来手动重新加载数据

  // 如果连图表容器都没有，说明 HTML 里缺少这个元素，直接退出
  if (!stateChartDom) {
    console.error("[city.js] 找不到 stateTempChart 容器");
    return;
  }

  // ──────────────────────────────────────────
  // 第二步：创建 ECharts 实例（画板）
  // ──────────────────────────────────────────
  // echarts.init(容器, 主题, 配置)
  // devicePixelRatio: 2 表示用 2 倍分辨率渲染（在 Retina 屏幕上更清晰）

  const stateChart = echarts.init(stateChartDom, null, {
    devicePixelRatio: 2,
  });

  /**
   * 设置状态提示文字
   * @param {HTMLElement} dom      - 显示文字的 DOM 元素
   * @param {string}      text     - 要显示的文字
   * @param {boolean}     isError  - true = 红色报错样式，false = 正常灰蓝色
   */
  function setMessage(dom, text, isError) {
    dom.textContent = text || "";
    dom.style.color = isError ? "#d9534f" : "#8a9bb5";
    //            ↑ 三元表达式：条件 ? 真的值 : 假的值
    //              如果 isError 是 true → 红色(#d9534f)
    //              如果 isError 是 false → 灰蓝(#8a9bb5)
  }

  /**
   * 核心函数：加载城市温度数据并画出条形图
   * async = 异步函数，里面可以用 await 等待网络请求完成
   *
   * 流程图：
   *   读取年份和国家 → 发网络请求 → 等服务器回复 → 拿到数据 → 画图
   */
  async function loadCityTemp() {
    // 1. 读取用户输入的年份（如果没填就用 2024）
    const year = Number(stateYearInput.value || 2024);
    // 2. 读取用户选择的国家
    const country = countrySelect.value;
    // 3. 最多显示 15 个城市
    const limit = 15;

    // 4. 显示"加载中..."提示
    setMessage(stateMsgDom, "加载中...", false);

    // 5. 在图表上显示加载动画（转圈圈）
    stateChart.showLoading({
      text: "加载中...",
      color: "#4fc3f7",
      textColor: "#c8d6e5",
      maskColor: "rgba(15,25,35,0.8)",
    });

    try {
      // 6. 向后端发送请求，获取城市温度数据
      //    fetch() 就像在浏览器地址栏输入网址，只不过是用代码来做
      //    await 表示"等这个操作完成再继续，不要急着往下跑"
      const resp = await fetch(
        "/api/city-temp?year=" +
          year +
          "&country=" +
          encodeURIComponent(country) +   // encodeURIComponent 把中文等国名转成 URL 能识别的格式
          "&limit=" +
          limit
      );

      // 7. 把服务器返回的 JSON 字符串转成 JS 对象
      //    比如 '{"cities":["北京"],"temps":[12.5]}' → { cities: ["北京"], temps: [12.5] }
      const data = await resp.json();

      // 8. 如果服务器返回了错误状态码（比如 404、500），抛出错误
      if (!resp.ok) {
        throw new Error(data.detail || "请求失败");
      }

      // 9. 数据翻转——让温度最高的城市排在最上面
      //    因为条形图默认从下往上画，不反转的话最冷的在最上面
      //    .slice() = 复制一份数组（不改原数组）
      //    .reverse() = 把数组倒过来：[1,2,3] 变成 [3,2,1]
      const cities = data.cities.slice().reverse();
      const temps = data.temps.slice().reverse();

      // 10. 配置图表——告诉 ECharts 要画成什么样
      const option = {
        backgroundColor: "#152238",  // 和卡片背景一样的深蓝色

        // 标题
        title: {
          text: year + " 年 " + country + " 城市平均温度排名（前 " + limit + "）",
          left: "center",
          textStyle: { color: "#c8d6e5", fontSize: 15 },
        },

        // 鼠标悬停时显示的提示框
        tooltip: {
          trigger: "axis",       // 触发方式：坐标轴触发（鼠标移到柱子上就弹）
          axisPointer: { type: "shadow" },  // 鼠标悬停时显示阴影指示器
          backgroundColor: "rgba(21,34,56,0.95)",  // 半透明深蓝背景
          borderColor: "#1e3a5f",
          formatter: function (p) {
            // p 是数组，p[0] 是当前柱子对应的数据
            return (
              "<b>" + p[0].name + "</b><br/>年均温: <b>" +
              p[0].value.toFixed(1) + " °C</b>"
            );
            // toFixed(1) = 保留 1 位小数，比如 15.67 → "15.7"
          },
        },

        // 图表边距（left 设大一点，因为城市名可能很长）
        grid: { left: 110, right: 50, top: 55, bottom: 30 },

        // X 轴（水平方向）= 温度数值
        xAxis: {
          type: "value",     // 数值轴
          name: "温度 (°C)",
          nameTextStyle: { color: "#8a9bb5" },
          axisLabel: { color: "#8a9bb5", formatter: "{value} °C" },
          splitLine: { lineStyle: { color: "#1a2d42", type: "dashed" } },
          // splitLine = 背景网格线，虚线，让图表更好读数
        },

        // Y 轴（垂直方向）= 城市名称
        yAxis: {
          type: "category",  // 类别轴
          data: cities,      // 城市名数组
          axisLabel: { color: "#8a9bb5", fontSize: 11 },
          axisLine: { lineStyle: { color: "#1e3a5f" } },
        },

        // 数据系列 = 真正要画的内容
        series: [
          {
            name: "年均温",
            type: "bar",         // bar = 条形图
            barMaxWidth: 26,     // 柱子最多 26px 宽，太多城市也不会挤
            data: temps.map(function (v) {
              // ↑ .map() = 把数组每个元素"映射"成新值
              //   比如 [12.5, 16.2] 变成 [{value:12.5, color:...}, {value:16.2, color:...}]
              return {
                value: v,  // 温度值
                itemStyle: {
                  // 根据温度给柱子不同颜色：
                  //   > 20°C → 红色（热）
                  //   10-20°C → 橙色（温）
                  //   < 10°C → 蓝色（凉）
                  color:
                    v > 20 ? "#d9534f" : v > 10 ? "#ffab40" : "#4fc3f7",
                },
              };
            }),
          },
        ],
      };

      // 11. 把配置应用到图表上（第二个参数 true = 不合并，完全替换旧配置）
      stateChart.setOption(option, true);
      // 12. 隐藏加载动画
      stateChart.hideLoading();
      // 13. 显示完成信息
      setMessage(
        stateMsgDom,
        "加载完成，共 " + data.count + " 个城市。",
        false
      );
    } catch (err) {
      // 14. 如果上面任何一步出错（网络断了、服务器报错等），走这里
      stateChart.hideLoading();  // 先隐藏加载动画
      setMessage(stateMsgDom, "加载失败：" + err.message, true);
      // err.message = 错误的具体描述，比如 "NetworkError" 或 "请求失败"
    }
  }

  // ──────────────────────────────────────────
  // 第三步：绑定事件——让按钮和下拉菜单能工作
  // ──────────────────────────────────────────

  // 点"刷新"按钮 → 重新加载数据
  reloadStateBtn.addEventListener("click", loadCityTemp);
  // addEventListener("click", fn) = "当用户点击这个按钮时，执行 fn 函数"

  // 切换国家 → 自动重新加载（不需要再点刷新）
  countrySelect.addEventListener("change", loadCityTemp);
  // "change" 事件在下拉菜单选项改变时触发

  // ──────────────────────────────────────────
  // 第四步：窗口大小变化时，图表也跟着缩放
  // ──────────────────────────────────────────
  window.addEventListener("resize", function () {
    // 先检查图表还存在且没有被销毁（切换页面时可能被销毁）
    if (stateChart && !stateChart.isDisposed()) {
      stateChart.resize();  // ECharts 内置方法：重新计算尺寸
    }
  });

  // ──────────────────────────────────────────
  // 第五步：页面加载完成后，立刻加载一次数据
  // ──────────────────────────────────────────
  loadCityTemp();
  // 不需要等用户操作，打开页面就能看到图表
})();
