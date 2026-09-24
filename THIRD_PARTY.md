# 第三方依赖与数据来源

项目自身代码采用 MIT。第三方软件按各自许可证分发，不将其声明为本项目作者原创。精确版本由 Python 和前端锁文件记录；部署依赖从标准包仓库安装。完整安装元数据摘要见 `docs/dependency-licenses.json`。

| 依赖 | 用途 | 许可证 |
| --- | --- | --- |
| FastAPI、Pydantic、Uvicorn | API / 配置 / 服务器 | MIT / MIT / BSD-3-Clause |
| Starlette、HTTPX、AnyIO | ASGI、HTTP 与测试基础 | BSD-3-Clause / BSD-3-Clause / MIT |
| python-multipart | 上传解析 | Apache-2.0 |
| NumPy、pandas、SciPy、statsmodels | 数据与统计 | BSD-3-Clause（含各包第三方组件声明） |
| linearmodels | 面板估计 | NCSA |
| pydynpd | 动态面板系统 GMM | MIT |
| pyhdfe | 固定效应吸收后诊断 | MIT |
| openpyxl | Excel 读取/结果工作簿 | MIT |
| matplotlib | 可扩展绘图依赖 | PSF-based；本版默认直接生成 SVG |
| pytest | 验证 | MIT |
| React、React DOM、Vite、TypeScript | 浏览器工作台与构建 | MIT / MIT / MIT / Apache-2.0 |
| lucide-react | 界面图标 | ISC（源图形亦可能包含 MIT 许可部分） |

## 示例和基准

`examples/synthetic_*` 均由项目提供的生成器生成，固定种子 20260924，属于**合成演示数据**，不代表真实经济对象。

`tests/fixtures/arellano_bond.csv` 是用于数值验证的公开 Arellano–Bond 数据副本，不是合成演示数据，也不在网页的示例入口中混用：

- 来源：<https://github.com/dazhwu/pydynpd/blob/main/data.csv>
- 下载时 Git blob SHA：`d7a53168e2846fefb2c1568fd502922cf9c59f93`。
- 上游仓库采用 MIT，原许可证保存为 `tests/fixtures/PYDYNPD_LICENSE`。
- 数值对照：<https://github.com/dazhwu/pydynpd/blob/main/Benchmark/test_2.md> 中的系统 GMM / R panelvar 表，以及 pydynpd README/API 的详细数值。
- 原始研究：Arellano, M. & Bond, S. (1991), *Some Tests of Specification for Panel Data*, Review of Economic Studies 58(2), 277–297。
- 软件论文：Wu et al. (2023), *pydynpd: A Python package for dynamic panel model*, JOSS 8(83), 4416, <https://doi.org/10.21105/joss.04416>。

上游 `test_2.md` 的末尾 xtabond2 代码片段实际包含 `nolevel`，属于差分 GMM；本项目**未将那段输出冒称为系统 GMM 对照**。当前独立软件数值对照使用同页 R panelvar 的系统 GMM 结果，按其显示精度设置容差；没有声称本机安装或运行过 Stata/R。
