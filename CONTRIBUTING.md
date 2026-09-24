# 贡献指南

修改统计方法时，请同时提交方法来源、适用条件、失败情形和至少一种独立参考计算。禁止用预填常数、随机统计结果或 OLS/IV 替代未实现估计器。

报告缺陷时说明版本、模型配置、数据结构、频率、错误信息和最小复现步骤。请使用合成数据或取得授权的数据，不在 issue 中上传私有研究数据。可用 `examples/generate.py` 扩展合成示例。

运行 `python -m pytest -q` 和 `cd frontend && pnpm build`。服务器绑定 loopback。依赖改动须同步锁文件；新统计口径须更新 `docs/METHODS.md`、`FEATURES.md` 和验证证据。所有用户输入视为不可信，不引入 eval、动态 shell、任意 Python 公式执行或静默数据删除。
