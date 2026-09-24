import io
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from econworkbench.schema import ModelConfig, Structure, Transform
from econworkbench.data import read_upload, transform, indexed, overview, describe
from econworkbench.engine import estimate
from econworkbench.formula import design
from econworkbench.serialization import frame_payload, restore_frame

ROOT=Path(__file__).resolve().parents[1]
S=Structure(kind='panel',entity='id',time='year')


def test_import_chinese_and_collision():
    raw='收入,v001,log,a-b\n1,2,3,4\n5,6,7,8'.encode()
    df,mapping,*_=read_upload(raw,'../../untrusted.csv')
    assert len(set(df.columns))==4
    assert '收入' in mapping.values()
    assert all(c.isascii() for c in df.columns)


def test_excel_sheet_and_dta_roundtrip():
    book=(ROOT/'examples'/'synthetic_workbook.xlsx').read_bytes()
    df,_,sheets,chosen=read_upload(book,'x.xlsx','面板_合成演示数据')
    assert len(sheets)==2 and len(df)==1200
    memory=io.BytesIO();df.to_stata(memory,write_index=False,version=118)
    imported,*_=read_upload(memory.getvalue(),'x.dta')
    np.testing.assert_allclose(imported.y,df.y)


@pytest.mark.parametrize('formula',["y ~ __import__('os').system('dir')",'y ~ np.log(x)','y ~ x;print(1)','y ~ x + x','y ~~ x','y ~ x +','y ~ x / 2'])
def test_unsafe_or_invalid_formula_blocked(formula):
    df=pd.DataFrame({'y':range(12),'x':range(1,13)})
    with pytest.raises(ValueError):
        design(df,ModelConfig(mode='formula',formula=formula))


def test_formula_transforms_and_nonpositive():
    df=pd.DataFrame({'y':range(12),'x':range(-1,11),'z':np.arange(12)**2})
    y,X,used,notes=design(df,ModelConfig(mode='formula',formula='y ~ log(x) + x*z + square(z)'))
    assert X['log(x)'].isna().sum()==2
    assert {'x','z','x:z','square(z)'}.issubset(X.columns)
    assert notes


def test_lag_and_difference_never_cross_gap_or_entity():
    df=pd.DataFrame({'id':[1,1,1,2,2],'year':[2020,2022,2023,2020,2021],'x':[10,20,30,100,110]})
    lag,log=transform(df,Transform(op='lag',columns=['x']),S)
    assert np.isnan(lag.loc[1,'lag_x'])
    assert lag.loc[2,'lag_x']==20 and lag.loc[4,'lag_x']==100
    diff,_=transform(df,Transform(op='diff',columns=['x']),S)
    assert np.isnan(diff.loc[1,'diff_x']) and diff.loc[2,'diff_x']==10
    assert 'lag_x' not in df
    assert log['detail']['missing_after']==3


def test_monthly_lag_and_missingness():
    df=pd.DataFrame({'time':['2020-01','2020-03','2020-04'],'x':[1,3,4]})
    s=Structure(kind='time',time='time',frequency='M')
    out,_=transform(df,Transform(op='lag',columns=['x']),s)
    assert out['lag_x'].isna().sum()==2 and out.loc[2,'lag_x']==3


def test_duplicate_index_rejected():
    df=pd.DataFrame({'id':[1,1],'year':[2020,2020]})
    with pytest.raises(ValueError,match='重复'):
        indexed(df,S)
    assert overview(df,{},S)['panel']['duplicate_index_rows']==2


@pytest.mark.parametrize('failure',['collinear','small','constant','strings'])
def test_model_validation(failure):
    rng=np.random.default_rng(2)
    df=pd.DataFrame({'y':rng.normal(size=20),'x':rng.normal(size=20),'z':rng.normal(size=20)})
    if failure=='collinear':df.z=df.x*2
    if failure=='small':df=df.iloc[:4]
    if failure=='constant':df.y=1
    if failure=='strings':df.x='not a number'
    with pytest.raises(ValueError):
        estimate(df,ModelConfig(y='y',x=['x','z']))


def test_staggered_did_rejected():
    df=pd.read_csv(ROOT/'examples'/'synthetic_did_gmm.csv')
    df['policy']=((df.id<50)&(df.year>=(2015+df.id%2))).astype(int)
    cfg=ModelConfig(model='did',y='y',treat='treated',post='policy',structure=S,se='cluster',cluster='id')
    with pytest.raises(ValueError,match='分期'):
        estimate(df,cfg)


def test_hac_rejects_gaps_and_unit_root_status():
    df=pd.read_csv(ROOT/'examples'/'synthetic_time.csv').drop(index=[20])
    cfg=ModelConfig(y='y',x=['x'],se='HAC',structure={'kind':'time','time':'month','frequency':'M'})
    with pytest.raises(ValueError,match='缺口'):
        estimate(df,cfg)
    cfg.se='HC1';r=estimate(df,cfg)
    assert all(t['status']=='条件不足' for t in r['tests'] if t['name'] in ['ADF','KPSS'])


def test_transform_log_winsor_and_impute():
    df=pd.DataFrame({'x':[0,-1,2,3,4,500,np.nan]})
    log,record=transform(df,Transform(op='log',columns=['x']),Structure())
    assert record['detail']['nonpositive_to_missing']==2 and log.log_x.isna().sum()==3
    win,record=transform(df,Transform(op='winsor',columns=['x'],lower=.1,upper=.9),Structure())
    assert win.winsor_x.max()==pytest.approx(df.x.quantile(.9))
    imp,record=transform(df,Transform(op='impute',columns=['x'],method='median'),Structure())
    assert imp.impute_x.iloc[-1]==df.x.median() and pd.isna(df.x.iloc[-1])


def test_pairwise_n_and_spearman():
    df=pd.DataFrame({'a':[1,2,np.nan,4],'b':[2,np.nan,6,8]})
    r=describe(df,method='spearman')
    assert r['pair_n']['a']['b']==2
    assert r['correlation']['a']['b']==pytest.approx(1)


def test_frame_preserves_float_precision():
    df=pd.DataFrame({'x':[np.pi,np.nextafter(1.,2),np.nan],'label':['A','B',None]})
    restored=restore_frame(frame_payload(df))
    np.testing.assert_equal(restored.x.to_numpy(),df.x.to_numpy())


def test_frame_preserves_infinity_and_large_integer():
    df=pd.DataFrame({'id':[2**60+1,2**60+2,2**60+3],'x':[np.inf,-np.inf,np.nan]})
    restored=restore_frame(frame_payload(df))
    pd.testing.assert_frame_equal(restored,df,check_names=False)
