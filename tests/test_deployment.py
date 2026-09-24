from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from econworkbench import api, runtime


def test_cloud_processing_disclosure_and_same_origin(monkeypatch):
    monkeypatch.setattr(runtime,'MODE','cloud')
    with TestClient(api.app) as c:
        response=c.get('/api/health')
        assert response.json()['processing_location']=='server'
        assert '服务器' in response.json()['privacy_notice']
        assert '本机' not in response.json()['privacy_notice']
        assert "connect-src 'self';" in response.headers['content-security-policy']
        assert '127.0.0.1' not in response.headers['content-security-policy']


def test_concurrent_session_capacity(monkeypatch):
    monkeypatch.setattr(runtime,'MAX_SESSIONS',2)
    with TestClient(api.app):
        def attempt(_):
            try:
                return api.create_session()['token']
            except HTTPException as exc:
                assert exc.status_code==429
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            tokens=list(pool.map(attempt,range(12)))
        assert len([token for token in tokens if token])==2
        assert len(api.SESSIONS)==2


def test_data_budget_counts_raw_and_global_sessions(monkeypatch):
    with TestClient(api.app):
        tokens=[api.create_session()['token'] for _ in range(2)]
        a,b=[api.SESSIONS[token] for token in tokens]
        frame=pd.DataFrame({'x':[1.0]*40_000})
        monkeypatch.setattr(runtime,'SESSION_DATA_MB',1)
        monkeypatch.setattr(runtime,'TOTAL_DATA_MB',1)
        first=api.add_dataset(a,frame,{'x':'x'},'test')
        assert api.data_bytes([first])==2*frame.memory_usage(deep=True).sum()
        with pytest.raises(HTTPException) as error:
            api.add_dataset(b,frame.copy(),{'x':'x'},'test')
        assert error.value.status_code==503
        monkeypatch.setattr(runtime,'TOTAL_DATA_MB',10)
        with pytest.raises(ValueError,match='会话数据内存'):
            api.add_dataset(a,frame.copy(),{'x':'x'},'test')
        assert len(a['datasets'])==1 and not b['datasets']
