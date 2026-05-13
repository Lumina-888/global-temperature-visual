# 全球气温变化可视化分析

## 项目目标
构建一个基于 FastAPI（后端）和 pyecharts（图表生成）的数据可视化大屏，通过对 Berkeley Earth 气温数据集的清洗与分析，从三个维度讲述全球变暖故事：**长期趋势**、**地区差异**、**季节性波动**。

### 技术栈
**后端框架**: **FastAPI**（Python 微框架，负责路由与数据接口）
**数据处理**: **Pandas**（用于处理 CSV、清洗缺失值及聚合计算）
**前端图表**: **ECharts**（通过 pyecharts 封装，支持动态交互与大屏布局）

### 数据集

| 数据集 | 关键字段 |
|---|---|
| **GlobalTemperatures.csv** | `dt`, `LandAverageTemperature`, `LandAverageTemperatureUncertainty`, `LandMaxTemperature`, `LandMaxTemperatureUncertainty`, `LandMinTemperature`, `LandMinTemperatureUncertainty`, `LandAndOceanAverageTemperature`, `LandAndOceanAverageTemperatureUncertainty` |
| **GlobalLandTemperaturesByCountry.csv** | `dt`, `AverageTemperature`, `AverageTemperatureUncertainty`, `Country` |
| **GlobalLandTemperaturesByState.csv** | `dt`, `AverageTemperature`, `AverageTemperatureUncertainty`, `State`, `Country` |
| **GlobalLandTemperaturesByMajorCity.csv** | `dt`, `AverageTemperature`, `AverageTemperatureUncertainty`, `City`, `Country`, `Latitude`, `Longitude` |
| **GlobalLandTemperaturesByCity.csv** | `dt`, `AverageTemperature`, `AverageTemperatureUncertainty`, `City`, `Country`, `Latitude`, `Longitude` |

字段说明：
- **Uncertainty**：测量不确定度，代表 95% 置信区间宽度，可用于在图表中绘制误差带
- **Latitude / Longitude**：可用于地理热力图和散点地图

### 数据处理流
```
源数据 CSV → data_engine.py（清洗、聚合、计算距平）→ FastAPI 路由 → JSON → 前端请求 → ECharts 渲染
```

---

## 数据大屏设计

大屏按 **顶部概览 → 中部双图 → 底部三图** 三层网格布局，所有图表共享时间范围筛选器，支持点击联动。

### 维度一：全球变暖趋势

| 图表 | 类型 | 数据源 | 说明 |
|---|---|---|---|
| **全球年均温变化（含不确定度）** | 折线图 + 置信带 | `GlobalTemperatures.csv` | X 轴为年份，Y 轴为 `LandAndOceanAverageTemperature`，叠加 95% 置信带（`Uncertainty` 字段）；叠加 10 年滑动平均线过滤短期波动 |
| **全球温度距平图** | 柱状图（红/蓝双色） | `GlobalTemperatures.csv` | 以 1951–1980 年为基准期，计算每年相对于基准均值的偏差；正值红色（偏暖），负值蓝色（偏冷），直观呈现"变暖"幅度 |
| **极值温度趋势** | 双折线图 | `GlobalTemperatures.csv` | 同时展示 `LandMaxTemperature` 和 `LandMinTemperature` 的年均值变化，比较最高温与最低温的上升速率是否一致 |

### 维度二：地区差异

| 图表 | 类型 | 数据源 | 说明 |
|---|---|---|---|
| **全球国家温度热力图** | 地图（choropleth） | `GlobalLandTemperaturesByCountry.csv` | 按国家填充颜色，颜色深浅表示年均温高低；支持年份滑块动画，逐年播放温度扩散过程 |
| **纬度带变暖速率对比** | 分组柱状图 | `GlobalLandTemperaturesByCity.csv` | 利用城市纬度字段，将城市分为热带（0°–23.5°）、温带（23.5°–66.5°）、寒带（66.5°–90°），对比各带的百年升温速率 |
| **重点城市温度排名** | 横向柱状图 | `GlobalLandTemperaturesByMajorCity.csv` | 展示选定年份内全球主要城市的年均温排名，可切换年份 |

### 维度三：季节性波动

| 图表 | 类型 | 数据源 | 说明 |
|---|---|---|---|
| **全球月均温季节周期** | 折线图 | `GlobalTemperatures.csv` | X 轴为 1–12 月，Y 轴为所有年份同月的平均温度，展示全球平均的季节温度变化模式 |
| **季节距平热力图** | 热力图（heatmap） | `GlobalTemperatures.csv` | X 轴为月份，Y 轴为年份，颜色表示当月温度与同月长期均值的偏差，一张图同时展示趋势 + 季节性 |
| **南北半球季节对比** | 双折线图 | `GlobalLandTemperaturesByCity.csv` | 按纬度区分南北半球城市，分别聚合月均温，展示南北半球相反的季节性模式 |

---

## API 设计

所有接口返回 JSON，格式为 `{"data": [...], "metadata": {...}}`。

| 路由 | 方法 | 说明 |
|---|---|---|
| `/` | GET | 大屏主页面 |
| `/api/global/annual` | GET | 全球年均温序列（含不确定度） |
| `/api/global/monthly` | GET | 全球月均温（用于季节周期） |
| `/api/global/anomaly` | GET | 全球温度距平数据 |
| `/api/country/annual` | GET | 按年份/国家聚合的年均温 |
| `/api/city/annual` | GET | 按年份/城市聚合的年均温 |
| `/api/city/latband` | GET | 按纬度带聚合的年均温序列 |

通用查询参数：`?start_year=1900&end_year=2020` 用于时间范围筛选。
