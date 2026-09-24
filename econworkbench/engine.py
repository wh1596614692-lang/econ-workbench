"""Statistical engine shared by the API and exported reproduction scripts."""
import contextlib
import importlib.metadata
import io
import platform
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from linearmodels.panel import PanelOLS
from .schema import ModelConfig
from .data import describe, fingerprint, indexed, require_columns, time_ticks, overview
from .formula import design
from .diagnostics import diagnostics, status, unit_roots


def versions():
    return {'python':platform.python_version(), **{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','statsmodels','linearmodels','pydynpd','fastapi']}}


def coefficient_table(names, params, se, stat, p, ci):
    return [dict(variable=str(n), coefficient=float(b), std_error=float(s), statistic=float(t), p_value=float(pv),
                 ci_low=float(lo), ci_high=float(hi), stars='***' if pv < .01 else '**' if pv < .05 else '*' if pv < .1 else '')
            for n,b,s,t,pv,(lo,hi) in zip(names,params,se,stat,p,ci)]


def validate_rank(X):
    if len(X) <= X.shape[1] + 2:
        raise ValueError('有效样本太少：至少需大于参数数目 + 2。请减少参数或增加观测。')
    if np.linalg.matrix_rank(X.to_numpy()) < X.shape[1]:
        raise ValueError('解释变量完全共线或存在常数列。请检查重复变量、虚拟变量和恒等关系；系统不会自动挑选显著变量。')


def ols_fit(y, X, sample, cfg):
    validate_rank(X)
    model = sm.OLS(y, X)
    if cfg.se == 'classic':
        return model.fit(), '常规 OLS；t/F 分布；残差自由度 n−k'
    if cfg.se in {'HC1','HC3'}:
        return model.fit(cov_type=cfg.se, use_t=True), f'{cfg.se} 异方差稳健；t/F 分布，df=n−k'
    if cfg.se == 'cluster':
        require_columns(sample,[cfg.cluster])
        n = sample[cfg.cluster].nunique()
        if n < 2:
            raise ValueError('聚类至少需要 2 个独立簇。')
        return model.fit(cov_type='cluster',cov_kwds={'groups':pd.factorize(sample[cfg.cluster])[0], 'use_correction':True,'df_correction':True},use_t=True), f'单向聚类 {cfg.cluster}，{n} 簇；CR1 修正；t/F 推断 df=G−1'
    if cfg.structure.kind != 'time':
        raise ValueError('HAC 仅支持确认频率且无缺口的单条时间序列。')
    _, t, _ = indexed(sample,cfg.structure)
    if (np.diff(t) != 1).any() or cfg.hac_lags >= len(sample):
        raise ValueError('HAC 有效样本存在时间缺口或滞后过大；不能压缩时间后计算。')
    return model.fit(cov_type='HAC', cov_kwds={'maxlags':cfg.hac_lags,'use_correction':True},use_t=True), f'HAC Bartlett 核，最大滞后 {cfg.hac_lags}，n/(n−k) 修正；t/F df=n−k'


def panel_fit(y, X, sample, cfg):
    if cfg.structure.kind != 'panel':
        raise ValueError('固定效应和 DID 需要面板结构、个体 ID 与时间索引。')
    idx, _, _ = indexed(sample,cfg.structure)
    yp, xp = y.copy(), X.copy()
    yp.index, xp.index = idx, idx
    eff = 'twoway' if cfg.model == 'did' else cfg.effects
    if len(idx.unique(0)) < 2 or len(idx.unique(1)) < 2:
        raise ValueError('面板模型至少需要两个个体和两个时期。')
    # Absorption is delegated to PanelOLS; rank defects among remaining regressors are errors.
    model = PanelOLS(yp,xp,entity_effects=eff in {'entity','twoway'},time_effects=eff in {'time','twoway'},drop_absorbed=True,check_rank=True)
    options = dict(debiased=True,auto_df=True)
    if cfg.se == 'classic':
        options['cov_type'] = 'unadjusted'
    elif cfg.se == 'HC1':
        options['cov_type'] = 'robust'
    elif cfg.se == 'cluster':
        require_columns(sample,[cfg.cluster])
        if sample[cfg.cluster].nunique() < 2:
            raise ValueError('聚类至少需要两个独立簇。')
        options.update(cov_type='clustered',clusters=pd.DataFrame({'cluster':pd.factorize(sample[cfg.cluster])[0]},index=idx), group_debias=True)
    else:
        raise ValueError('面板 FE/DID 提供常规、HC1 或单向聚类标准误；HC3/HAC 在此尚未实现。')
    fit = model.fit(**options)
    if fit.df_resid < 3:
        raise ValueError('吸收固定效应后残差自由度不足 3。')
    note = f'PanelOLS {options["cov_type"]}；debiased=True, auto_df=True；t/F 推断 df={fit.df_resid}'
    if cfg.se == 'cluster':
        note += '；簇数修正 G/(G−1)·(n−1)/n；聚类自由度按 linearmodels 的效应嵌套规则调整'
    return fit, note


def did_design(df,cfg,X):
    s = cfg.structure
    if s.kind != 'panel':
        raise ValueError('DID 需要面板数据。')
    _, ticks, entity = indexed(df,s)
    require_columns(df,[cfg.treat])
    treat = df[cfg.treat]
    if treat.isna().any() or not set(treat.unique()).issubset({0,1}) or treat.nunique() != 2:
        raise ValueError('处理组变量必须为无缺失的 0/1，且同时存在处理组与对照组。')
    if treat.groupby(entity).nunique().max() != 1:
        raise ValueError('处理组变量在个体内变化：可能是分期实施政策或时变处理。分期 DID 尚未实现，已阻止普通 TWFE 估计。请使用固定的 ever-treated 分组及共同政策时点。')
    if cfg.post:
        require_columns(df,[cfg.post])
        post = df[cfg.post]
        if post.isna().any() or not set(post.unique()).issubset({0,1}):
            raise ValueError('政策后变量必须为无缺失的 0/1。')
        if post.groupby(ticks).nunique().max() > 1:
            raise ValueError('同一时期政策后状态不一致：可能存在分期实施。分期 DID 尚未实现，已阻止估计；post 必须是所有组共同的政策后指示。')
        bytime = post.groupby(ticks).first().sort_index()
        if bytime.nunique() != 2 or (bytime.diff().dropna() < 0).any():
            raise ValueError('政策后变量必须在共同时间点从 0 单次变为 1。')
        policy = int(bytime[bytime == 1].index.min())
    else:
        if not cfg.policy_time:
            raise ValueError('请设置共同政策实施时间或 post 变量。')
        policy = int(time_ticks(pd.Series([cfg.policy_time]),s).iloc[0])
        post = (ticks >= policy).astype(int)
    if pd.crosstab(treat,post).shape != (2,2) or (pd.crosstab(treat,post) == 0).any().any():
        raise ValueError('需要处理/对照组各自的政策前、后观测。')
    if 'DID_effect' in X or 'DID_effect' in df:
        raise ValueError('DID_effect 为保留输出名，请重命名原变量。')
    X = X.copy()
    X['DID_effect'] = treat*post
    return X, ticks-policy, treat


def event_study(sample,cfg,X,y,rel,treat):
    if not cfg.event_study:
        return status('事件研究','不适用','用户未选择运行。')
    if len(set(rel[rel<0])) < 2 or len(set(rel[rel>=0])) < 2 or cfg.event_base not in set(rel):
        return status('事件研究','条件不足','至少需要两个政策前时期、两个政策后时期，且指定基准期在样本中。')
    if cfg.event_base < -cfg.event_before:
        return status('事件研究','条件不足','基准期不能落在前端合并区间之外。')
    try:
        exog = X.drop(columns=['DID_effect']).copy()
        # Tail binning retains all regression observations and states the interpretation explicitly.
        binned = rel.clip(-cfg.event_before,cfg.event_after)
        periods = sorted(set(binned.astype(int))-{cfg.event_base})
        names = []
        for k in periods:
            name = f'event_m{abs(k)}' if k < 0 else f'event_p{k}'
            names.append(name)
            exog[name] = (binned == k).astype(float)*treat
        fitted, _ = panel_fit(y,exog,sample,cfg)
        if any(n not in fitted.params for n in names):
            raise ValueError('部分相对期被吸收，事件研究无法完整识别。')
        ci = fitted.conf_int()
        rows = [dict(period=k, variable=n, coefficient=float(fitted.params[n]),ci_low=float(ci.loc[n].iloc[0]),ci_high=float(ci.loc[n].iloc[1])) for k,n in zip(periods,names)]
        rows.append(dict(period=cfg.event_base,variable='基准期',coefficient=0.,ci_low=0.,ci_high=0.,reference=True))
        pre = [n for k,n in zip(periods,names) if k<0]
        joint = status('政策前联合检验','条件不足','没有可检验的政策前系数。')
        if pre:
            R = np.array([[float(p == n) for p in fitted.params.index] for n in pre])
            w = fitted.wald_test(R)
            joint = status('政策前联合检验','已完成','Wald χ²；未拒绝政策前系数为零不等于证明平行趋势。',statistic=w.stat,p_value=w.pval,df=w.df)
        return status('事件研究','已完成',f'基准期 {cfg.event_base}；≤−{cfg.event_before} 和 ≥{cfg.event_after} 合并尾部；95% 逐点置信区间，非同时置信带。',table=sorted(rows,key=lambda x:x['period']),joint=joint)
    except Exception as e:
        return status('事件研究','运行失败',str(e))


def fit_gmm(df,cfg):
    if cfg.structure.kind != 'panel' or cfg.mode != 'form':
        raise ValueError('系统 GMM 请使用表单配置并设置面板索引；不接受自由 GMM 命令。')
    g, s = cfg.gmm,cfg.structure
    if g.lag_min > g.lag_max or g.pred_min > g.pred_max:
        raise ValueError('工具变量最小滞后不能大于最大滞后。')
    variables = cfg.x+cfg.controls
    roles = g.endogenous+g.predetermined+g.exogenous
    if len(roles) != len(set(roles)) or set(roles) != set(variables) or len(variables) != len(set(variables)):
        raise ValueError('所有解释变量必须且只能归入内生、预定、严格外生中的一类，并与 X/控制变量一致。')
    require_columns(df,[cfg.y]+variables)
    if cfg.y in variables:
        raise ValueError('当期 Y 不能同时作为 X；Y 滞后由专用设置生成。')
    if any(not pd.api.types.is_numeric_dtype(df[c]) for c in [cfg.y]+variables):
        raise ValueError('GMM 模型变量必须为数值。')
    _, ticks, ent = indexed(df,s)
    N,T = ent.nunique(), int(ticks.max()-ticks.min()+1)
    if N < 10 or T < max(6,g.y_lags+4):
        raise ValueError('本工作台要求 GMM 至少 10 个个体和 6 期，并留足动态滞后/AR(2) 检验所需时期。')
    if T > 40 or N*T > 100_000:
        raise ValueError('GMM 计算限制：最多 40 期且补齐网格不超过 10 万行。请缩小样本。')
    aliases = {v:f'a{i}' for i,v in enumerate([cfg.y]+variables)}
    reverse = {v:k for k,v in aliases.items()}
    data = df[[cfg.y]+variables].rename(columns=aliases).replace([np.inf,-np.inf],np.nan)
    data['panelid'] = ent
    data['period'] = ticks
    # pydynpd encodes time categorically; explicitly fill the global calendar so a
    # year missing for ALL entities cannot silently become one observed period.
    grid = pd.MultiIndex.from_product([sorted(ent.unique()),range(int(ticks.min()),int(ticks.max())+1)],names=['panelid','period'])
    data = data.set_index(['panelid','period']).reindex(grid).reset_index()
    data = data.sort_values(['panelid','period']).reset_index(drop=True)
    if g.time_dummies and data.groupby('period')[aliases[cfg.y]].count().eq(0).any():
        raise ValueError('存在对所有个体均缺失 Y 的时期，该期时间虚拟变量无法识别。请取消 GMM 时间虚拟变量或明确缩小时间范围；不会压缩时间缺口。')
    dep = aliases[cfg.y]
    rhs = f'{dep} L(1:{g.y_lags}).{dep} ' + ' '.join(aliases[v] for v in variables)
    instruments = f'gmm({dep} {" ".join(aliases[v] for v in g.endogenous)}, {g.lag_min}:{g.lag_max})'
    if g.predetermined:
        instruments += f' gmm({" ".join(aliases[v] for v in g.predetermined)}, {g.pred_min}:{g.pred_max})'
    if g.exogenous:
        instruments += f' iv({" ".join(aliases[v] for v in g.exogenous)})'
    opts = ' '.join(x for x in ['collapse' if g.collapse else '', 'onestep' if g.steps == 1 else '', 'timedumm' if g.time_dummies else ''] if x)
    command = rhs+' | '+instruments+' | '+opts
    # Conservative bound prevents instrument proliferation from exhausting memory.
    bound = ((g.lag_max-g.lag_min+1)*(1+len(g.endogenous))+(g.pred_max-g.pred_min+1)*len(g.predetermined))*(2 if g.collapse else 2*T) + len(g.exogenous)+T
    if bound > 350:
        raise ValueError('工具变量矩阵过大。请折叠工具变量、缩短滞后范围或减少内生变量。')
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        from pydynpd import regression
        try:
            m = regression.abond(command,data,['panelid','period']).models[0]
        except SystemExit as e:
            raise ValueError('GMM 库拒绝配置：'+capture.getvalue()[-1500:]) from e
    tab = m.regression_table
    if not np.isfinite(tab[['coefficient','std_err','z_value','p_value']].to_numpy()).all() or (tab.std_err <= 0).any():
        raise ValueError('GMM 输出非有限值或退化标准误；请检查识别、工具变量和组内变异。')
    # Reject generalized-inverse solutions to rank-deficient moment systems.
    rank = np.linalg.matrix_rank(m.step_results[g.steps-1].vcov)
    if rank < len(tab):
        raise ValueError('GMM 协方差矩阵秩不足；请减少工具变量或调整模型。')
    def display_name(n):
        if n in reverse:
            return reverse[n]
        if '.' in n:
            lag,col = n.split('.',1)
            return lag+'.'+reverse.get(col,col)
        return n
    ci = np.column_stack([tab.coefficient- stats.norm.ppf(.975)*tab.std_err,tab.coefficient+stats.norm.ppf(.975)*tab.std_err])
    coefficients = coefficient_table([display_name(n) for n in tab.variable],tab.coefficient,tab.std_err,tab.z_value,tab.p_value,ci)
    checks = [status(f'Arellano–Bond AR({a.lag})','已完成','差分残差序列相关检验，原假设为该阶无相关；pydynpd 的检验取两步结果（一步系数时亦如此）。',statistic=a.AR,p_value=a.P_value) for a in m.AR_list]
    checks.append(status('Hansen J','已完成' if m.hansen.df>0 else '条件不足','原假设为过度识别矩条件成立；不拒绝不能证明工具有效，工具过多会削弱检验。',statistic=m.hansen.test_value,p_value=m.hansen.p_value,df=m.hansen.df))
    checks.append(status('Difference-in-Hansen','尚未实现','pydynpd 当前适配接口不提供该检验。'))
    notes = [str(w.message) for w in caught]
    if m.z_information.num_instr >= N:
        notes.append('工具变量数不少于个体数，存在工具增殖风险；建议折叠并缩短滞后范围。')
    if N < 50:
        notes.append('个体数少于 50，GMM 大 N 渐近推断可能不可靠。')
    if T >= N:
        notes.append('T≥N：动态面板 GMM 的短面板适用性不足。')
    notes += ['系统 GMM 还要求水平方程的额外矩条件及初始条件假设；高持续性可能导致弱工具。', 'GMM 观测数为库报告的可用差分方程观测数，不是原始行数；描述统计使用估计输入数据，不能称为单一回归有效样本。']
    return dict(coefficients=coefficients, nobs=int(m.num_obs), entities=int(m.N), instruments=int(m.z_information.num_instr),
                r2=None, adjusted_r2=None, df_resid=None, tests=checks, warnings=notes,
                se_note='两步稳健，Windmeijer (2005) 有限样本方差修正；z/正态推断' if g.steps == 2 else '一步稳健方差；z/正态推断；Hansen/AR 检验来自库内部的两步拟合',
                command=command, aliases=reverse, sample_ids=None, absorbed=[], event=None,
                formula=f'{cfg.y} ~ '+ ' + '.join([f'L{l}.{cfg.y}' for l in range(1,g.y_lags+1)]+variables),
                covariance=m.step_results[g.steps-1].vcov.tolist(), parameter_names=[display_name(n) for n in tab.variable])


def estimate(df, cfg: ModelConfig, include_groups=True):
    original = df
    if cfg.sample_ids is not None:
        df = df.loc[df.index.intersection(cfg.sample_ids)].copy()
    if df.empty:
        raise ValueError('当前筛选/共同样本为空。')
    if cfg.structure.kind != 'cross':
        _, ticks, ent = indexed(df,cfg.structure)
        order = pd.DataFrame({'e':ent,'t':ticks}).sort_values(['e','t']).index
        df = df.loc[order]
    if cfg.model == 'gmm':
        result = fit_gmm(df,cfg)
        result['descriptive'] = describe(df,[cfg.y]+cfg.x+cfg.controls)
        result['descriptive']['note'] = 'GMM 输入样本（含滞后/工具所需的历史观测）；N 与差分方程可用观测数不同。'
        result['tests'] += unit_roots(df,cfg,cfg.y)
        result['y'] = cfg.y
    else:
        yname, X, used, notes = design(df,cfg)
        rel = treat = None
        if cfg.model == 'did':
            X,rel,treat = did_design(df,cfg,X)
        if cfg.se == 'cluster':
            require_columns(df,[cfg.cluster])
        valid = X.replace([np.inf,-np.inf],np.nan).notna().all(axis=1) & np.isfinite(df[yname])
        if cfg.se == 'cluster':
            valid &= df[cfg.cluster].notna()
        sample, X = df.loc[valid].copy(), X.loc[valid].copy()
        if len(sample) < 6:
            raise ValueError('有效样本少于 6 行，请检查缺失、变量和筛选规则。')
        if df[yname].loc[valid].nunique() < 2:
            raise ValueError('被解释变量在有效样本中没有变异。')
        if cfg.model == 'did':
            # Repeat identifying support checks on actual complete-case sample.
            did_design(sample,cfg,X.drop(columns=['DID_effect']))
        notes.append(f'完整案例规则：输入 {len(df)} 行，因模型变量缺失/无穷或聚类变量缺失排除 {len(df)-len(sample)} 行；有效 {len(sample)} 行。原始数据保留。')
        if cfg.se == 'cluster':
            clusters = sample[cfg.cluster].nunique()
            if clusters < 30:
                notes.append(f'仅 {clusters} 个聚类；常规聚类渐近推断可能不可靠，未实现 wild-cluster bootstrap。')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            if cfg.model == 'ols':
                fit,se_note = ols_fit(sample[yname],X,sample,cfg)
                coefficients = coefficient_table(X.columns,fit.params,fit.bse,fit.tvalues,fit.pvalues,fit.conf_int().to_numpy())
                r2, adj = float(fit.rsquared),float(fit.rsquared_adj)
                absorbed = []
                F = status('整体显著性 F / Wald F','已完成','除截距外系数联合为零，使用当前协方差估计；不检验因果识别。',statistic=float(fit.fvalue),p_value=float(fit.f_pvalue),df_num=float(fit.df_model),df_denom=float(getattr(fit,'df_resid_inference',fit.df_resid)))
                r2s = {'r2':r2,'adjusted_r2':adj}
                cov = fit.cov_params().to_numpy()
            else:
                fit,se_note = panel_fit(sample[yname],X,sample,cfg)
                coefficients = coefficient_table(fit.params.index,fit.params,fit.std_errors,fit.tstats,fit.pvalues,fit.conf_int().to_numpy())
                absorbed = [c for c in X if c not in fit.params]
                if cfg.model == 'did' and 'DID_effect' in absorbed:
                    raise ValueError('DID 政策项被吸收，政策效应无法识别。')
                r2s = {'r2':float(fit.rsquared),'adjusted_r2':None,'within':float(fit.rsquared_within),'between':float(fit.rsquared_between),'overall':float(fit.rsquared_overall),'inclusive':float(fit.rsquared_inclusive)}
                f = fit.f_statistic if cfg.se == 'classic' else fit.f_statistic_robust
                F = status('整体显著性 F / Wald F','已完成','斜率系数联合为零；PanelOLS 当前协方差；固定效应不在检验集合内。',statistic=f.stat,p_value=f.pval,df_num=f.df,df_denom=f.df_denom)
                cov = fit.cov.to_numpy()
        notes += [str(w.message) for w in caught]
        if absorbed:
            notes.append('被固定效应吸收且无法单独识别：'+', '.join(absorbed))
        if not np.isfinite(np.array([[r['coefficient'],r['std_error']] for r in coefficients])).all():
            raise ValueError('系数或标准误非有限；请检查样本变异、自由度和共线性。')
        result = dict(coefficients=coefficients,nobs=len(sample),df_resid=float(fit.df_resid),**r2s,
                      sample_ids=[int(i) for i in sample.index],warnings=notes,absorbed=absorbed,se_note=se_note,
                      y=yname,formula=yname+' ~ '+' + '.join(X.columns),tests=[F]+diagnostics(sample,cfg,X,fit,yname)+unit_roots(df,cfg,yname),
                      covariance=cov.tolist(),parameter_names=[r['variable'] for r in coefficients],
                      descriptive=describe(sample,used),event=None)
        result['descriptive']['note'] = '本模型回归有效样本；相关系数为 Pearson（完整案例样本）。相关不代表因果。'
        if cfg.model in {'fe','did'}:
            result['entities'] = int(sample[cfg.structure.entity].nunique())
            result['warnings'].append('面板 R² 为吸收所设效应后的口径；within/between/overall 不可当成同一个 R²，也不直接与 OLS 比较。')
        if cfg.model == 'did':
            result['event'] = event_study(sample,cfg,X,sample[yname],rel.loc[sample.index],treat.loc[sample.index])
            result['warnings'].append('DID 因果解释依赖平行趋势、无预期效应、稳定构成和无溢出等假设；当前仅支持共同政策时点。')
    result.update(config=cfg.model_dump(),data_hash=fingerprint(original),input_rows=len(df),versions=versions(),random_seed=None,
                  structure=overview(df,{},cfg.structure)['panel'],heterogeneity=[],heterogeneity_test=None)
    if cfg.group and include_groups:
        require_columns(df,[cfg.group])
        if df[cfg.group].nunique() > 12:
            raise ValueError('异质性分组超过 12 类，请使用类别变量或先筛选。')
        for label,part in df.groupby(cfg.group,dropna=False):
            try:
                sub = estimate(part,cfg.model_copy(update={'group':'','name':cfg.name+' / '+str(label)}),False)
                result['heterogeneity'].append(dict(group=str(label),status='已完成',input_rows=len(part),result=sub))
            except ValueError as e:
                result['heterogeneity'].append(dict(group=str(label),status='条件不足',input_rows=len(part),note=str(e)))
            except Exception as e:
                result['heterogeneity'].append(dict(group=str(label),status='运行失败',input_rows=len(part),note=str(e)))
        result['heterogeneity_test'] = heterogeneity_test(df,cfg)
        result['warnings'].append('一组显著、另一组不显著，不等于组间差异显著；分组会改变样本构成并增加多重检验风险。')
    return result


def heterogeneity_test(df,cfg):
    if cfg.model != 'ols' or df[cfg.group].nunique() != 2:
        return status('组间斜率差异','尚未实现','当前只对恰有两组的 OLS 提供完整交互项联合检验。各组独立估计不构成差异检验。')
    try:
        y,X,_,_ = design(df,cfg)
        levels = sorted(df[cfg.group].dropna().unique(),key=str)
        group = df[cfg.group].eq(levels[1]).astype(float)
        valid = X.replace([np.inf,-np.inf],np.nan).notna().all(axis=1) & np.isfinite(df[y]) & df[cfg.group].notna()
        if cfg.se == 'cluster':
            valid &= df[cfg.cluster].notna()
        interactions=[]
        for c in list(X):
            name='group2:'+c
            X[name]=X[c]*group
            if c != 'const':
                interactions.append(name)
        fit,_=ols_fit(df.loc[valid,y],X.loc[valid],df.loc[valid],cfg)
        R=np.array([[float(p==n) for p in X.columns] for n in interactions])
        w=fit.wald_test(R,use_f=True,scalar=True)
        return status('组间斜率差异','已完成',f'完整交互模型：{levels[1]} 相对于 {levels[0]} 的所有斜率差联合为零；使用当前协方差。',statistic=float(w.statistic),p_value=float(w.pvalue),df_num=float(w.df_num),df_denom=float(w.df_denom))
    except Exception as e:
        return status('组间斜率差异','运行失败',str(e))
