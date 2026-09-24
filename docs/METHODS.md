# 统计计算口径

## OLS

估计器为 statsmodels `OLS`，默认含常数。先删除当前设计矩阵、Y 或聚类变量的缺失/无穷值（仅模型临时样本，不修改数据版本），明确报告排除数。完全共线拒绝估计。常规方差用 SSE/(n−k)；HC1 采用 n/(n−k)，HC3 用杠杆值修正。均显式设置 `use_t=True`，常规/HC/HAC 的 t 自由度为 n−k。

单向聚类启用 `use_correction` 与 `df_correction`，方差修正 G/(G−1)·(n−1)/(n−k)，推断自由度 G−1；少于 30 簇提示有限样本风险。HAC 使用 Bartlett 核、指定带宽和 n/(n−k) 修正，仅适用于按时间排序的单条规则时间序列；完整案例删除后出现缺口则拒绝 HAC。

整体检验为除常数外斜率联合为零，用与系数一致的协方差口径。相关性、统计显著性和因果识别分别解释。参考：[statsmodels 协方差文档](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.get_robustcov_results.html)。

## 固定效应

使用 `PanelOLS`，不以混合 OLS 代替，也不手写仅适于平衡面板的双向去均值。实体/时间索引唯一。`drop_absorbed=True`，吸收变量名单和库警告写入结果；其他共线性报错。保留 singleton 观测，未声称提供 singleton 稳健推断修正。

启用 `debiased=True, auto_df=True`。单向聚类用 `group_debias=True`。效应自由度由 linearmodels 按协方差及嵌套规则决定；FE 的 t/F 自由度是结果对象 `df_resid`，**不是 OLS 聚类中的 G−1**。若需要其他软件的特定有限样本口径，应在独立软件复核并显式比较设置。

主 R² 为吸收所设效应后的拟合口径，同时保存 within、between、overall、inclusive；这些值含义不同。调整 R² 仅为 OLS 提供。VIF 分原始设计矩阵与 pyhdfe 迭代投影吸收效应后的设计矩阵。不会按 VIF 自动删变量。

参考：[PanelOLS.fit](https://bashtage.github.io/linearmodels/panel/panel/linearmodels.panel.model.PanelOLS.fit.html)。

## 共同政策时点 DID

`treated` 必须是个体内固定的 0/1 分组，同时有处理、对照组以及两组政策前后观测。用户提供共同政策时点或对所有组一致的 post。post 须按时间单次从 0 转 1。同一期 post 不一致或 treated 随时间变化会拒绝估计。**如果用户错误地把真实分期政策强行编码成同一个共同时点，单凭这两列无法识别这个编码错误；必须由研究者确认政策设计。**

自动构造 `DID_effect = treated × post`，使用双向 FE，控制变量由用户明确指定。事件研究在至少两个政策前期和两个政策后期时运行，默认相对期 −1 为基准。窗口之外合并到两端，不丢掉尾部后隐含基准；置信区间是逐点 95%，非同时置信带。政策前系数联合检验采用当前聚类/稳健协方差的 Wald χ²。未拒绝不能证明平行趋势。

分期 DID、预期/溢出修正、合成控制尚未实现。

## 系统 GMM

使用经过公开比较的 **pydynpd 0.2.2**；构造标准 dynamic-panel 命令，明确使用默认的 levels 方程，绝不加入 `nolevel`，不启用 `?` 搜索。用户输入不进入命令解析，实际列被内部别名 a0、a1…替换。

Y 的滞后 1…p 进入方程；Y 和内生变量的差分方程工具最早为 t−2，预定变量最早为 t−1，严格外生变量使用 IV-style 工具。levels 矩由库生成。滞后范围固定有界，可折叠；默认两步、Windmeijer (2005) 稳健方差修正；一步提供库的一步稳健标准误。z/正态推断。

已审计的库行为及适配：

- 库按类别编码时间。工作台先补齐 ID×真实时期网格，再排序，保留缺口，防止所有个体缺少某一年时把它压缩。
- 如果完整缺失期导致库自动添加的时间虚拟变量不可识别，拒绝并说明取消时间虚拟变量/缩小时间范围；不偷偷删时期。
- `num_obs` 来自可用**差分方程**观测数。描述统计使用输入历史样本，GMM 不虚构一个统一的有效行集合，故不开放共同样本重估。
- 库在一步模式也计算第二步，并在第二步执行 Hansen/AR 检验。报告对此明确标注，不能将这些检验描述成一步残差检验。
- 不提供 Difference-in-Hansen；不将 Sargan 与 Hansen 混称。无过度识别自由度时报告条件不足。
- 提示工具数相对个体数、少个体、长面板、弱工具及额外水平方程矩条件风险；不以 Hansen p>0.05 证明工具有效。

参考：[pydynpd 源码与文档](https://github.com/dazhwu/pydynpd)、[JOSS 论文](https://doi.org/10.21105/joss.04416)、[公开系统 GMM 比较](https://github.com/dazhwu/pydynpd/blob/main/Benchmark/test_2.md)。

## 其他诊断、稳健性与报告

ADF 原假设为单位根；KPSS 原假设为水平/趋势平稳。仅单条确认频率的时间序列、≥20 期、至少三个不同值且无缺口时执行；p 值为 KPSS 表边界时保留警告。面板不拼接。ADF 的确定性项、最大滞后、AIC/BIC/t-stat 与 KPSS auto/legacy 可设。

Koenker–BP 是 OLS 残差异方差 LM 检验，本工作台只在含截距且非 cluster/HAC 的 OLS 提供。BG 仅用于足够长且完整规则的时间序列 OLS。FE/GMM 不套用普通 OLS 残差检验。

用户主动创建规格，所有结果独立保留。比较不会排序显著性。共同样本只匹配同一原始导入下的行号集合，按原规格再估计，不复用旧系数。组间差异联合检验目前仅两组 OLS：给全部斜率与常数加入组交互，用当前协方差检验所有斜率差为零。

规则报告只描述实际系数、区间与已完成检验；没有单位元数据时只用原变量单位，避免误报百分比/百分点。对于 log 变量不自动套用小变化近似；用户应根据最终变量构造给出经济解释。
