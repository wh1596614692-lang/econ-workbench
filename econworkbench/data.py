"""Immutable data operations. No expression evaluation or input filenames on disk."""
import hashlib
import io
import re
import zipfile
import numpy as np
import pandas as pd
from .schema import Structure, Transform

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 150
SAFE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def require_columns(df, columns):
    missing = [x for x in columns if not x or x not in df.columns]
    if missing:
        raise ValueError(f"变量不存在或尚未选择：{', '.join(missing)}。请先选择有效变量。")


def read_upload(content: bytes, filename: str, sheet: str | None = None):
    if len(content) > MAX_BYTES:
        raise ValueError("文件超过 20 MB 限制。")
    suffix = filename.rsplit('.', 1)[-1].lower()
    sheets = []
    stream = io.BytesIO(content)
    if suffix == 'xlsx':
        with zipfile.ZipFile(stream) as z:
            if sum(f.file_size for f in z.infolist()) > 100 * 1024 * 1024:
                raise ValueError("Excel 解压后超过 100 MB 限制。")
        stream.seek(0)
        with pd.ExcelFile(stream, engine='openpyxl') as book:
            sheets = book.sheet_names
            chosen = sheet if sheet is not None else sheets[0]
            if chosen not in sheets:
                raise ValueError("Excel 工作表不存在。")
            df = book.parse(chosen, nrows=MAX_ROWS + 1)
        sheet = chosen
    elif suffix == 'csv':
        try:
            df = pd.read_csv(stream, encoding='utf-8-sig', nrows=MAX_ROWS + 1)
        except UnicodeDecodeError:
            stream.seek(0)
            df = pd.read_csv(stream, encoding='gb18030', nrows=MAX_ROWS + 1)
    elif suffix == 'dta':
        df = pd.read_stata(stream, convert_categoricals=False)
    else:
        raise ValueError("只允许 CSV、.xlsx 和 .dta；不接受宏工作簿。")
    if df.empty or len(df) > MAX_ROWS or len(df.columns) > MAX_COLUMNS or df.size > 2_000_000:
        raise ValueError("数据为空或超过限制（10 万行、150 列、200 万单元格）。")
    mapping, used = {}, set()
    for i, old in enumerate(df.columns):
        name = str(old)
        safe = name if SAFE.fullmatch(name) and name not in {'const', 'log', 'sqrt', 'square'} else f'v{i+1:03d}'
        while safe in used:
            safe += '_v'
        mapping[safe] = name
        used.add(safe)
    df.columns = list(mapping)
    df.index = pd.Index(range(len(df)), name='_row_id')
    return df, mapping, sheets, sheet


def fingerprint(df):
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes() + '|'.join(df.columns).encode()).hexdigest()


def time_ticks(series: pd.Series, s: Structure):
    if series.isna().any():
        raise ValueError("时间索引有缺失，请先明确处理。")
    if s.frequency == 'numeric':
        n = pd.to_numeric(series, errors='coerce') / s.step
        if not np.isfinite(n).all() or not np.allclose(n, np.round(n), atol=1e-7, rtol=0):
            raise ValueError("数值时间必须是所设步长的整数倍。日期请选择年/季/月/日频率。")
        return pd.Series(np.round(n).astype('int64'), index=series.index)
    try:
        # PeriodIndex preserves absent periods instead of compressing a time gap.
        periods = pd.PeriodIndex(series.astype(str), freq=s.frequency)
        return pd.Series(periods.asi8, index=series.index)
    except Exception as e:
        raise ValueError("无法按所选频率解析时间。请使用年份、2020Q1、2020-01 或 ISO 日期。") from e


def indexed(df, s: Structure):
    if s.kind == 'cross' or not s.time:
        raise ValueError("此操作需要确认时间变量和频率。")
    require_columns(df, [s.time] + ([s.entity] if s.kind == 'panel' else []))
    if s.kind == 'panel' and df[s.entity].isna().any():
        raise ValueError("个体索引有缺失。请先明确处理。")
    ticks = time_ticks(df[s.time], s)
    entity = df[s.entity].astype(str) if s.kind == 'panel' else pd.Series('series', index=df.index)
    idx = pd.MultiIndex.from_arrays([entity, ticks], names=['_entity', '_time'])
    if idx.has_duplicates:
        raise ValueError("发现重复个体—时间索引（时间序列为重复时间）。请先聚合或修正，系统不会自动删除。")
    return idx, ticks, entity


def overview(df, mapping, s: Structure | None = None):
    columns = []
    for c in df:
        col = df[c]
        numeric = pd.api.types.is_numeric_dtype(col)
        infs = int(np.isinf(col.astype(float)).sum()) if numeric else 0
        invalid = int((col.notna() & pd.to_numeric(col, errors='coerce').isna()).sum()) if not numeric else 0
        columns.append(dict(name=c, original=mapping.get(c, c), dtype=str(col.dtype), numeric=numeric,
                            missing=int(col.isna().sum()), missing_pct=float(col.isna().mean()*100), infinite=infs,
                            nonnumeric=invalid, unique=int(col.nunique())))
    info = dict(rows=len(df), columns=columns, duplicate_rows=int(df.duplicated().sum()),
                preview=df.head(25).reset_index().to_dict('records'), hash=fingerprint(df), panel=None)
    if s and s.kind != 'cross':
        try:
            idx, ticks, ent = indexed(df, s)
            temp = pd.DataFrame({'t':ticks, 'e':ent})
            grouped = temp.groupby('e').t
            counts = grouped.size()
            gaps = int(sum(int(x.max()-x.min()+1-len(x)) for _, x in grouped))
            balanced = bool(counts.nunique() == 1 and grouped.min().nunique() == 1 and grouped.max().nunique() == 1 and gaps == 0)
            info['panel'] = dict(entities=int(counts.size), periods=int(ticks.nunique()), balanced=balanced,
                                 missing_periods=gaps, min_periods=int(counts.min()), max_periods=int(counts.max()),
                                 sorted=bool(idx.is_monotonic_increasing), frequency=s.frequency, step=s.step,
                                 range=[str(df.loc[ticks.idxmin(),s.time]), str(df.loc[ticks.idxmax(),s.time])])
        except ValueError as e:
            duplicate = 0
            keys = [s.time] + ([s.entity] if s.kind == 'panel' else [])
            if all(k in df for k in keys):
                duplicate = int(df.duplicated(keys, keep=False).sum())
            info['panel'] = {'error':str(e), 'duplicate_index_rows':duplicate}
    return info


def lag_values(df, col, s, periods):
    idx, ticks, ent = indexed(df, s)
    values = pd.Series(df[col].to_numpy(), index=idx)
    lookup = pd.MultiIndex.from_arrays([ent, ticks-periods])
    return pd.Series(values.reindex(lookup).to_numpy(), index=df.index)


def transform(df, spec: Transform, s: Structure):
    require_columns(df, spec.columns)
    out = df.copy(deep=True)
    before = len(df)
    detail, affected = {}, 0
    if not spec.columns:
        raise ValueError("请至少选择一个变量。")
    if spec.op == 'drop_missing':
        out = out.dropna(subset=spec.columns)
        affected = before-len(out)
    elif spec.op == 'filter':
        col = out[spec.columns[0]]
        value = spec.value
        if pd.api.types.is_numeric_dtype(col):
            value = float(value)
        ops = {'eq':col.eq, 'ne':col.ne, 'gt':col.gt, 'ge':col.ge, 'lt':col.lt, 'le':col.le}
        mask = col.isin(spec.values) if spec.operator == 'in' else ops[spec.operator](value)
        out = out.loc[mask & col.notna()]
        affected = before-len(out)
    else:
        target = spec.target or f'{spec.op}_{spec.columns[0]}'
        if not SAFE.fullmatch(target) or target in out:
            raise ValueError("新变量名须为未使用的安全英文名称（字母开头，字母/数字/下划线）。")
        if spec.op == 'numeric':
            result = pd.to_numeric(out[spec.columns[0]], errors='coerce').replace([np.inf, -np.inf], np.nan)
        else:
            for c in spec.columns:
                if not pd.api.types.is_numeric_dtype(out[c]):
                    raise ValueError(f"{c} 不是数值变量；可显式使用“转数值”并查看转换日志。")
                if np.isinf(out[c].astype(float)).any():
                    raise ValueError(f'{c} 存在无穷值；请先用“转数值”显式将无穷值转为缺失，并查看日志。')
            val = out[spec.columns[0]].astype(float)
            if spec.op == 'impute':
                fill = val.mean() if spec.method == 'mean' else val.median() if spec.method == 'median' else float(spec.value)
                if not np.isfinite(fill):
                    raise ValueError("填充值不是有限数值。")
                result = val.fillna(fill)
                detail['fill_value'] = fill
            elif spec.op == 'log':
                result = np.log(val.where(val > 0))
                detail['nonpositive_to_missing'] = int((val <= 0).sum())
            elif spec.op in {'lag', 'diff'}:
                lag = lag_values(out, spec.columns[0], s, spec.periods)
                result = lag if spec.op == 'lag' else val-lag
                detail['rule'] = '按个体和真实时间键精确匹配，不跨时间缺口'
            elif spec.op == 'center':
                result = val-val.mean()
                detail['mean'] = val.mean()
            elif spec.op == 'standardize':
                sd = val.std(ddof=1)
                if not np.isfinite(sd) or sd <= 0:
                    raise ValueError("常数列或样本不足，无法标准化。")
                result = (val-val.mean())/sd
                detail.update(mean=val.mean(), std_ddof1=sd)
            elif spec.op == 'interaction':
                if len(spec.columns) != 2:
                    raise ValueError("交互项需要两个变量。")
                result = val*out[spec.columns[1]]
            elif spec.op == 'winsor':
                if spec.lower >= spec.upper:
                    raise ValueError("缩尾下分位必须小于上分位。")
                lo, hi = val.quantile([spec.lower, spec.upper])
                result = val.clip(lo, hi)
                detail.update(lower_value=lo, upper_value=hi, quantile_method='linear')
            else:
                raise ValueError("不支持的操作。")
        same = result.eq(df[spec.columns[0]]) | (result.isna() & df[spec.columns[0]].isna())
        affected = int((~same).sum())
        detail.update(target=target, missing_after=int(result.isna().sum()), new_missing=int((result.isna() & df[spec.columns[0]].notna()).sum()))
        out[target] = result
    if out.empty:
        raise ValueError("处理后没有观测值，请调整规则。")
    return out, dict(spec=spec.model_dump(), structure=s.model_dump(), before=before, after=len(out), affected=affected, detail=detail)


def describe(df, columns=None, group='', method='pearson'):
    columns = columns or list(df.select_dtypes(include='number').columns)[:40]
    require_columns(df, columns + ([group] if group else []))
    if any(not pd.api.types.is_numeric_dtype(df[c]) for c in columns):
        raise ValueError("描述统计和相关矩阵仅选择数值变量。")
    numeric = df[columns].replace([np.inf,-np.inf], np.nan)
    def summary(d):
        return d.describe(percentiles=[.25,.5,.75]).T.rename(columns={'count':'N'}).reset_index(names='variable').to_dict('records') if len(d.columns) else []
    grouped = []
    if group:
        if df[group].nunique() > 30:
            raise ValueError("分组超过 30 类，请选择分类变量或先筛选。")
        for value, part in df.groupby(group, dropna=False):
            grouped.append({'group':str(value),'rows':len(part), 'table':summary(numeric.loc[part.index])})
    valid = numeric.notna().astype('int64')
    return dict(table=summary(numeric), correlation=numeric.corr(method=method).to_dict(),
                pair_n=(valid.T@valid).to_dict(), grouped=grouped, columns=columns, method=method,
                note='当前数据版本；描述统计逐变量删除缺失，相关矩阵成对删除缺失，无穷值按缺失处理。相关不代表因果。')
