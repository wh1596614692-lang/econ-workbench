"""合成演示数据。仅用于演示/测试，不代表任何真实经济体。种子 20260924。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd


def generate(folder=Path(__file__).parent):
    folder=Path(folder)
    folder.mkdir(exist_ok=True,parents=True)
    rng=np.random.default_rng(20260924)
    n=320
    education=rng.integers(9,21,n).astype(float)
    experience=rng.uniform(0,35,n)
    region=rng.choice(['东部','西部'],n)
    income=2.2+.085*education+.021*experience+.15*(region=='东部')+rng.normal(0,.3,n)
    cross=pd.DataFrame({'log_income':income,'education':education,'experience':experience,'region':region})
    cross.loc[[7,88,203],'experience']=np.nan
    cross.to_csv(folder/'synthetic_cross.csv',index=False,encoding='utf-8-sig')
    t=np.arange(120)
    x=rng.normal(size=120)
    y=np.zeros(120)
    for i in range(1,120):
        y[i]=.65*y[i-1]+.4*x[i]+rng.normal(0,.6)
    ts=pd.DataFrame({'month':pd.period_range('2010-01',periods=120,freq='M').astype(str),'y':y,'x':x})
    ts.to_csv(folder/'synthetic_time.csv',index=False,encoding='utf-8-sig')
    rows=[]
    for i in range(100):
        alpha=rng.normal(0,.6)
        prev=alpha/(1-.45)+rng.normal()
        treat=int(i<50)
        for year in range(2010,2022):
            xx=rng.normal()
            control=rng.normal()
            shock=rng.normal(0,.6)
            dyn=.45*prev+.65*xx+.2*control+alpha+.03*(year-2010)+shock
            outcome=alpha+.75*xx+.2*control+.08*(year-2010)+1.3*treat*(year>=2016)+rng.normal(0,.5)
            rows.append((i,year,outcome,dyn,xx,control,treat,int(year>=2016),'A' if i%2 else 'B',alpha))
            prev=dyn
    panel=pd.DataFrame(rows,columns=['id','year','y','dynamic_y','x','control','treated','post','region','invariant'])
    panel.to_csv(folder/'synthetic_did_gmm.csv',index=False,encoding='utf-8-sig')
    unbalanced=panel.drop(panel.sample(137,random_state=20260924).index)
    unbalanced.to_csv(folder/'synthetic_panel.csv',index=False,encoding='utf-8-sig')
    with pd.ExcelWriter(folder/'synthetic_workbook.xlsx',engine='openpyxl') as w:
        cross.to_excel(w,sheet_name='截面_合成演示数据',index=False)
        panel.to_excel(w,sheet_name='面板_合成演示数据',index=False)
    configs={
      'cross':dict(name='合成截面 · 教育与收入',model='ols',y='log_income',x=['education'],controls=['experience'],se='HC3',group='region'),
      'time':dict(name='合成时间序列',model='ols',y='y',x=['x'],se='HAC',hac_lags=3,structure=dict(kind='time',time='month',frequency='M')),
      'panel':dict(name='合成不平衡面板 · 双向固定效应',model='fe',y='y',x=['x'],controls=['control','invariant'],se='cluster',cluster='id',effects='twoway',structure=dict(kind='panel',entity='id',time='year')),
      'did':dict(name='合成 DID · 共同政策时点',model='did',y='y',controls=['x','control'],se='cluster',cluster='id',treat='treated',policy_time='2016',structure=dict(kind='panel',entity='id',time='year')),
      'gmm':dict(name='合成动态面板 · 系统 GMM',model='gmm',y='dynamic_y',x=['x'],controls=['control'],structure=dict(kind='panel',entity='id',time='year'),gmm=dict(exogenous=['x','control'],lag_min=2,lag_max=3,collapse=True,steps=2,time_dummies=True))
    }
    (folder/'configs.json').write_text(json.dumps(configs,ensure_ascii=False,indent=2),encoding='utf-8')
    return configs


if __name__=='__main__':
    generate()
