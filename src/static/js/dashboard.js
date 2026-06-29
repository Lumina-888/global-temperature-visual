/**
 * dashboard.js — 仪表板主控制器
 * =================================
 * 这个脚本是网站的核心大脑，管理页面上除了"城市温度排名"之外的所有图表。
 *
 * 它管的图表（共 5 个）：
 *   1. 全球温度多线对比  —— 一张图里画 4 条线（陆地最高/平均/最低 + 海陆综合）
 *   2. 温度距平柱状图    —— 每年比平均值高了多少或低了多少
 *   3. 月均温季节周期    —— 1~12 月各月平均温度
 *   4. 世界地图         —— 用颜色显示各国温度
 *   5. 纬度带温度对比    —— 热带 vs 温带 vs 寒带
 *
 * 启动流程（从下往上看也行）：
 *   页面加载完成 → 初始化 5 个图表实例 → 加载 GeoJSON 地图数据
 *   → 并行加载各个图表的数据 → 画图 → 绑定筛选器和 resize 事件
 */

(function () {
  "use strict";  // 严格模式：变量必须先声明再使用，避免低级错误

  // ═══════════════════════════════════════════
  // 一、调试工具 — 页面顶部的状态条
  // ═══════════════════════════════════════════

  // 找到调试栏的 DOM 元素
  const DBG = document.getElementById("debugBar");

  /**
   * 在调试栏和浏览器控制台同时输出信息
   * 就像汽车仪表盘，告诉你"引擎启动了"、"油加满了"之类的状态
   *
   * @param {string} msg   - 要显示的信息
   * @param {string} color - 可选，文字颜色（默认不变）
   */
  const dbg = (msg, color) => {
    if (DBG) DBG.textContent = "[Dashboard] " + msg;
    if (color && DBG) DBG.style.color = color;
    console.log("[Dashboard]", msg);  // 同时在浏览器控制台输出，方便调试
  };

  // ═══════════════════════════════════════════
  // 二、环境检查 — ECharts 库加载了吗？
  // ═══════════════════════════════════════════
  // 如果 CDN 挂了，echarts 变量就是 undefined，后面所有图表都画不了

  if (typeof echarts === "undefined") {
    dbg("FATAL: ECharts 库未加载！", "#d9534f");
    return;  // 直接退出，不继续执行后面的代码
  }
  dbg("ECharts v" + (echarts.version || "?") + " 就绪", "#ff9800");

  // ═══════════════════════════════════════════
  // 三、全局状态变量 — 记住"当前是什么状态"
  // ═══════════════════════════════════════════

  let startYear = 1900;            // 筛选的起始年份（默认 1900）
  let worldGeoJson = null;         // 世界地图的地理数据（GeoJSON 格式），加载后才赋值
  let mapYear = 2024;              // 地图当前显示的年份
  const countryDataCache = {};     // 国家温度数据缓存——年份作 key，避免重复请求
  let mapLoading = false;          // 地图是否正在加载中（防止用户快速拖滑块导致重复请求）

  // ═══════════════════════════════════════════
  // 四、工具函数 — 避免反复写一样的代码
  // ═══════════════════════════════════════════

  // 简写：$("xxx") = document.getElementById("xxx")，少打很多字
  const $ = (id) => document.getElementById(id);

  /**
   * 设置卡片底部的状态文字
   * @param {string} id   - 状态元素的 id（如 "statusGlobal"）
   * @param {string} text - 要显示的文字
   * @param {string} cls  - CSS 类名（"ok"=绿色, "error"=红色, "loading"=橙色）
   */
  const setStatus = (id, text, cls) => {
    const d = $(id);
    if (d) { d.textContent = text; d.className = "card-status " + (cls || ""); }
  };

  // 缓存 DOM 引用（从 HTML 里找到这些元素并记住，后面直接用变量名访问）
  const elStartYear = $("startYear");     // 起始年份输入框
  const elEndYear = $("endYear");         // 结束年份输入框
  const elApply = $("applyFilter");       // "应用筛选"按钮
  const elFilterMsg = $("filterMsg");     // 筛选结果消息
  const elMapSlider = $("mapYearInput");  // 地图年份滑块
  const elMapLabel = $("mapYearLabel");   // 地图年份标签

  // ═══════════════════════════════════════════
  // 五、图表实例变量 — 先声明，后面 initAllCharts() 里赋值
  // ═══════════════════════════════════════════
  // 5 个变量对应 5 个图表，初始都是 undefined
  let chartGlobal,    // 全球温度多线对比图
      chartAnomaly,    // 温度距平柱状图
      chartMonthly,    // 月均温季节周期图
      chartMap,        // 世界地图
      chartLatband,    // 纬度带温度对比图
      chartCity;       // 城市图表（已迁移到 city.js，这里不再使用）

  // ═══════════════════════════════════════════
  // 六、ECharts 通用配置 — 多个图表共用的颜色和样式
  // ═══════════════════════════════════════════

  // 图表背景色（和卡片背景一样，融为一体）
  const DARK_BG = "#152238";

  // X 轴的通用样式（所有图表的 X 轴看起来一样）
  const AXIS_COMMON = {
    type: "category",                          // 类别轴（不是数值轴）
    axisLabel: { color: "#8a9bb5" },           // 标签颜色
    axisLine: { lineStyle: { color: "#1e3a5f" } },  // 轴线颜色
    axisTick: { lineStyle: { color: "#1e3a5f" } },  // 刻度线颜色
  };

  /**
   * 创建一个 Y 轴配置（数值轴）
   * @param {string} name - 轴的名字，比如 "温度 (°C)"
   * @returns {object} ECharts 的 yAxis 配置对象
   */
  const valueAxis = (name) => ({
    type: "value",    // 数值轴（和 category 相对）
    name,              // ES6 简写：等于 name: name
    scale: true,       // 自动调整刻度范围，不强制从 0 开始
    nameTextStyle: { color: "#8a9bb5" },
    axisLabel: { color: "#8a9bb5", formatter: "{value} °C" },
    splitLine: { lineStyle: { color: "#1a2d42", type: "dashed" } },
    // splitLine = 背景横向网格线，虚线，帮助人眼对齐数值
  });

  // 加载动画的配置（统一的转圈圈样式）
  const loadingOpts = {
    text: "加载中...",
    color: "#4fc3f7",
    textColor: "#c8d6e5",
    maskColor: "rgba(15,25,35,0.8)",  // 半透明遮罩
  };

  // ═══════════════════════════════════════════
  // 七、国家名映射 — 数据里的名字 ≠ 地图文件里的名字
  // ═══════════════════════════════════════════
  // 比如数据里叫 "United States"，地图文件里叫 "United States of America"
  // 不映射的话，地图上找不到这个国家，颜色就显示不出来

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

  /**
   * 把数据集里的国家名转成 GeoJSON 地图文件里的国家名
   * 如果映射表里有就用映射后的，没有就直接用原名
   */
  const mapToGeoJsonName = (n) => COUNTRY_NAME_MAP[n] || n;

  // ═══════════════════════════════════════════
  // 八、加载世界地图数据（GeoJSON）
  // ═══════════════════════════════════════════
  // GeoJSON 是一种地理数据格式，描述了每个国家的边界形状
  // 有了它，ECharts 才能画出地图

  const loadWorldGeoJson = () => {
    dbg("加载世界地图 GeoJSON...");
    setStatus("statusMap", "正在加载地图数据...", "loading");

    // 两个数据源：先试本地文件，失败了再用 GitHub 上的备用地址
    const urls = [
      "/static/data/world.geo.json",                                      // 本地（快）
      "https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json",  // 远程备用
    ];

    /**
     * 递归尝试加载：先试第 idx 个 URL，失败就试下一个
     * 就像钥匙串——第一把打不开就换下一把
     */
    const tryUrl = (idx) => {
      if (idx >= urls.length) return Promise.reject(new Error("所有数据源失败"));
      dbg("尝试: " + urls[idx]);
      return fetch(urls[idx])
        .then(r => {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();  // 把响应体解析成 JSON 对象
        })
        .catch(() => tryUrl(idx + 1));  // 失败 → 试下一个 URL
    };

    return tryUrl(0).then(geo => {
      worldGeoJson = geo;  // 保存到全局变量
      dbg("GeoJSON 就绪 (" + (geo.features || []).length + " 个区域)");
      // ↑ geo.features 是数组，每个元素是一个国家的地理信息
      echarts.registerMap("world", geo);
      // ↑ 把地图数据注册到 ECharts，名字叫 "world"，后面画地图时引用这个名字
      setStatus("statusMap", "地图数据就绪", "ok");
    });
  };

  // ═══════════════════════════════════════════
  // 九、初始化所有图表实例
  // ═══════════════════════════════════════════
  // 每个图表需要一个容器（HTML 里的 div）和一个 ECharts 实例
  // 这一步 = 给每个 div 分配一个"画师"

  const initAllCharts = () => {
    // 容器列表：[容器 id, 用于调试的名称]
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
        // echarts.init(容器元素, 主题, 额外配置)
        // devicePixelRatio: 2 = 高清渲染
        results.push(echarts.init($(id), null, { devicePixelRatio: 2 }));
        dbg("✓ " + name);
      } catch (e) {
        results.push(null);  // 初始化失败就存 null，后面判断跳过
        dbg("✗ " + name + ": " + e.message, "#d9534f");
      }
    });

    // 按顺序拆包：把结果数组的元素一一赋给 5 个变量
    [chartGlobal, chartAnomaly, chartMonthly, chartMap, chartLatband] = results;
    dbg(results.filter(Boolean).length + "/5 图表实例已创建", "#81c784");
    //   ↑ .filter(Boolean) = 去掉 null/undefined，只留成功创建的
  };

  // ═══════════════════════════════════════════
  // 十、图表 1 — 全球温度多线对比
  // ═══════════════════════════════════════════
  // 一张图里画 4 条线：
  //   红线 = 陆地平均温（最粗）
  //   蓝线 = 海陆综合温（带半透明填充）
  //   红虚线 = 陆地最高温
  //   蓝虚线 = 陆地最低温

  const loadGlobalAnnual = () => {
    if (!chartGlobal) return;  // 图表没创建成功就跳过
    setStatus("statusGlobal", "正在加载...", "loading");
    chartGlobal.showLoading(loadingOpts);  // 显示转圈圈

    // 请求后端 API：只获取 startYear 之后的数据
    fetch("/api/global/annual?min_year=" + startYear)
      .then(r => r.json())
      .then(d => {
        dbg("全球年均温: " + d.count + " 条记录");

        // 动态更新结束年份输入框（用数据里最新的年份）
        if (d.years && d.years.length > 0) {
          const maxYr = d.years[d.years.length - 1];
          if (elEndYear) elEndYear.value = maxYr;
        }

        // 配置图表（setOption = 告诉 ECharts 画什么、怎么画）
        chartGlobal.setOption({
          backgroundColor: DARK_BG,

          title: {
            text: "全球温度变化趋势",
            left: "center",
            textStyle: { color: "#e0e0e0", fontSize: 16, fontWeight: "bold" }
          },

          // 鼠标悬停提示框
          tooltip: {
            trigger: "axis",  // 显示该 X 坐标上所有线的值
            backgroundColor: "rgba(21,34,56,0.95)",
            borderColor: "#1e3a5f",
            formatter: params => {
              // params = 当前鼠标位置对应的所有数据点的数组
              let s = "<b>" + params[0].axisValue + " 年</b><br/>";
              params.forEach(p => {
                if (p.value != null)
                  s += p.marker + " " + p.seriesName + ": <b>" + p.value.toFixed(2) + " °C</b><br/>";
                // p.marker = 图例的小圆点或方块
                // p.seriesName = 这条线的名字（如 "陆地平均温"）
              });
              return s;
            },
          },

          legend: { bottom: 4, textStyle: { color: "#8a9bb5", fontSize: 11 } },
          // ↑ 图例放在底部，比如"─ 陆地平均温  ─ 海陆综合温"

          grid: { left: 60, right: 30, top: 55, bottom: 45 },
          // ↑ grid = 图表绘图区的边距，防止文字被切掉

          xAxis: [{ ...AXIS_COMMON, data: d.years }],
          // ↑ 展开运算符 ... = 把 AXIS_COMMON 的所有属性复制过来，再添加 data

          yAxis: [valueAxis("温度 (°C)")],

          dataZoom: [
            { type: "inside" },  // 鼠标滚轮缩放 + 拖拽平移
            { type: "slider", bottom: 20, height: 18, textStyle: { color: "#8a9bb5" } },
            // ↑ 底部的滑动缩放条
          ],

          // series = 真正要画的数据系列，每个对象 = 一条线
          series: [
            {
              name: "陆地最高温",
              type: "line",
              data: d.land_max,
              smooth: true,    // 平滑曲线（不是折线）
              symbol: "none",  // 不显示数据点的小圆点
              lineStyle: { color: "#ef9a9a", width: 1.5, type: "dashed" },
              // dashed = 虚线
            },
            {
              name: "陆地平均温",
              type: "line",
              data: d.land_avg,
              smooth: true,
              symbol: "none",
              lineStyle: { color: "#ef5350", width: 2.5 },  // 红色实线，最粗
            },
            {
              name: "海陆综合温",
              type: "line",
              data: d.land_ocean_avg,
              smooth: true,
              symbol: "none",
              lineStyle: { color: "#42a5f5", width: 2.5 },  // 蓝色实线
              areaStyle: {
                // 折线下方填充半透明蓝色渐变——从有线到无线
                color: {
                  type: "linear", x: 0, y: 0, x2: 0, y2: 1,
                  colorStops: [
                    { offset: 0, color: "rgba(66,165,245,0.1)" },  // 顶部：浅蓝
                    { offset: 1, color: "rgba(66,165,245,0.0)" },  // 底部：完全透明
                  ],
                },
              },
            },
            {
              name: "陆地最低温",
              type: "line",
              data: d.land_min,
              smooth: true,
              symbol: "none",
              lineStyle: { color: "#90caf9", width: 1.5, type: "dashed" },
            },
          ],
        }, true);  // 第二个参数 true = 不合并旧配置，完全替换

        chartGlobal.hideLoading();  // 隐藏转圈圈
        setStatus("statusGlobal", "加载完成（" + d.count + " 年）", "ok");
      })
      .catch(err => {
        // 网络错误或数据解析错误走这里
        chartGlobal.hideLoading();
        setStatus("statusGlobal", "加载失败: " + err.message, "error");
      });
  };

  // ═══════════════════════════════════════════
  // 十一、图表 2 — 温度距平柱状图
  // ═══════════════════════════════════════════
  // "距平" = 偏离平均值的程度
  // 比如年均温 15°C，今年 16°C → 距平 +1°C（比平均高 1°C）
  // 红色柱子 = 比平均高（偏暖年份），蓝色柱子 = 比平均低（偏冷年份）

  const loadAnomaly = () => {
    if (!chartAnomaly) return;
    setStatus("statusAnomaly", "正在加载...", "loading");
    chartAnomaly.showLoading(loadingOpts);

    fetch("/api/global/anomaly")
      .then(r => r.json())
      .then(d => {
        dbg("距平数据: 基准均值 " + d.baseline_avg + "°C");
        // 基准均值 = 某个时间段（如 1951-1980）的全球平均温度

        // 找到起始年份在年份数组中的位置，截取对应的数据
        const idx = Math.max(0, d.years.indexOf(startYear));
        const years = d.years.slice(idx);        // 从起始年份开始截取
        const anomalies = d.anomalies.slice(idx); // 对应的距平值也同步截取

        chartAnomaly.setOption({
          backgroundColor: DARK_BG,
          title: {
            text: "全球温度距平（基准: " + d.baseline_start + "-" + d.baseline_end + "）",
            left: "center",
            textStyle: { color: "#c8d6e5", fontSize: 15 },
          },
          tooltip: {
            trigger: "axis",
            formatter: p =>
              p[0].axisValue + " 年<br/>距平: " +
              (p[0].value >= 0 ? "+" : "") + p[0].value.toFixed(2) + " °C",
            // 大于等于 0 就加个 + 号：比如 "+1.23 °C"
          },
          grid: { left: 55, right: 20, top: 50, bottom: 40 },
          xAxis: [{ ...AXIS_COMMON, data: years }],
          yAxis: [valueAxis("距平 (°C)")],
          series: [{
            type: "bar",  // 柱状图
            data: anomalies.map(v => ({
              value: v,
              itemStyle: {
                // 每个柱子独立着色：正距平 = 红（暖年），负距平 = 蓝（冷年）
                color: v >= 0 ? "#d9534f" : "#4fc3f7",
              },
            })),
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

  // ═══════════════════════════════════════════
  // 十二、图表 3 — 月均温季节周期
  // ═══════════════════════════════════════════
  // 把多年数据按月份取平均，展示"全年温度曲线"
  // 通常呈 U 形或倒 U 形：夏天高、冬天低
  // 水平虚线 = 年均温线，用来直观看出哪几个月高于/低于平均

  const loadMonthly = () => {
    if (!chartMonthly) return;
    setStatus("statusMonthly", "正在加载...", "loading");
    chartMonthly.showLoading(loadingOpts);

    const MONTHS = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];

    fetch("/api/global/monthly")
      .then(r => r.json())
      .then(d => {
        // 过滤掉 null 值（某个月份可能缺数据）
        const valid = d.temps.filter(t => t != null);
        // 计算有效月份的平均温度——用来画参考线
        const avgTemp = valid.length > 0
          ? +(valid.reduce((a, b) => a + b, 0) / valid.length).toFixed(1)
          : 0;
        // reduce((a,b) => a+b, 0) = 累加求和
        // .toFixed(1) = 保留 1 位小数，+号转回数字

        dbg("月均温: " + valid.length + "/12 月有效");

        chartMonthly.setOption({
          backgroundColor: DARK_BG,
          title: {
            text: "全球月均温季节周期（多年平均）",
            left: "center",
            textStyle: { color: "#c8d6e5", fontSize: 15 },
          },
          tooltip: {
            trigger: "axis",
            formatter: p =>
              MONTHS[p[0].dataIndex] + " 均温: " +
              (p[0].value != null ? p[0].value.toFixed(1) + " °C" : "无数据"),
          },
          grid: { left: 55, right: 20, top: 50, bottom: 30 },
          xAxis: [{ ...AXIS_COMMON, data: MONTHS }],
          yAxis: [valueAxis("温度 (°C)")],
          series: [{
            type: "line",
            data: d.temps,
            smooth: true,           // 平滑曲线
            connectNulls: true,     // 如果中间有 null，跳过它，把前后连起来
            symbol: "circle",       // 数据点的形状
            symbolSize: 6,          // 数据点的大小
            lineStyle: { color: "#81c784", width: 2 },
            areaStyle: { color: "rgba(129,199,132,0.15)" },  // 曲线下方淡绿色填充
            markLine: {
              // 标记线 = 在图表上画参考线
              silent: true,  // 不响应鼠标事件
              data: [{
                yAxis: avgTemp,
                name: "年均",
                label: { formatter: "年均\n{c}°C", color: "#ff9800" },
                // \n = 换行，{c} = 该线的 Y 值（年均温）
              }],
              lineStyle: { color: "#ff9800", type: "dashed", width: 1.5 },
              symbol: "none",  // 线两端不显示箭头或圆点
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

  // ═══════════════════════════════════════════
  // 十三、图表 4 — 世界地图
  // ═══════════════════════════════════════════
  // 用颜色深浅表示各国温度
  // 分两步：先加载数据（loadMapData），再渲染（renderMap）
  // 带缓存：同一个年份的数据只请求一次

  /**
   * 加载某一年各国温度数据
   * @param {number}   year     - 年份
   * @param {function} callback - 数据加载完成后的回调函数
   */
  const loadMapData = (year, callback) => {
    // 先看缓存里有没有——有就直接用，不发网络请求
    if (countryDataCache[year]) {
      callback(countryDataCache[year]);
      return;
    }

    dbg("请求国家数据 (year=" + year + ")");
    fetch("/api/country/annual?year=" + year)
      .then(r => r.json())
      .then(d => {
        // 把国家名映射成 GeoJSON 的名字，然后打包成 [{name, value}, ...]
        const data = d.countries.map((c, i) => ({
          name: mapToGeoJsonName(c),  // 映射后的国家名
          value: d.temps[i],           // 对应的温度值
        }));
        dbg("国家数据就绪: " + d.count + " 国 (year=" + year + ")");
        countryDataCache[year] = data;  // 存入缓存
        callback(data);                  // 通知"数据好了，可以画了"
      })
      .catch(err => {
        dbg("ERROR: 国家数据加载失败 " + err.message, "#d9534f");
        callback([]);  // 失败时传空数组，地图显示"无数据"
      });
  };

  /**
   * 在地图上渲染数据
   * @param {number} year - 年份
   * @param {Array}  data - [{name: "China", value: 12.5}, ...]
   */
  const renderMap = (year, data) => {
    if (!chartMap) return;
    dbg("渲染地图: " + year + " 年, " + data.length + " 个数据点");

    chartMap.setOption({
      backgroundColor: DARK_BG,
      title: {
        text: year + " 年全球各国平均温度",
        left: "center",
        textStyle: { color: "#c8d6e5", fontSize: 15 },
      },
      tooltip: {
        trigger: "item",  // 鼠标移到哪个国家就显示哪个国家的数据
        formatter: p =>
          p.name + "<br/>年均温: " +
          (p.value != null ? p.value.toFixed(1) + " °C" : "无数据"),
      },
      visualMap: {
        // visualMap = 视觉映射：把数值(-10~30)映射到颜色(蓝→绿→黄→橙→红)
        min: -10,
        max: 30,
        inRange: {
          color: ["#4fc3f7", "#e8f5e9", "#fff176", "#ffab40", "#d9534f"],
          //        冷(蓝)  →  凉(浅绿) → 温(黄) →  热(橙)  → 极热(红)
        },
        text: ["30°C", "-10°C"],  // 图例两端的标签
        textStyle: { color: "#8a9bb5" },
        left: 8,
        bottom: 16,
      },
      geo: {
        // geo = 地理坐标系配置
        map: "world",       // 引用之前注册的地图数据
        roam: true,          // 允许鼠标缩放和拖拽
        zoom: 1.15,          // 初始缩放比例（>1 = 放大了看）
        center: [15, 10],    // 地图中心点（经度, 纬度），让中国在中间
        itemStyle: {
          areaColor: "#1a2d42",       // 没数据的国家 = 深灰蓝
          borderColor: "#2a4a6b",     // 国界线颜色
          borderWidth: 0.5,
        },
        emphasis: {
          // 鼠标悬停时的样式
          label: { show: false },          // 不显示国家名
          itemStyle: { areaColor: "#3a5a7b" },  // 变亮
        },
      },
      series: [{
        type: "map",
        map: "world",
        geoIndex: 0,  // 使用上面定义的 geo 配置
        data,          // 国家温度数据
      }],
    }, true);

    setStatus("statusMap", "加载完成（" + year + " 年, " + data.length + " 国）", "ok");
  };

  /**
   * 更新地图到指定年份（外部调用的入口）
   * @param {number} year - 目标年份
   */
  const updateMap = (year) => {
    if (mapLoading) return;  // 正在加载中，别重复请求
    mapYear = year;
    elMapLabel.textContent = year;  // 更新滑块旁边的年份数字

    if (!worldGeoJson) {
      // 地图数据还没加载完（比如 GeoJSON 还在下载）
      setStatus("statusMap", "等待地图数据...", "loading");
      return;
    }

    mapLoading = true;  // 上锁
    setStatus("statusMap", "正在加载 " + year + " 年数据...", "loading");
    loadMapData(year, data => {
      renderMap(year, data);
      mapLoading = false;  // 解锁
    });
  };

  /**
   * 初始化地图模块：绑定滑块事件 + 首次加载
   */
  const initMap = () => {
    dbg("初始化地图模块");
    updateMap(mapYear);  // 默认显示 2024 年
    // 当用户拖动滑块时，更新地图
    elMapSlider.addEventListener("change", () =>
      updateMap(parseInt(elMapSlider.value, 10))
    );
    // parseInt(x, 10) = 把字符串 "2024" 转成数字 2024（10 表示十进制）
  };

  // ═══════════════════════════════════════════
  // 十四、图表 5 — 纬度带温度对比
  // ═══════════════════════════════════════════
  // 把地球按纬度切成三块，对比温度变化趋势：
  //   热带（赤道附近）→ 红线
  //   温带（中纬度）  → 绿线
  //   寒带（极地）    → 蓝线

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
          title: {
            text: "纬度带温度变化趋势对比",
            left: "center",
            textStyle: { color: "#c8d6e5", fontSize: 15 },
          },
          tooltip: {
            trigger: "axis",
            formatter: params => {
              let s = params[0].axisValue + " 年<br/>";
              params.forEach(p => {
                if (p.value != null)
                  s += p.marker + " " + p.seriesName + ": " + p.value.toFixed(1) + " °C<br/>";
              });
              return s;
            },
          },
          legend: { bottom: 0, textStyle: { color: "#8a9bb5" } },
          grid: { left: 55, right: 20, top: 50, bottom: 40 },
          xAxis: [{ ...AXIS_COMMON, data: d.years }],
          yAxis: [valueAxis("温度 (°C)")],
          series: [
            {
              name: d.tropical_label || "热带",
              type: "line", data: d.tropical,
              smooth: true, symbol: "none",
              lineStyle: { color: "#d9534f", width: 2 },  // 红色
            },
            {
              name: d.temperate_label || "温带",
              type: "line", data: d.temperate,
              smooth: true, symbol: "none",
              lineStyle: { color: "#81c784", width: 2 },  // 绿色
            },
            {
              name: d.polar_label || "寒带",
              type: "line", data: d.polar,
              smooth: true, symbol: "none",
              lineStyle: { color: "#4fc3f7", width: 2 },  // 蓝色
            },
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

  // ═══════════════════════════════════════════
  // 十五、全局筛选 — 用户修改年份范围时触发
  // ═══════════════════════════════════════════

  const applyGlobalFilter = () => {
    // 读取输入框的值并转成数字
    const s = parseInt(elStartYear.value, 10);  // 起始年份
    const e = parseInt(elEndYear.value, 10);    // 结束年份

    // 输入校验：不是数字，或起始 ≥ 结束 → 报错
    if (isNaN(s) || isNaN(e) || s >= e) {
      elFilterMsg.textContent = "请输入有效年份范围（起始 < 结束）";
      return;
    }

    startYear = s;  // 更新全局起始年份
    elFilterMsg.textContent = "已更新: " + s + "–" + e;
    dbg("全局筛选: " + s + "–" + e);

    // 重新加载受筛选影响的图表（月均温和世界地图不受影响，不需要重载）
    loadGlobalAnnual();
    loadAnomaly();
    loadLatband();
  };

  // ═══════════════════════════════════════════
  // 十六、窗口大小变化时的处理
  // ═══════════════════════════════════════════
  // 用户缩放浏览器窗口 → 图表也要跟着缩放，否则会变形

  window.addEventListener("resize", () => {
    [chartGlobal, chartAnomaly, chartMonthly, chartMap, chartLatband, chartCity]
      .forEach(c => {
        try {
          if (c) c.resize();  // ECharts 的 resize 方法
        } catch (e) {
          /* 忽略 resize 时的偶发错误（比如正在切换页面） */
        }
      });
  });

  // ═══════════════════════════════════════════
  // 十七、总启动函数 — 一切从这里开始
  // ═══════════════════════════════════════════

  const start = () => {
    dbg("══════ 启动仪表板 ══════", "#4fc3f7");

    // 1. 初始化所有图表实例
    initAllCharts();

    // 2. 检查是否所有图表都失败了（容器不存在等情况）
    if (!chartGlobal && !chartAnomaly && !chartMonthly && !chartLatband && !chartCity) {
      dbg("FATAL: 所有图表容器初始化失败", "#d9534f");
      return;
    }

    // 3. 绑定"应用筛选"按钮的点击事件
    elApply.addEventListener("click", applyGlobalFilter);

    // 4. 立即加载不需要地图的图表数据（并行发起请求）
    loadGlobalAnnual();  // 多线对比图
    loadAnomaly();       // 距平图
    loadMonthly();       // 月均温图
    loadLatband();       // 纬度带图

    // 5. 加载地图数据（GeoJSON），成功后初始化地图
    //    地图依赖 GeoJSON，所以要等它加载完
    loadWorldGeoJson()
      .then(() => initMap())  // GeoJSON 就绪 → 初始化地图模块
      .catch(err => {
        // 地图加载失败：显示错误提示，但不影响其他图表
        dbg("地图模块失败: " + err.message, "#d9534f");
        setStatus("statusMap", "地图不可用", "error");
        if (chartMap) {
          chartMap.setOption({
            backgroundColor: DARK_BG,
            title: {
              text: "地图加载失败\n请检查网络连接",
              left: "center", top: "center",
              textStyle: { color: "#d9534f", fontSize: 14 },
            },
          });
        }
      });
  };

  // ═══════════════════════════════════════════
  // 十八、真正的入口 — 页面就绪后启动
  // ═══════════════════════════════════════════
  // document.readyState = 页面加载状态
  //   "complete" = HTML 和所有资源（图片、CSS）都加载完了
  // 延迟 100ms 再启动，确保 CSS 布局已计算完毕（否则图表容器尺寸可能为 0）

  if (document.readyState === "complete") {
    setTimeout(start, 100);
  } else {
    window.addEventListener("load", () => setTimeout(start, 100));
  }
})();
