# 肯葳科技亚马逊自动运营系统

> AI 驱动的亚马逊运营自动化平台 — 从数据采集到运营方案，一键生成。

---

## 功能亮点

| 功能 | 说明 |
|------|------|
| **自动采集** | 通过 Playwright 浏览器自动化，从 SellerSprite（卖家精灵）自动导出 6 种报表 |
| **智能分析** | 6000+ 关键词自动分类、竞品矩阵对比、关键词 Gap 分析、4 套定价模型 |
| **Excel 报表** | 8 个标签页的运营方案工作簿，含 Excel 公式、条件格式、可编辑单元格 |
| **网页仪表盘** | Next.js 14 交互式仪表盘，7 个数据标签页 + 控制中心 |
| **多产品管理** | 支持同时管理多个产品，一键切换，数据完全隔离 |
| **Docker 部署** | 一键容器化部署，跨平台运行（Mac / Windows / Linux） |

---

## 系统架构

```
Amazon 产品链接
       |
       v
  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
  │  产品发现    │────>│  数据采集    │────>│  数据处理    │
  │  Discovery   │     │  Collection  │     │  Processing  │
  └─────────────┘     └──────────────┘     └──────────────┘
       |                     |                     |
  自动识别竞品          SellerSprite x6        关键词分类
  生成种子词            Seller Central x4      竞品矩阵
  更新配置文件          下载到 inputs/          Gap 分析
                                               定价模型
                                               广告监测
                                               流量分析
                                                  |
                                                  v
                              ┌──────────────────────────────┐
                              │           输出               │
                              ├──────────────────────────────┤
                              │  Excel 运营方案 (.xlsx)      │
                              │  JSON 数据文件 (processed/)  │
                              │  网页仪表盘 (localhost:3000) │
                              │  运行摘要 (run_summary.md)   │
                              └──────────────────────────────┘
```

---

## 快速开始

### 方式一：Docker 部署（推荐）

> 适合所有用户，无需手动安装 Python 或 Node.js。

**前提条件**：安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
# 1. 克隆项目
git clone https://github.com/xiangyuzeng/ECOMMERCEAUTOMATION.git
cd ECOMMERCEAUTOMATION

# 2. 配置环境变量
cp .env.example .env
# 用文本编辑器打开 .env，填入你的 AdsPower API Key 和 Profile ID
# （详见下方"AdsPower 配置"章节）

# 3. 一键启动
# Mac / Linux:
chmod +x start.sh && ./start.sh

# Windows:
# 双击 start.bat 或在命令提示符中运行：
start.bat

# 4. 打开浏览器访问
# http://localhost:3000
```

### 方式二：本地运行

<details>
<summary><b>Mac 本地安装步骤</b>（点击展开）</summary>

```bash
# 1. 安装 Homebrew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装 Python 和 Node.js
brew install python@3.11 node@20

# 3. 克隆项目
git clone https://github.com/xiangyuzeng/ECOMMERCEAUTOMATION.git
cd ECOMMERCEAUTOMATION

# 4. 安装 Python 依赖
pip3 install -r requirements.txt --break-system-packages

# 5. 安装仪表盘依赖
cd dashboard && npm install && cd ..

# 6. 初始化目录结构
chmod +x setup.sh && ./setup.sh

# 7. 启动仪表盘
cd dashboard && npm run dev
# 打开 http://localhost:3000
```
</details>

<details>
<summary><b>Windows 本地安装步骤</b>（点击展开）</summary>

```cmd
:: 1. 安装 Python 3.11+
::    下载：https://www.python.org/downloads/
::    安装时勾选 "Add Python to PATH"

:: 2. 安装 Node.js 20+
::    下载：https://nodejs.org/

:: 3. 克隆项目
git clone https://github.com/xiangyuzeng/ECOMMERCEAUTOMATION.git
cd ECOMMERCEAUTOMATION

:: 4. 安装 Python 依赖
pip install -r requirements.txt

:: 5. 安装仪表盘依赖
cd dashboard && npm install && cd ..

:: 6. 启动仪表盘
cd dashboard && npm run dev
:: 打开 http://localhost:3000
```
</details>

---

## AdsPower 配置

系统使用 [AdsPower](https://www.adspower.com/) 进行浏览器自动化采集。配置步骤：

1. **安装 AdsPower** — 下载并安装 AdsPower 客户端
2. **获取 API Key** — 打开 AdsPower → 设置 → API → 复制 API Key
3. **获取 Profile ID** — 在浏览器配置列表中，找到目标配置文件的 ID
4. **登录 SellerSprite** — 在 AdsPower 浏览器中登录你的卖家精灵账号
5. **填入配置** — 将 API Key 和 Profile ID 填入 `.env` 文件：

```env
ADSPOWER_API_URL=http://localhost:50325
ADSPOWER_API_KEY=你的API密钥
ADSPOWER_PROFILE_ID=你的配置文件ID
```

> 如果不使用自动采集功能，可以手动下载数据文件放入 `inputs/` 目录。

---

## 使用流程

### 第一步：输入产品链接

在仪表盘控制中心输入 Amazon 产品链接，系统自动：
- 识别产品信息（标题、品牌、价格、评分）
- 发现竞品（自动搜索同类产品的前 4 名竞争对手）
- 生成种子关键词
- 更新配置文件

### 第二步：自动数据采集

系统通过 AdsPower 浏览器自动从 SellerSprite 采集：

| 数据类型 | 说明 | 用途 |
|----------|------|------|
| Reverse ASIN（反查 ASIN） | 每个 ASIN 的流量关键词 | 词库、Gap 分析 |
| Keyword Mining（关键词挖掘） | 种子词扩展 | 词库扩充 |
| Traffic Comparison（流量对比） | 多 ASIN 流量比较 | 流量分析 |
| Ads Insights（广告洞察） | 关键词广告位排名趋势 | 广告监测 |
| Competitor Research（竞品研究） | 竞品详细数据 | 竞品矩阵 |
| Keyword Research（关键词研究） | 类目热搜词 | 词库补充 |

### 第三步：查看运营方案

采集完成后，系统自动运行数据处理管道，生成：

**Excel 运营方案**（8 个标签页）：

| 标签页 | 内容 | 数据量 |
|--------|------|--------|
| 竞品分析 | 我的产品 + 4 个竞品的垂直对比矩阵 | 14 项指标 |
| 产品清单 | 4 套定价方案 + 变体销售数据 | Excel 公式 |
| 词库整理 | 全部关键词的分类、排名、搜索量 | 6000+ 行 |
| 广告指标监测 | Top 5 关键词的周度追踪热力图 | 12 周数据 |
| 定价策略 | 每个变体的成本分解和利润率 | 每 ASIN 1 行 |
| 流量入口 | 7 大流量渠道的策略建议 | 含具体关键词 |
| 关键词Gap分析 | MISSING/CATCHUP/DEFEND 三类差距词 | 按优先级排序 |
| 数据源日志 | 所有输入文件的审计追踪 | 自动生成 |

**网页仪表盘**（http://localhost:3000）：
- 7 个交互式数据标签页
- 实时采集进度监控
- 多产品切换
- 可编辑的成本字段

---

## 多产品管理

系统支持同时管理多个产品，数据完全隔离：

```
data/
  products.json              # 产品索引
  B094PZTFMB/                # 产品 A
    config.json              # 产品 A 的配置
    inputs/sellersprite/     # 产品 A 的采集数据
    processed/               # 产品 A 的 JSON 输出
    outputs/                 # 产品 A 的 Excel 报表
  B0BTRTZNS8/                # 产品 B
    ...
```

在仪表盘中点击产品选择器即可切换，无需重新采集。

---

## 项目结构

```
ECOMMERCEAUTOMATION/
├── Dockerfile                  # Docker 构建文件
├── docker-compose.yml          # Docker 编排配置
├── start.sh / start.bat        # 一键启动脚本（Mac / Windows）
├── .env.example                # 环境变量模板
├── config.json                 # 当前产品配置
├── config.example.json         # 配置文件模板
├── requirements.txt            # Python 依赖（pandas, openpyxl, playwright）
├── setup.sh                    # 目录初始化脚本
│
├── scripts/
│   ├── generate_report.py      # 数据处理管道入口
│   ├── config_manager.py       # 多产品配置管理
│   ├── parsers/                # 数据解析器
│   │   ├── sellersprite.py     #   SellerSprite .xlsx（6 种格式）
│   │   └── seller_central.py   #   Seller Central .csv（4 种格式）
│   ├── processors/             # 数据处理器
│   │   ├── keywords.py         #   关键词合并、去重、分类
│   │   ├── competitors.py      #   竞品对比矩阵
│   │   ├── gap_analysis.py     #   关键词 Gap 分析
│   │   ├── pricing.py          #   定价模型
│   │   ├── ads.py              #   广告指标监测
│   │   └── traffic.py          #   流量入口分析
│   ├── exporters/              # 数据导出器
│   │   ├── excel_writer.py     #   Excel 工作簿（8 标签页）
│   │   └── json_writer.py      #   JSON（供仪表盘使用）
│   └── collectors/             # 自动采集器
│       ├── collect.py          #   采集编排器
│       ├── sellersprite.py     #   SellerSprite 浏览器自动化
│       ├── seller_central.py   #   Seller Central 采集
│       └── product_discovery.py#   产品发现 + 竞品搜索
│
├── dashboard/                  # Next.js 14 网页仪表盘
│   ├── app/
│   │   ├── page.jsx            #   主界面（8 标签页）
│   │   ├── data.js             #   数据加载
│   │   └── api/                #   后端 API（11 个端点）
│   └── package.json
│
├── data/                       # 多产品数据存储
├── inputs/                     # 输入文件（兼容旧版单产品模式）
├── processed/                  # 处理后的 JSON 数据
├── outputs/                    # Excel 报表输出
├── logs/                       # 运行日志
│
└── wiki/
    └── 使用指南.md              # 完整使用手册（13 章）
```

---

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 数据处理 | Python 3.11, pandas, openpyxl | 解析、处理、导出 |
| 浏览器自动化 | Playwright + AdsPower | 自动数据采集 |
| 网页仪表盘 | Next.js 14, React 18, Recharts | 交互式数据展示 |
| 容器化 | Docker, docker-compose | 跨平台部署 |
| Excel 生成 | openpyxl | 8 标签页工作簿 + 公式 |

---

## 常见问题

<details>
<summary><b>Q: 不使用 AdsPower 可以运行吗？</b></summary>

可以。你可以手动从 SellerSprite 网站下载数据文件，放入 `inputs/sellersprite/` 目录，然后运行数据处理管道。详见 [INPUT_CHECKLIST.md](INPUT_CHECKLIST.md)。
</details>

<details>
<summary><b>Q: Docker 启动后无法访问 localhost:3000？</b></summary>

1. 确认 Docker Desktop 正在运行
2. 运行 `docker compose ps` 查看容器状态
3. 运行 `docker compose logs` 查看错误日志
4. 如果端口被占用：`lsof -ti:3000 | xargs kill` (Mac) 或 `netstat -ano | findstr :3000` (Windows)
</details>

<details>
<summary><b>Q: 采集过程中浏览器崩溃怎么办？</b></summary>

系统内置了自动恢复机制：
- 每个任务开始前会检测浏览器状态
- 浏览器崩溃后会尝试恢复页面
- 已采集的数据不会丢失
- 可以重新运行采集，系统会跳过已有数据
</details>

<details>
<summary><b>Q: 如何切换到其他产品？</b></summary>

在仪表盘控制中心输入新的 Amazon 产品链接，系统自动：
1. 归档旧产品数据
2. 发现新产品信息和竞品
3. 开始采集新产品数据

也可以在产品选择器中切换回之前的产品。
</details>

<details>
<summary><b>Q: 支持哪些 Amazon 站点？</b></summary>

当前版本支持 Amazon US（美国站）。其他站点（UK, DE, JP 等）计划在后续版本支持。
</details>

---

## 详细使用指南

完整的 13 章使用手册（含截图和详细步骤）：

**[wiki/使用指南.md](wiki/使用指南.md)**

包含：环境搭建（Mac/Windows）、AdsPower 配置、界面详解、多产品管理、Excel 报告使用、Docker 部署、故障排除等。

---

## 手动运行管道

如果不使用仪表盘，也可以通过命令行运行：

```bash
# 运行数据处理管道（读取 inputs/ 中的文件，生成报表）
python3 scripts/generate_report.py

# 指定产品 ID 运行（多产品模式）
python3 scripts/generate_report.py --product-id B094PZTFMB
```

---

## 许可证

本项目为 **肯葳科技** 内部工具。未经授权，请勿复制或分发。
