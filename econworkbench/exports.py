import html
import io
import json
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from .serialization import clean, frame_payload

ROOT=Path(__file__).resolve().parents[1]
NOTE='*** p<0.01；** p<0.05；* p<0.10。括号内为所选口径标准误；95% 置信区间。统计显著不等于经济重要或因果成立。'


def dump(obj):
    return json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)


def cell(v):
    if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r')):
        return "'"+v
    return v


def safe_frame(df):
    return df.map(cell)


def paper_table(runs):
    variables=list(dict.fromkeys(c['variable'] for r in runs for c in r['coefficients']))
    table=[]
    for variable in variables:
        row={'变量':variable}
        for i,r in enumerate(runs):
            c=next((c for c in r['coefficients'] if c['variable']==variable),None)
            row[f'({i+1}) {r["config"]["name"]}']=f'{c["coefficient"]:.6f}{c["stars"]}\n({c["std_error"]:.6f})' if c else '—'
        table.append(row)
    for label,key in [('观测数','nobs'),('R²（各模型口径）','r2'),('调整 R²（OLS）','adjusted_r2'),('组内 R²（FE）','within'),('残差自由度','df_resid'),('个体数','entities'),('工具变量数','instruments')]:
        table.append({'变量':label,**{f'({i+1}) {r["config"]["name"]}':r.get(key,'—') for i,r in enumerate(runs)}})
    for label,func in [('模型',lambda r:r['config']['model']),('固定效应',lambda r: 'twoway' if r['config']['model']=='did' else r['config']['effects'] if r['config']['model']=='fe' else '—'),('标准误',lambda r:r['se_note']),('数据指纹',lambda r:r['data_hash'][:12])]:
        table.append({'变量':label,**{f'({i+1}) {r["config"]["name"]}':func(r) for i,r in enumerate(runs)}})
    return pd.DataFrame(table)


def sample_note(runs):
    if any(r.get('sample_ids') is None for r in runs):
        return '含 GMM：系统方程有不同可用样本，不进行单一行集合的共同样本比较。'
    first=runs[0]
    same=all(r['data_hash']==first['data_hash'] and set(r['sample_ids'])==set(first['sample_ids']) for r in runs)
    return '各模型数据版本和有效样本完全一致。' if same else '各模型数据版本或有效样本不同；系数变化可能同时反映样本与规格变化。可主动运行共同样本比较。'


def svg_plot(rows,event=False):
    rows=[r for r in rows if r.get('ci_low') is not None and r.get('ci_high') is not None]
    height=max(180,65+len(rows)*36)
    if not rows:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="100"><text x="20" y="50">No estimable coefficients</text></svg>'
    low=min([0]+[r['ci_low'] for r in rows]); high=max([0]+[r['ci_high'] for r in rows])
    span=high-low or 1
    low-=span*.08; high+=span*.08
    scale=lambda x:230+(x-low)/(high-low)*520
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}" viewBox="0 0 800 {height}"><rect width="100%" height="100%" fill="white"/><g font-family="sans-serif" font-size="13" fill="#263c48">',f'<line x1="{scale(0)}" x2="{scale(0)}" y1="20" y2="{height-30}" stroke="#a5b1bb" stroke-dasharray="4 4"/>']
    for i,r in enumerate(rows):
        y=35+i*36
        name=('t='+str(r['period'])) if event else r['variable']
        parts += [f'<text x="16" y="{y+4}">{html.escape(name)}</text>',f'<line x1="{scale(r["ci_low"])}" x2="{scale(r["ci_high"])}" y1="{y}" y2="{y}" stroke="#0d7377" stroke-width="3"/>',f'<circle cx="{scale(r["coefficient"])}" cy="{y}" r="5" fill="#0d7377"/>']
    parts.append(f'<text x="230" y="{height-8}">{low:.3g}</text><text x="710" y="{height-8}">{high:.3g}</text></g></svg>')
    return ''.join(parts)


def correlation_svg(desc):
    cols=desc['columns']; size=64; n=len(cols); offset=130
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{offset+n*size}" height="{offset+n*size}" font-family="sans-serif" font-size="12"><rect width="100%" height="100%" fill="white"/>']
    for i,a in enumerate(cols):
        parts.append(f'<text x="4" y="{offset+i*size+35}">{html.escape(a)}</text><text transform="translate({offset+i*size+35},120) rotate(-50)">{html.escape(a)}</text>')
        for j,b in enumerate(cols):
            v=desc['correlation'].get(a,{}).get(b)
            valid=v is not None and np.isfinite(v)
            color=f'rgb({int(230-abs(v)*200)},{int(241-abs(v)*125)},{int(244-abs(v)*122)})' if valid and v>=0 else f'rgb(245,{int(231-abs(v)*150)},{int(223-abs(v)*170)})' if valid else '#eee'
            parts.append(f'<rect x="{offset+j*size}" y="{offset+i*size}" width="{size-2}" height="{size-2}" fill="{color}"/><text x="{offset+j*size+12}" y="{offset+i*size+35}" fill="{"white" if valid and v>.65 else "#233"}">{f"{v:.2f}" if valid else "NA"}</text>')
    return ''.join(parts)+'</svg>'


def report(runs,datasets):
    body=['<h1>经济学实证分析 · 研究辅助初稿</h1><p>基于实际输入和计算结果生成。单位未指定时仅按变量的数值单位解释；不自动推断百分比、百分点或经济意义。</p>',paper_table(runs).to_html(index=False,escape=True).replace('\\n','<br>'),f'<p>{html.escape(NOTE)}</p><p>{html.escape(sample_note(runs))}</p>']
    for i,r in enumerate(runs):
        cfg=r['config']; e=html.escape
        body += [f'<h2>({i+1}) {e(cfg["name"])}</h2>',f'<p>模型：{e(cfg["model"])}；{e(r["formula"])}。输入 {r["input_rows"]} 行，有效观测 {r["nobs"]}。{e(r["se_note"])}</p>',f'<p>数据 SHA-256：{e(r["data_hash"])}</p>',f'<pre>{e(dump({"结构":r.get("structure"),"设定":cfg}))}</pre>']
        body += [pd.DataFrame(r['coefficients']).to_html(index=False,escape=True,float_format=lambda x:f'{x:.6g}'),svg_plot(r['coefficients'])]
        for c in r['coefficients']:
            if c['variable'] in {'const','_con'} or c['variable'].startswith('period_'):
                continue
            inference='在 5% 阈值下有统计证据表明该系数偏离零' if c['p_value'] < .05 else '在 5% 阈值下证据不足以拒绝该系数为零，不能据此证明没有影响'
            body.append(f'<p>{e(c["variable"])}：估计值 {c["coefficient"]:.5g}，95% 区间 [{c["ci_low"]:.5g}, {c["ci_high"]:.5g}]；{inference}。其经济意义需结合变量单位、量纲与研究情境判断。</p>')
        body += ['<h3>描述统计</h3>',f'<p>{e(r["descriptive"]["note"])}</p>',pd.DataFrame(r['descriptive']['table']).to_html(index=False,escape=True),'<h3>诊断与适用性</h3>']
        for t in r['tests']:
            body.append(f'<p><b>{e(t["name"])} · {e(t["status"])}</b>：{e(t["note"])} '+ (f'统计量 {t.get("statistic")}，p={t.get("p_value")}' if 'p_value' in t else '')+'</p>')
            if t.get('table'):
                body.append(pd.DataFrame(t['table']).to_html(index=False,escape=True))
        if r.get('event'):
            body.append('<h3>事件研究</h3><pre>'+e(dump(r['event']))+'</pre>')
            if r['event'].get('table'):
                body.append(svg_plot(r['event']['table'],True))
        body.append('<h3>异质性</h3>')
        if not r['heterogeneity']:
            body.append('<p>未运行；不生成结论。</p>')
        for group in r['heterogeneity']:
            body.append(f'<h4>{e(group["group"])} · {e(group["status"])}</h4>')
            if group.get('result'):
                body.append(f'<p>N={group["result"]["nobs"]}</p>'+pd.DataFrame(group['result']['coefficients']).to_html(index=False,escape=True))
            else:
                body.append('<p>'+e(group.get('note',''))+'</p>')
        if r.get('heterogeneity_test'):
            body.append('<pre>'+e(dump(r['heterogeneity_test']))+'</pre>')
        body.append('<h3>限制与后续检查</h3><ul>'+''.join('<li>'+e(w)+'</li>' for w in r['warnings'])+'</ul>')
        body.append('<p>一般回归呈现条件相关关系。请检查研究设计、遗漏变量、测量误差和敏感性；不能靠显著性筛选规格。稳健性比较需同时考虑方向、量级、置信区间及样本变化。</p>')
        ds=datasets[r['dataset_id']]
        body.append('<h3>数据处理与映射</h3><pre>'+e(dump({'name':ds['name'],'mapping':ds['mapping'],'log':ds['log'],'software':r['versions']}))+'</pre>')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>实证分析报告</title><style>body{font:15px/1.65 system-ui,sans-serif;color:#183840;margin:40px auto;max-width:1160px;padding:0 24px}table{border-collapse:collapse;width:100%;font-size:12px;display:block;overflow:auto}td,th{padding:8px;border-bottom:1px solid #dbe4e8;text-align:right;white-space:pre-line}th{background:#eef5f7}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f9;padding:16px;font-size:12px}svg{max-width:100%;height:auto}h2{margin-top:48px;border-bottom:2px solid #17757a}@media print{body{margin:0}h2{break-before:page}}</style><body>'+''.join(body)+'</body></html>'


def latex(runs):
    trans={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    esc=lambda x:''.join(trans.get(c,c) for c in str(x)).replace('\n',' ')
    df=paper_table(runs)
    lines=[r'% UTF-8; compile with XeLaTeX + ctex. All SE definitions included below.',r'\begin{tabular}{l'+'c'*len(runs)+'}',r'\hline',' & '.join(map(esc,df.columns))+r' \\',r'\hline']
    lines += [' & '.join(esc(v) for v in row)+r' \\' for row in df.itertuples(index=False,name=None)]
    lines += [r'\hline',r'\end{tabular}',r'\par '+esc(NOTE),r'\par '+esc(sample_note(runs))]
    return '\n'.join(lines)


REPRODUCE='''# Reproduce every exported run using the SAME statistical core. No server or API key.
from pathlib import Path
import json
import numpy as np
from econworkbench.serialization import restore_frame, clean
from econworkbench.schema import ModelConfig, Transform, Structure
from econworkbench.data import transform
from econworkbench.engine import estimate

root = Path(__file__).resolve().parent
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
results = []
for item in manifest["runs"]:
    folder = root / "data" / item["dataset_id"]
    df = restore_frame(json.loads((folder / "raw.json").read_text(encoding="utf-8")))
    recipe = json.loads((folder / "recipe.json").read_text(encoding="utf-8"))
    for step in recipe:
        df, _ = transform(df, Transform(**step["spec"]), Structure(**step["structure"]))
    result = estimate(df, ModelConfig(**item["config"]))
    expected = json.loads((root / item["result_file"]).read_text(encoding="utf-8"))
    for a, b in zip(result["coefficients"], expected["coefficients"], strict=True):
        assert a["variable"] == b["variable"]
        np.testing.assert_allclose([a[k] for k in ("coefficient","std_error","p_value")],
                                   [b[k] for k in ("coefficient","std_error","p_value")], rtol=1e-6, atol=1e-8)
    assert result["nobs"] == expected["nobs"]
    results.append(clean(result))
    print(item["config"]["name"], "OK", result["nobs"])
(root / "reproduced_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
'''


def build_bundle(runs,datasets):
    buf=io.BytesIO()
    table=paper_table(runs)
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('report.html',report(runs,datasets))
        z.writestr('regression_table.csv',safe_frame(table).to_csv(index=False).encode('utf-8-sig'))
        z.writestr('regression_table.tex',latex(runs))
        xls=io.BytesIO()
        with pd.ExcelWriter(xls,engine='openpyxl') as writer:
            safe_frame(table).to_excel(writer,sheet_name='论文总表',index=False)
            pd.DataFrame({'说明':[NOTE,sample_note(runs),'所有数值均来自 results/*.json；缺失/不适用值留空。']}).to_excel(writer,sheet_name='说明',index=False)
            for i,r in enumerate(runs):
                for label,tab in [('系数',r['coefficients']),('描述',r['descriptive']['table']),('检验',[{k:v for k,v in t.items() if k not in {'table','critical','warnings'}} for t in r['tests']])]:
                    safe_frame(pd.DataFrame(tab)).to_excel(writer,sheet_name=f'{i+1}_{label}',index=False)
                corr=pd.DataFrame(r['descriptive']['correlation'])
                safe_frame(corr.reset_index()).to_excel(writer,sheet_name=f'{i+1}_相关',index=False)
                safe_frame(pd.DataFrame(r['descriptive']['pair_n']).reset_index()).to_excel(writer,sheet_name=f'{i+1}_相关N',index=False)
                if r.get('event',{} ) and r['event'].get('table'):
                    safe_frame(pd.DataFrame(r['event']['table'])).to_excel(writer,sheet_name=f'{i+1}_事件',index=False)
                for j,g in enumerate(r['heterogeneity']):
                    if g.get('result'):
                        safe_frame(pd.DataFrame(g['result']['coefficients'])).to_excel(writer,sheet_name=f'{i+1}_组{j+1}',index=False)
        z.writestr('results.xlsx',xls.getvalue())
        manifest={'runs':[],'note':NOTE,'sample_comparison':sample_note(runs),'contains_user_data':True}
        for i,r in enumerate(runs):
            path=f'results/model_{i+1}.json'
            z.writestr(path,dump(r))
            z.writestr(f'tables/model_{i+1}_coefficients.csv',safe_frame(pd.DataFrame(r['coefficients'])).to_csv(index=False).encode('utf-8-sig'))
            z.writestr(f'figures/model_{i+1}_coefficients.svg',svg_plot(r['coefficients']))
            z.writestr(f'figures/model_{i+1}_correlation.svg',correlation_svg(r['descriptive']))
            if r.get('event') and r['event'].get('table'):
                z.writestr(f'figures/model_{i+1}_events.svg',svg_plot(r['event']['table'],True))
            manifest['runs'].append({'config':r['config'],'dataset_id':r['dataset_id'],'result_file':path})
        for did in set(r['dataset_id'] for r in runs):
            ds=datasets[did]
            z.writestr(f'data/{did}/raw.json',dump(frame_payload(ds['raw'])))
            z.writestr(f'data/{did}/recipe.json',dump(ds['log']))
            z.writestr(f'data/{did}/column_mapping.json',dump(ds['mapping']))
            z.writestr(f'data/{did}/processed.csv',safe_frame(ds['df'].reset_index()).to_csv(index=False).encode('utf-8-sig'))
        z.writestr('manifest.json',dump(manifest))
        z.writestr('reproduce.py',REPRODUCE)
        z.writestr('README.txt','此包包含你主动导出的用户数据。安装 requirements-lock.txt（若存在，否则 requirements.txt），执行 python reproduce.py。脚本逐步重放处理并核对系数/SE/p/N。JSON 保留完整浮点数；CSV/Excel 危险字符串以单引号转义。HTML 可在浏览器打开或打印。')
        for file in ['requirements.txt','requirements-lock.txt','LICENSE','THIRD_PARTY.md']:
            if (ROOT/file).exists():
                z.write(ROOT/file,file)
        for file in ['docs/dependency-licenses.json','docs/METHODS.md']:
            if (ROOT/file).exists():
                z.write(ROOT/file,file)
        for file in (ROOT/'docs'/'third-party').rglob('*'):
            if file.is_file():
                z.write(file,file.relative_to(ROOT).as_posix())
        for name in ['__init__','schema','data','formula','diagnostics','engine','serialization']:
            z.write(ROOT/'econworkbench'/f'{name}.py',f'econworkbench/{name}.py')
    return buf.getvalue()
