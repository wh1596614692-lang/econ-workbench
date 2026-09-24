"""A small allowlisted grammar; never passes user text to eval/patsy/formulaic."""
import re
import numpy as np
import pandas as pd
from .data import require_columns

NAME = r'[A-Za-z][A-Za-z0-9_]*'
ATOM = re.compile(rf'^(?:({NAME})|(log|sqrt|square)\(({NAME})\))$')


def design(df, cfg):
    if cfg.mode == 'formula':
        parts = cfg.formula.split('~')
        if len(parts) != 2 or not re.fullmatch(NAME, parts[0].strip()):
            raise ValueError("公式格式：y ~ x1 + x2 + log(x3) + x1:x2。固定效应请在表单设置。")
        y = parts[0].strip()
        raw = [t.strip().replace(' ', '') for t in parts[1].split('+')]
        if not raw or any(not t for t in raw):
            raise ValueError("公式存在空项。")
    else:
        y = cfg.y
        raw = cfg.x + cfg.controls
    require_columns(df, [y])
    intercept = '0' not in raw
    terms = []
    seen_raw = set()
    for t in raw:
        if t in seen_raw:
            raise ValueError(f"变量或公式项重复：{t}")
        seen_raw.add(t)
        if t in {'0','1'}:
            continue
        if '*' in t:
            pair = t.split('*')
            if len(pair) != 2 or any(not ATOM.fullmatch(a) for a in pair):
                raise ValueError("* 只支持两个简单项，例如 x1*x2。")
            expanded = pair + [':'.join(pair)]
        else:
            expanded = [t]
        for item in expanded:
            if item not in terms:
                terms.append(item)
    if not terms and cfg.model not in {'did','gmm'}:
        raise ValueError("请至少选择一个解释变量。")
    used = {y}
    warnings = []
    def atom(t):
        m = ATOM.fullmatch(t)
        if not m:
            raise ValueError(f"不支持的公式项：{t}。仅允许变量、log(x)、sqrt(x)、square(x)、a:b、a*b 和 +0。")
        name = m[1] or m[3]
        require_columns(df, [name])
        used.add(name)
        if not pd.api.types.is_numeric_dtype(df[name]):
            raise ValueError(f"{name} 不是数值变量。请先转换或创建虚拟变量。")
        v = df[name].astype(float)
        if m[2] == 'log':
            count = int((v <= 0).sum())
            if count:
                warnings.append(f'log({name}) 的 {count} 个非正值被标为缺失；回归完整案例规则将排除这些行。')
            return np.log(v.where(v > 0))
        if m[2] == 'sqrt':
            return np.sqrt(v.where(v >= 0))
        return v**2 if m[2] == 'square' else v
    X = pd.DataFrame(index=df.index)
    if intercept:
        X['const'] = 1.
    for t in terms:
        pair = t.split(':')
        if len(pair) > 2:
            raise ValueError("最多允许二阶交互项。")
        X[t] = atom(pair[0]) if len(pair) == 1 else atom(pair[0])*atom(pair[1])
    if not pd.api.types.is_numeric_dtype(df[y]):
        raise ValueError("被解释变量必须为数值类型。")
    if y in terms:
        raise ValueError("被解释变量不能同时作为当期解释变量。")
    return y, X, sorted(used), warnings
