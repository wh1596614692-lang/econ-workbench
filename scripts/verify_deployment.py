"""Verify a deployment with synthetic data; delete only the session created here."""
import argparse
import io
import json
import time
import zipfile
from pathlib import Path
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--expect-mode',choices=['local','cloud'],default='cloud')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with httpx.Client(base_url=args.url.rstrip('/'),timeout=60) as client:
        def request(method,path,**kwargs):
            response=client.request(method,path,**kwargs)
            response.raise_for_status()
            return response
        assert request('GET','/api/health').json()['deployment_mode']==args.expect_mode
        request('GET','/')
        token=request('POST','/api/session',json={}).json()['token']
        client.headers['Authorization']='Bearer '+token
        try:
            runs=[]
            for key in ['cross','panel','did','gmm']:
                if key=='cross':
                    payload=(root/'examples'/'synthetic_cross.csv').read_bytes()
                    ds=request('POST','/api/upload',files={'file':('synthetic_cross.csv',payload,'text/csv')}).json()
                    cfg=json.loads((root/'examples'/'configs.json').read_text(encoding='utf-8'))[key]
                else:
                    example=request('POST','/api/examples/'+key,json={}).json()
                    ds,cfg=example['dataset'],example['config']
                job=request('POST','/api/runs',json={'dataset_id':ds['id'],'config':cfg}).json()['job_id']
                deadline=time.monotonic()+200
                while time.monotonic()<deadline:
                    state=request('GET','/api/jobs/'+job).json()
                    if state['status']!='running':
                        break
                    time.sleep(.25)
                assert state['status']=='completed',state
                result=state['result']
                assert result['nobs']=={'cross':317,'panel':1063,'did':1200,'gmm':1000}[key]
                runs.append(result)
                print(key,'OK; N =',result['nobs'],flush=True)
            bundle=request('POST','/api/export',json={'run_ids':[r['id'] for r in runs]}).content
            with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                assert archive.testzip() is None
                assert 'results.xlsx' in archive.namelist() and 'reproduce.py' in archive.namelist()
                for i,result in enumerate(runs,1):
                    assert json.loads(archive.read(f'results/model_{i}.json'))['coefficients']==result['coefficients']
            print('Upload, four estimators, diagnostics and ZIP export: OK',flush=True)
        finally:
            request('DELETE','/api/session')


if __name__=='__main__':
    main()
