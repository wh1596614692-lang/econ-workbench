# 经纬 · 经济学实证分析工作台

本地运行的中文实证工作台：上传自己的 CSV / Excel / Stata 数据，检查与处理数据，估计模型，查看诊断，比较规格，导出可复现研究包。**网页中的所有结果均来自 Python 实际计算。** 不调用外部 AI、不需要密钥、不自动搜索显著规格。

## 快速启动

**要让别人通过链接使用：** 已提供 Render Docker 部署配置，见 [在线部署说明](docs/DEPLOYMENT.md)。需要云账号并确认托管费用；当前交付不代表已获得公网地址。

推荐 **Python 3.12**（验证环境：3.12.14）。交付包包含已构建的 `frontend/dist`，普通使用不需要 Node。

Windows：在项目文件夹打开 PowerShell，运行 `./start.ps1`。首次创建 `.venv` 并从 PyPI 安装锁定依赖。若系统策略不允许运行脚本，使用下方逐条命令，无需修改全局执行策略。

macOS / Linux：`sh start.sh`。

手动启动（Windows）：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
.\.venv\Scripts\python -m uvicorn econworkbench.api:app --host 127.0.0.1 --port 8000 --workers 1
```

访问 **http://127.0.0.1:8000**。API 文档在 `/docs`。停止服务后会话数据清除。不要使用 `--workers 2` 等多 worker 参数，因为此版本的会话存储是单进程内存。

Docker Compose（需 Docker Engine / Docker Desktop）：

```sh
docker compose up --build
# 访问 http://127.0.0.1:8000
docker compose down
```

Docker 配置已提供，但本次 Windows 环境无 Docker，因此未声称实际验证过容器构建。

## 一次完整分析

1. “数据”页上传文件；Excel 可切换工作表。中文/不安全列名会映射为英文名并显示原名。
2. 右侧确认截面/时间序列/面板。面板需 ID、时间和频率；点击“检查索引”查看重复键、缺口和平衡性。
3. 如需处理，点击“添加操作”。每次生成新版本；不覆盖原列；日志列明规则、阈值及受影响行数。
4. 选择 Y、X、控制变量和标准误；也可使用受限公式。点击“运行估计”。长任务可取消。
5. 查看系数、95% 区间、模型有效样本、诊断适用性。修改数据/设置后旧结果会显示旧配置提示。
6. 更名并改变规格即可保存稳健性模型。异质性在右侧选择分组。比较页可主动按共同样本重估。
7. “报告与导出”选择模型，下载 ZIP 或单独 HTML 报告。ZIP **包含用户主动导出的数据**。

示例入口全都标记为“合成演示数据”。`examples/generate.py` 使用固定种子 **20260924** 生成截面、月度时间序列、不平衡面板、共同政策 DID 和动态面板 GMM；`examples/configs.json` 提供对应配置。随机数只用于明确标注的示例生成，估计器不生成虚构统计结果。

## 统计实现

| 方法 | 实现与边界 |
| --- | --- |
| OLS | statsmodels；常规、HC1、HC3、单向聚类 CR1、规则时间序列 HAC；t/F 推断与修正写入结果 |
| 固定效应 | linearmodels PanelOLS；个体、时间、双向；支持不平衡；报告吸收项、自由度及多种 R² |
| DID | 共同政策时点、固定处理组、双向 FE；政策项、聚类 SE、事件研究和政策前 Wald 联合检验 |
| 系统 GMM | pydynpd 0.2.2；真正的差分＋水平方程系统，一/两步，内生/预定/外生分类，工具滞后范围、折叠和时间虚拟变量；两步 Windmeijer 修正；AR(1)/AR(2)/Hansen |

公式语法：`y ~ x1 + x2 + log(x3) + x1:x2`。支持 `sqrt(x)`、`square(x)`、`a*b`（展开主效应与交互项）、`+0`（不含截距）。仅安全变量名；自建白名单解析，不调用 `eval` 或用户可执行公式引擎。GMM 用专用表单。

处理支持显式删除/填补缺失、转数值、log、精确时间滞后/差分、中心化、标准化、交互、分位缩尾及条件筛选。季度/月度日期用 PeriodIndex；数值时间默认一步为 1，可手动调整。时间缺口不压缩。log 非正值变为缺失并记录；回归完整案例排除数会明确报告。

描述统计支持分组，Pearson/Spearman 使用成对有效 N；回归结果另提供模型有效样本统计。诊断按条件执行：原始/吸收后 VIF、时间序列 ADF/KPSS、OLS Koenker–BP、规则时间序列 BG。检验不会自动改变模型。

**尚未实现或受限**：分期 DID（检测到时阻止估计）、面板单位根、Difference-in-Hansen、wild-cluster bootstrap、多向聚类、FE 的 HC3/HAC、FE/DID/GMM 组间系数差异检验。只有两组 OLS 支持完整交互项的组间斜率联合检验。详见 [功能与限制](docs/FEATURES.md) 和 [统计口径](docs/METHODS.md)。

## 导出与复现

ZIP 包括 `results.xlsx`、CSV、LaTeX、HTML 报告、SVG 系数/事件/相关图、完整模型 JSON、列名映射、原始数据 JSON、处理配方、锁定依赖和实际统计核心代码。表格、报告和图形全部从同一保存结果对象产生。

解压导出包后：

```sh
python -m pip install -r requirements-lock.txt
python reproduce.py
```

脚本从原始数据逐步重放处理，重新估计，并逐项核对系数、标准误、p 值和 N（浮点容差 `rtol=1e-6, atol=1e-8`），保存 `reproduced_results.json`。HTML 可直接用浏览器打开/打印。LaTeX 中文表建议 XeLaTeX + ctex。CSV/Excel 危险字符串加单引号防止公式执行；复现使用未改变内容的 JSON。

## 开发与测试

React 19 + TypeScript 5.8 + Vite 6.4；Python FastAPI + pandas/NumPy/SciPy/statsmodels/linearmodels/pydynpd。前后端精确依赖见 `requirements-lock.txt` 与 `frontend/pnpm-lock.yaml`。Node 推荐 22+，pnpm 10.11+。

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm build
# 开发：pnpm dev；Vite /api 代理到 127.0.0.1:8000
```

在项目根目录、已安装依赖的 Python 环境中：

```sh
python -m pytest -q
```

测试覆盖独立 OLS 协方差计算、显式虚拟变量 FE 对照、两期 DID 差分均值、GMM 公开基准、ADF/KPSS/BP 统计量、缺失/共线性/重复索引/间隔/恶意公式、会话隔离、取消及“上传→变换→估计→检验→导出→独立脚本重现”。详细证据见 [验证记录](docs/VALIDATION.md)。

项目结构：`econworkbench/` 是 API 与共享统计核心，`frontend/` 是交互界面，`tests/` 是验证，`examples/` 是合成示例，`docs/` 是方法与限制。欢迎提交带最小复现数据的 bug；请不要公开私有数据。许可证为 MIT，第三方软件与基准来源见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 数据与运行边界

上传上限 20 MB，10 万行、150 列、200 万单元格；Excel 解压上限 100 MB。本地默认每会话最多 25 数据版本、30 任务、200 MB 原始和处理后 DataFrame 预算；全实例 DataFrame 预算 1200 MB；最多 12 个会话、2 个并发统计进程；任务超时 180 秒。GMM 限制 40 期、10 万行补齐网格和工具规模。在线部署使用更保守的可配置预算，见部署说明；结果、进程及解析器内存不包含在 DataFrame 预算内。

数据只在服务会话内存中保留；上传解析器可能使用操作系统临时文件，处理完成即关闭。会话随机 bearer token 隔离，闲置两小时自动清理，可主动清理；计算子进程可终止。上传内容不写到项目或日志，不覆盖用户文件。不依赖持久数据库。本地服务默认仅监听本机；分享版需采用部署说明中的服务器模式和托管 HTTPS。匿名链接分享没有账户认证；大范围公开或团队部署需另外配置访问规则和边缘限流。当前会话机制不是完整账户系统。
