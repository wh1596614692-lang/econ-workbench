"""Single-process local server. Data live in isolated, expiring in-memory sessions."""
import asyncio
import contextlib
import hashlib
import html
import json
import os
import secrets
import time
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .schema import RunRequest, TransformRequest, DescribeRequest, Structure, CompareRequest, ModelConfig
from .data import read_upload, overview, transform, describe, MAX_BYTES
from .serialization import clean
from .exports import build_bundle, paper_table, report, sample_note, svg_plot
from .jobs import Job
from . import runtime

ROOT=Path(__file__).resolve().parents[1]
SESSIONS={}
TTL=7200
STATE_LOCK=threading.RLock()


def data_bytes(datasets):
    # Count raw + processed frames once each, including shared immutable sources.
    frames={id(frame):frame for ds in list(datasets) for frame in (ds['raw'],ds['df'])}
    return sum(int(frame.memory_usage(deep=True).sum()) for frame in frames.values())


def purge_session(session):
    for j in session['jobs'].values():
        j.cancel('会话已清理。')


async def maintenance():
    while True:
        await asyncio.sleep(.3)
        for token,s in list(SESSIONS.items()):
            if time.monotonic()-s['used']>TTL:
                purge_session(s)
                SESSIONS.pop(token,None)
            else:
                for jid,j in s['jobs'].items():
                    state=j.poll()
                    if state['status']=='completed' and jid not in s['runs']:
                        result=state['result']
                        result.update(id=jid,dataset_id=j.dataset_id,created=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
                        s['runs'][jid]=result


@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(maintenance())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    for s in SESSIONS.values():
        purge_session(s)
    SESSIONS.clear()


app=FastAPI(title='经纬 · 经济学实证工作台',version='0.1.0',lifespan=lifespan,docs_url=None,redoc_url=None)
app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:5173','http://localhost:5173'],allow_methods=['GET','POST','DELETE'],allow_headers=['Authorization','Content-Type'])


@app.middleware('http')
async def protect(request,call_next):
    size=request.headers.get('content-length')
    if request.method == 'POST' and not size:
        return JSONResponse({'detail':'POST 请求必须包含 Content-Length。'},status_code=411)
    if size and (not size.isdigit() or int(size)>MAX_BYTES+1024*1024):
        return JSONResponse({'detail':'请求体超过限制。'},status_code=413)
    # Uvicorn is bound to loopback by default; request input is never shell code.
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response


@app.exception_handler(ValueError)
async def value_error(request,exc):
    return JSONResponse({'detail':str(exc)},status_code=422)


def session(authorization: str=Header('')):
    token=authorization.removeprefix('Bearer ')
    s=SESSIONS.get(token)
    if not s or time.monotonic()-s['used']>TTL:
        if s:
            purge_session(s)
            SESSIONS.pop(token,None)
        raise HTTPException(401,'会话已过期或无效，请重新导入数据。')
    s['used']=time.monotonic()
    return s


def dataset(s,did):
    if did not in s['datasets']:
        raise HTTPException(404,'当前会话没有此数据版本。')
    return s['datasets'][did]


def metadata(ds,structure=None):
    return clean(dict(id=ds['id'],name=ds['name'],source_id=ds['source_id'],mapping=ds['mapping'],sheets=ds['sheets'],sheet=ds['sheet'],log=ds['log'],**overview(ds['df'],ds['mapping'],structure)))


def add_dataset(s,df,mapping,name,raw=None,log=None,sheets=None,sheet=None,source_id=None):
    with STATE_LOCK:
        if len(s['datasets'])>=25:
            raise ValueError('每会话最多保留 25 个数据版本，请导出后清理会话。')
        did=uuid4().hex
        ds=dict(id=did,name=name,df=df,raw=raw if raw is not None else df.copy(deep=True),mapping=mapping,log=log or [],sheets=sheets or [],sheet=sheet,source_id=source_id or did)
        if data_bytes([*s['datasets'].values(),ds])>runtime.SESSION_DATA_MB*1024*1024:
            raise ValueError(f'会话数据内存超过 {runtime.SESSION_DATA_MB} MB，请导出后清理。')
        all_data=[d for ss in list(SESSIONS.values()) for d in list(ss['datasets'].values())]
        if data_bytes([*all_data,ds])>runtime.TOTAL_DATA_MB*1024*1024:
            raise HTTPException(503,'服务器数据空间暂时不足，请稍后重试或缩小文件。')
        s['datasets'][did]=ds
        return ds


@app.get('/api/health')
def health():
    return {'status':'ok','version':'0.1.0','storage':'memory','ttl_seconds':TTL,**runtime.public_settings()}


@app.get('/docs',include_in_schema=False)
def offline_docs():
    rows=[]
    for path,methods in app.openapi()['paths'].items():
        for method,info in methods.items():
            rows.append('<tr><td>'+html.escape(method.upper())+'</td><td><code>'+html.escape(path)+'</code></td><td>'+html.escape(info.get('summary',''))+'</td></tr>')
    body='<!doctype html><meta charset="utf-8"><title>工作台 API 文档</title><style>body{font:16px/1.7 system-ui;max-width:1000px;margin:40px auto;padding:20px}td{padding:8px 20px;border-bottom:1px solid #ddd}pre{white-space:pre-wrap}</style><h1>经济学实证工作台 API</h1><p>先 POST /api/session 获得 token；其余会话接口使用 Authorization: Bearer TOKEN。JSON 模型定义和参数见 <a href="/openapi.json">完整 OpenAPI schema</a>。上传使用 multipart/form-data；所有 POST 需 Content-Length。</p><table>'+''.join(rows)+'</table>'
    return Response(body,media_type='text/html')


@app.post('/api/session')
def create_session():
    with STATE_LOCK:
        if len(SESSIONS)>=runtime.MAX_SESSIONS:
            raise HTTPException(429,f'实例最多 {runtime.MAX_SESSIONS} 个活跃会话。请清理旧会话或稍后重试。')
        token=secrets.token_urlsafe(32)
        SESSIONS[token]=dict(used=time.monotonic(),datasets={},runs={},jobs={})
        return {'token':token,'ttl_seconds':TTL}


@app.delete('/api/session')
def clear_session(authorization: str=Header(''),s=Depends(session)):
    purge_session(s)
    SESSIONS.pop(authorization.removeprefix('Bearer '),None)
    return {'status':'cleared'}


@app.post('/api/upload')
async def upload(file:UploadFile=File(...),sheet:str|None=Form(None),s=Depends(session)):
    try:
        content=await file.read(MAX_BYTES+1)
    finally:
        await file.close()
    try:
        df,mapping,sheets,chosen=read_upload(content,file.filename or '',sheet)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f'文件无法读取（{type(e).__name__}）。请检查格式、编码、工作表或文件是否损坏。') from e
    # User filename is metadata only; never used as a path or process argument.
    name=(file.filename or 'data')[:160].replace('\\','/').rsplit('/',1)[-1]
    ds=add_dataset(s,df,mapping,name,sheets=sheets,sheet=chosen)
    return metadata(ds)


@app.get('/api/examples')
def examples():
    return [{'key':k,'label':v} for k,v in [('cross','合成演示数据 · 截面'),('time','合成演示数据 · 时间序列'),('panel','合成演示数据 · 不平衡面板'),('did','合成演示数据 · DID'),('gmm','合成演示数据 · 系统 GMM')]]


@app.post('/api/examples/{key}')
def example(key:str,s=Depends(session)):
    files={'cross':'cross','time':'time','panel':'panel','did':'did_gmm','gmm':'did_gmm'}
    if key not in files:
        raise HTTPException(404,'示例不存在。')
    path=ROOT/'examples'/f'synthetic_{files[key]}.csv'
    df,mapping,_,_=read_upload(path.read_bytes(),path.name)
    ds=add_dataset(s,df,mapping,'合成演示数据 · '+key)
    cfg=json.loads((ROOT/'examples'/'configs.json').read_text(encoding='utf-8'))[key]
    return {'dataset':metadata(ds,Structure(**cfg.get('structure',{}))),'config':ModelConfig(**cfg).model_dump()}


@app.get('/api/datasets')
def list_datasets(s=Depends(session)):
    return [dict(id=d['id'],name=d['name'],rows=len(d['df']),steps=len(d['log'])) for d in s['datasets'].values()]


@app.post('/api/datasets/{did}/inspect')
def inspect(did:str,structure:Structure,s=Depends(session)):
    return metadata(dataset(s,did),structure)


@app.post('/api/datasets/{did}/describe')
def describe_data(did:str,body:DescribeRequest,s=Depends(session)):
    return clean(describe(dataset(s,did)['df'],body.columns,body.group,body.method))


@app.post('/api/datasets/{did}/transform')
def process_data(did:str,body:TransformRequest,s=Depends(session)):
    old=dataset(s,did)
    df,log=transform(old['df'],body.transform,body.structure)
    ds=add_dataset(s,df,old['mapping'].copy(),old['name'],raw=old['raw'],log=old['log']+[log],sheets=old['sheets'],sheet=old['sheet'],source_id=old['source_id'])
    return metadata(ds,body.structure)


def start_job(s,ds,cfg):
    with STATE_LOCK:
        if len(s['jobs'])>=30:
            raise HTTPException(429,'每会话最多保留 30 个任务，请导出后清理。')
        if sum(j.state['status']=='running' for ss in list(SESSIONS.values()) for j in list(ss['jobs'].values()))>=runtime.MAX_CONCURRENT_JOBS:
            raise HTTPException(429,f'已有 {runtime.MAX_CONCURRENT_JOBS} 个计算任务，请等待或取消。')
        jid=uuid4().hex
        s['jobs'][jid]=Job(ds['df'],cfg,ds['id'])
        return {'job_id':jid,'status':'running'}


@app.post('/api/runs')
def run(body:RunRequest,s=Depends(session)):
    return start_job(s,dataset(s,body.dataset_id),body.config.model_dump())


@app.get('/api/jobs/{jid}')
def poll_job(jid:str,s=Depends(session)):
    if jid not in s['jobs']:
        raise HTTPException(404,'任务不存在。')
    job=s['jobs'][jid]
    state=job.poll()
    if state['status']=='completed':
        result=state['result']
        result.update(id=jid,dataset_id=job.dataset_id)
        s['runs'][jid]=result
    return clean(state)


@app.delete('/api/jobs/{jid}')
def cancel_job(jid:str,s=Depends(session)):
    if jid not in s['jobs']:
        raise HTTPException(404,'任务不存在。')
    s['jobs'][jid].cancel()
    return s['jobs'][jid].state


@app.get('/api/runs')
def list_runs(s=Depends(session)):
    return clean(list(s['runs'].values()))


def selected_runs(s,ids):
    runs=[s['runs'].get(i) for i in ids]
    if not runs or any(r is None for r in runs):
        raise HTTPException(404,'请选择本会话内已完成的模型。')
    return runs


@app.post('/api/compare')
def compare(body:CompareRequest,s=Depends(session)):
    runs=selected_runs(s,body.run_ids)
    return clean({'table':paper_table(runs).to_dict('records'),'note':sample_note(runs)})


@app.post('/api/common-sample')
def common_sample(body:CompareRequest,s=Depends(session)):
    runs=selected_runs(s,body.run_ids)
    if any(r.get('sample_ids') is None for r in runs):
        raise ValueError('GMM 具有不同方程/工具样本，暂不提供共同样本重估。')
    sources={dataset(s,r['dataset_id'])['source_id'] for r in runs}
    if len(sources)!=1:
        raise ValueError('共同样本需要来自同一次导入的数据版本，不能按不同文件的行号匹配。')
    ids=sorted(set.intersection(*[set(r['sample_ids']) for r in runs]))
    if len(ids)<6:
        raise ValueError('共同样本少于 6 行。')
    # Client dispatches these reviewable configurations sequentially through /runs.
    return {'nobs':len(ids),'specifications':[{'dataset_id':r['dataset_id'],'config':dict(r['config'],sample_ids=ids,name=r['config']['name']+' · 共同样本')} for r in runs]}


@app.post('/api/export')
def export(body:dict,s=Depends(session)):
    ids=body.get('run_ids',[])
    if len(ids)>8:
        raise ValueError('一次最多导出 8 个模型。')
    runs=selected_runs(s,ids)
    return Response(build_bundle(runs,s['datasets']),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="econ-analysis.zip"'})


@app.post('/api/report')
def html_report(body:dict,s=Depends(session)):
    runs=selected_runs(s,body.get('run_ids',[]))
    return Response(report(runs,s['datasets']),media_type='text/html',headers={'Content-Disposition':'attachment; filename="econ-report.html"'})


dist=ROOT/'frontend'/'dist'
if dist.exists():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/')
    def index():
        return FileResponse(dist/'index.html')
else:
    @app.get('/')
    def index():
        return {'message':'前端尚未构建，请在 frontend 执行 pnpm install && pnpm build，或使用 Vite 开发服务器。','docs':'/docs'}
