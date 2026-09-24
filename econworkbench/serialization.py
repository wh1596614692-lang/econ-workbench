import datetime
import math
import numpy as np
import pandas as pd


def clean(value):
    if isinstance(value,dict):
        return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value,(np.integer,)):
        return int(value)
    if isinstance(value,(np.bool_,)):
        return bool(value)
    if isinstance(value,(float,np.floating)):
        return float(value) if math.isfinite(value) else None
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value,(pd.Timestamp,datetime.datetime,datetime.date)):
        return value.isoformat()
    return value


def frame_payload(df):
    def encode(v):
        if isinstance(v,(float,np.floating)) and np.isinf(v):
            return {'__float__':'inf' if v>0 else '-inf'}
        return clean(v)
    rows=[[encode(v) for v in row] for row in zip(*(df[c].tolist() for c in df))]
    return clean({'columns':list(df.columns),'index':list(df.index),'data':rows,
                  'dtypes':{c:str(df[c].dtype) for c in df}})


def restore_frame(payload):
    rows=[[float(v['__float__']) if isinstance(v,dict) and '__float__' in v else v for v in row] for row in payload['data']]
    df=pd.DataFrame(rows,columns=payload['columns'],index=payload['index'])
    for c,dtype in payload['dtypes'].items():
        if dtype.startswith('datetime'):
            df[c]=pd.to_datetime(df[c])
        elif dtype != 'object':
            df[c]=df[c].astype(dtype)
    df.index.name='_row_id'
    return df
