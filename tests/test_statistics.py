"""Independent algebra/reference checks, not just tests of the adapter's syntax."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy.stats import t as student_t
from econworkbench.engine import estimate
from econworkbench.schema import ModelConfig

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def cross():
    return pd.read_csv(ROOT/'examples'/'synthetic_cross.csv')


@pytest.fixture
def panel():
    return pd.read_csv(ROOT/'examples'/'synthetic_panel.csv')


@pytest.mark.parametrize('se',['classic','HC1','HC3','cluster'])
def test_ols_independent_matrix_covariance(cross,se):
    df=cross.dropna().copy()
    c=ModelConfig(y='log_income',x=['education','experience'],se=se,cluster='region')
    r=estimate(df,c)
    X=np.column_stack([np.ones(len(df)),df[['education','experience']]])
    y=df.log_income.to_numpy()
    n,k=X.shape
    B=np.linalg.inv(X.T@X)
    beta=np.linalg.lstsq(X,y,rcond=None)[0]
    u=y-X@beta
    if se=='classic':
        V=B*(u@u)/(n-k)
    elif se=='HC1':
        V=B@((X*u[:,None]).T@(X*u[:,None]))@B*n/(n-k)
    elif se=='HC3':
        h=np.sum((X@B)*X,axis=1)
        score=X*(u/(1-h))[:,None]
        V=B@score.T@score@B
    else:
        sums=np.array([(X[df.region.to_numpy()==g]*u[df.region.to_numpy()==g,None]).sum(axis=0) for g in df.region.unique()])
        G=len(sums)
        V=B@sums.T@sums@B*G/(G-1)*(n-1)/(n-k)
    np.testing.assert_allclose([v['coefficient'] for v in r['coefficients']],beta,atol=1e-10)
    np.testing.assert_allclose([v['std_error'] for v in r['coefficients']],np.sqrt(np.diag(V)),rtol=1e-9)
    df_t=df.region.nunique()-1 if se=='cluster' else n-k
    np.testing.assert_allclose([v['p_value'] for v in r['coefficients']],2*student_t.sf(np.abs(beta/np.sqrt(np.diag(V))),df_t),atol=1e-10)


def test_hac_independent_bartlett():
    df=pd.read_csv(ROOT/'examples'/'synthetic_time.csv')
    r=estimate(df,ModelConfig(y='y',x=['x'],se='HAC',hac_lags=3,structure={'kind':'time','time':'month','frequency':'M'}))
    X=np.column_stack([np.ones(len(df)),df.x])
    y=df.y.to_numpy(); n,k=X.shape
    B=np.linalg.inv(X.T@X); b=B@X.T@y; scores=X*(y-X@b)[:,None]
    S=scores.T@scores
    for lag in range(1,4):
        cross=scores[lag:].T@scores[:-lag]
        S+=(1-lag/4)*(cross+cross.T)
    np.testing.assert_allclose(np.array(r['covariance']),B@S@B*n/(n-k),rtol=1e-9)


@pytest.mark.parametrize('effects',['entity','time','twoway'])
def test_unbalanced_fe_vs_explicit_dummy_ols(panel,effects):
    cfg=ModelConfig(model='fe',y='y',x=['x','control'],se='classic',effects=effects,structure={'kind':'panel','entity':'id','time':'year'})
    r=estimate(panel,cfg)
    X=sm.add_constant(panel[['x','control']])
    for col,include in [('id',effects in ['entity','twoway']),('year',effects in ['time','twoway'])]:
        if include:
            X=pd.concat([X,pd.get_dummies(panel[col],prefix=col,drop_first=True,dtype=float)],axis=1)
    ref=sm.OLS(panel.y,X).fit()
    for name in ['x','control']:
        row=next(v for v in r['coefficients'] if v['variable']==name)
        np.testing.assert_allclose([row['coefficient'],row['std_error']],[ref.params[name],ref.bse[name]],rtol=1e-9)
    assert r['df_resid']==ref.df_resid


def test_absorbed_variable_reported(panel):
    r=estimate(panel,ModelConfig(model='fe',y='y',x=['x','invariant'],se='HC1',structure={'kind':'panel','entity':'id','time':'year'}))
    assert 'invariant' in r['absorbed']
    assert any(t['name']=='VIF（吸收固定效应后）' and t['status']=='已完成' for t in r['tests'])


def test_two_period_did_matches_difference_of_means():
    rng=np.random.default_rng(17)
    rows=[]
    for i in range(80):
        a=rng.normal()
        for time in [0,1]:
            rows.append([i,time,i<40,a+1.5*time+2.7*(i<40)*time+rng.normal(scale=.4)])
    df=pd.DataFrame(rows,columns=['id','time','treat','y']);df.treat=df.treat.astype(int)
    r=estimate(df,ModelConfig(model='did',y='y',treat='treat',policy_time='1',se='cluster',cluster='id',structure={'kind':'panel','entity':'id','time':'time'}))
    means=df.groupby(['treat','time']).y.mean()
    ref=means[1,1]-means[1,0]-means[0,1]+means[0,0]
    row=next(v for v in r['coefficients'] if v['variable']=='DID_effect')
    assert row['coefficient']==pytest.approx(ref,abs=1e-10)
    assert r['event']['status']=='条件不足'


def test_did_event_joint_and_base():
    df=pd.read_csv(ROOT/'examples'/'synthetic_did_gmm.csv')
    cfg=json.loads((ROOT/'examples'/'configs.json').read_text(encoding='utf-8'))['did']
    r=estimate(df,ModelConfig(**cfg))
    assert r['event']['status']=='已完成'
    assert r['event']['joint']['status']=='已完成'
    assert next(c for c in r['event']['table'] if c.get('reference'))['period']==-1


def test_adf_and_kpss_statistics_by_algebra():
    df=pd.read_csv(ROOT/'examples'/'synthetic_time.csv')
    r=estimate(df,ModelConfig(y='y',x=['x'],adf_maxlag=0,structure={'kind':'time','time':'month','frequency':'M'}))
    adf=next(t for t in r['tests'] if t['name']=='ADF')
    y=df.y.to_numpy()
    aux=sm.OLS(np.diff(y),np.column_stack([y[:-1],np.ones(len(y)-1)])).fit()
    assert adf['statistic']==pytest.approx(aux.tvalues[0],abs=1e-10)
    kpss=next(t for t in r['tests'] if t['name']=='KPSS')
    residual=y-y.mean(); n=len(y); lag=kpss['lags']
    longvar=residual@residual/n
    for k in range(1,lag+1):
        longvar+=2*(1-k/(lag+1))*(residual[k:]@residual[:-k])/n
    ref=np.sum(np.cumsum(residual)**2)/(n*n*longvar)
    assert kpss['statistic']==pytest.approx(ref,rel=1e-10)


def test_bp_lm_independent_auxiliary(cross):
    df=cross.dropna()
    r=estimate(df,ModelConfig(y='log_income',x=['education','experience']))
    X=sm.add_constant(df[['education','experience']])
    u=sm.OLS(df.log_income,X).fit().resid
    aux=sm.OLS(u*u,X).fit()
    test=next(t for t in r['tests'] if t['name']=='Koenker–Breusch–Pagan')
    assert test['statistic']==pytest.approx(len(df)*aux.rsquared,abs=1e-9)


def test_system_gmm_published_arellano_bond_benchmark():
    df=pd.read_csv(ROOT/'tests'/'fixtures'/'arellano_bond.csv')
    c=ModelConfig(model='gmm',y='n',x=['w','k'],structure={'kind':'panel','entity':'id','time':'year'},gmm={'y_lags':2,'predetermined':['w'],'exogenous':['k'],'lag_min':2,'lag_max':4,'pred_min':1,'pred_max':3,'collapse':False,'time_dummies':False})
    r=estimate(df.sample(frac=1,random_state=13),c)
    # Published pydynpd API values; independently published R panelvar matches to 4 decimals.
    beta=[.9453810,-.0860069,-.4477795,.1235808,1.5630849]
    se=[.1429764,.1082318,.1521917,.0508836,.4993484]
    np.testing.assert_allclose([v['coefficient'] for v in r['coefficients']],beta,atol=5e-7)
    np.testing.assert_allclose([v['std_error'] for v in r['coefficients']],se,atol=5e-7)
    panelvar_beta=[.9454,-.0860,-.4478,.1236,1.5631]
    np.testing.assert_allclose([v['coefficient'] for v in r['coefficients']],panelvar_beta,atol=5e-5)
    assert (r['nobs'],r['entities'],r['instruments'])==(611,140,51)
    assert r['tests'][0]['statistic']==pytest.approx(-2.35,abs=.005)
    assert r['tests'][1]['statistic']==pytest.approx(-1.15,abs=.005)
    assert r['tests'][2]['statistic']==pytest.approx(96.442,abs=.001)


@pytest.mark.parametrize('steps',[1,2])
def test_gmm_complete_calendar_and_steps(steps):
    df=pd.read_csv(ROOT/'examples'/'synthetic_did_gmm.csv')
    config=json.loads((ROOT/'examples'/'configs.json').read_text(encoding='utf-8'))['gmm']
    config['gmm']['steps']=steps
    config['gmm']['time_dummies']=False
    cfg=ModelConfig(**config)
    gap=df[df.year!=2015]
    explicit=df.copy()
    explicit.loc[explicit.year==2015,['dynamic_y','x','control']]=np.nan
    a,b=estimate(gap,cfg),estimate(explicit,cfg)
    np.testing.assert_allclose([c['coefficient'] for c in a['coefficients']],[c['coefficient'] for c in b['coefficients']],atol=1e-10)
    assert a['nobs']==b['nobs']
    assert 'Windmeijer' in a['se_note'] if steps==2 else '一步' in a['se_note']


def test_heterogeneity_interaction(cross):
    r=estimate(cross,ModelConfig(y='log_income',x=['education'],controls=['experience'],se='HC3',group='region'))
    assert len(r['heterogeneity'])==2
    assert all(g['status']=='已完成' for g in r['heterogeneity'])
    assert r['heterogeneity_test']['status']=='已完成'
