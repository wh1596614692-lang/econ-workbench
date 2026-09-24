import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.diagnostic import het_breuschpagan, acorr_breusch_godfrey
from statsmodels.tsa.stattools import adfuller, kpss
from .data import indexed


def status(name, state, note, **values):
    if state == '已完成' and any(k in values and (values[k] is None or not np.isfinite(values[k])) for k in ['statistic','p_value']):
        state = '条件不足'
        note += ' 统计量或 p 值非有限，不能据此作检验结论。'
    return dict(name=name, status=state, note=note, **values)


def vif_table(X):
    if X.shape[1] == 0:
        return []
    x = sm.add_constant(X, has_constant='skip').astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        return [{'variable':c, 'vif':float(variance_inflation_factor(x.to_numpy(), i))}
                for i,c in enumerate(x.columns) if c != 'const' and np.std(x[c]) > 1e-12]


def unit_roots(df, cfg, variable):
    if cfg.structure.kind != 'time':
        return [status('ADF / KPSS', '不适用' if cfg.structure.kind == 'cross' else '尚未实现',
                       '仅对已确认频率的单条时间序列运行；面板单位根检验尚未实现，不拼接个体序列。')]
    try:
        _, ticks, _ = indexed(df, cfg.structure)
        values = df.loc[ticks.sort_values().index, variable].replace([np.inf,-np.inf], np.nan)
        if values.isna().any() or (np.diff(np.sort(ticks)) != 1).any():
            raise ValueError('序列有缺失值或时间缺口；须先明确处理，不能删除后压缩时间。')
        if len(values) < 20 or values.nunique() < 3:
            raise ValueError('要求至少 20 期且有足够变异；当前序列过短或近似常数。')
    except ValueError as e:
        return [status(n, '条件不足', str(e)) for n in ['ADF','KPSS']]
    output = []
    for name in ['ADF','KPSS']:
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                if name == 'ADF':
                    v = adfuller(values, regression=cfg.adf_regression, maxlag=cfg.adf_maxlag, autolag=cfg.adf_autolag)
                    output.append(status(name,'已完成','原假设：存在单位根。拒绝与否取决于所选确定性项和滞后；不自动差分。', statistic=v[0],p_value=v[1],lags=v[2],nobs=v[3],critical=v[4],settings=cfg.adf_regression+'/'+cfg.adf_autolag))
                else:
                    v = kpss(values, regression=cfg.adf_regression, nlags=cfg.kpss_lags)
                    output.append(status(name,'已完成','原假设：围绕常数/趋势平稳。表列范围以外的 p 值是边界值。', statistic=v[0],p_value=v[1],lags=v[2],critical=v[3],settings=cfg.adf_regression+'/'+cfg.kpss_lags))
                output[-1]['warnings'] = [str(w.message) for w in caught]
        except Exception as e:
            output.append(status(name,'运行失败',str(e)))
    return output


def diagnostics(df, cfg, X, fit, y_name):
    out = []
    try:
        out.append(status('VIF（原始设计矩阵）','已完成','包含截距的辅助回归。高 VIF 不触发删变量。',table=vif_table(X)))
        if cfg.model in {'fe','did'}:
            import pyhdfe
            ids = []
            if cfg.effects in {'entity','twoway'} or cfg.model == 'did':
                ids.append(pd.factorize(df[cfg.structure.entity])[0])
            if cfg.effects in {'time','twoway'} or cfg.model == 'did':
                ids.append(pd.factorize(df[cfg.structure.time])[0])
            cols = [c for c in X if c != 'const']
            residualized = pyhdfe.create(np.column_stack(ids), drop_singletons=False).residualize(X[cols].to_numpy())
            keep = np.std(residualized, axis=0) > 1e-10
            table = vif_table(pd.DataFrame(residualized[:,keep], columns=np.array(cols)[keep]))
            out.append(status('VIF（吸收固定效应后）','已完成','迭代投影吸收固定效应，适用于不平衡面板；不含已吸收变量。',table=table))
    except Exception as e:
        out.append(status('VIF','运行失败',str(e)))
    if cfg.model == 'ols' and 'const' in X and cfg.se not in {'cluster','HAC'}:
        try:
            v = het_breuschpagan(fit.resid, X, robust=True)
            out.append(status('Koenker–Breusch–Pagan','已完成','OLS 残差异方差 LM 检验，原假设为条件方差恒定；需观测独立。',statistic=v[0],p_value=v[1]))
        except Exception as e:
            out.append(status('Koenker–Breusch–Pagan','运行失败',str(e)))
    else:
        out.append(status('Koenker–Breusch–Pagan','不适用','仅在含截距、非聚类/HAC 的 OLS 中提供；不套用到 FE、DID 或 GMM。'))
    if cfg.model == 'ols' and cfg.structure.kind == 'time':
        try:
            _, t, _ = indexed(df, cfg.structure)
            if len(t) < 20 or (np.diff(t) != 1).any():
                raise ValueError('有效样本过短或删除缺失后存在时间缺口。')
            base = sm.OLS(df[y_name], X).fit()
            v = acorr_breusch_godfrey(base, nlags=min(max(cfg.hac_lags,1),len(t)//5))
            out.append(status('Breusch–Godfrey','已完成','OLS 残差 LM 检验；原假设为所选滞后内无序列相关。',statistic=v[0],p_value=v[1]))
        except ValueError as e:
            out.append(status('Breusch–Godfrey','条件不足',str(e)))
    else:
        out.append(status('Breusch–Godfrey','不适用','仅用于按真实时间排序且无缺口的时间序列 OLS。'))
    return out
