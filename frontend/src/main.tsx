import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  BarChart3,
  Check,
  ChevronDown,
  CircleAlert,
  Database,
  FileText,
  FlaskConical,
  FolderOpen,
  GitCompareArrows,
  History,
  LoaderCircle,
  Play,
  Plus,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Table2,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import "./style.css";

type Structure = {
  kind: string;
  entity: string;
  time: string;
  frequency: string;
  step: number;
};
type Config = {
  name: string;
  model: string;
  mode: string;
  y: string;
  x: string[];
  controls: string[];
  formula: string;
  structure: Structure;
  effects: string;
  se: string;
  cluster: string;
  hac_lags: number;
  treat: string;
  post: string;
  policy_time: string;
  event_study: boolean;
  event_before: number;
  event_after: number;
  event_base: number;
  group: string;
  adf_regression: string;
  adf_autolag: string;
  adf_maxlag: number | null;
  kpss_lags: string;
  gmm: {
    y_lags: number;
    endogenous: string[];
    predetermined: string[];
    exogenous: string[];
    lag_min: number;
    lag_max: number;
    pred_min: number;
    pred_max: number;
    collapse: boolean;
    steps: number;
    time_dummies: boolean;
  };
  sample_ids?: number[] | null;
};
type Column = {
  name: string;
  original: string;
  numeric: boolean;
  dtype: string;
  missing: number;
  missing_pct: number;
  infinite: number;
  nonnumeric: number;
  unique: number;
};
type Dataset = {
  id: string;
  name: string;
  source_id: string;
  rows: number;
  columns: Column[];
  preview: Record<string, unknown>[];
  duplicate_rows: number;
  hash: string;
  sheets: string[];
  sheet: string;
  log: any[];
  panel: any;
};
type Coef = {
  variable: string;
  coefficient: number;
  std_error: number;
  statistic: number;
  p_value: number;
  ci_low: number;
  ci_high: number;
  stars: string;
  period?: number;
  reference?: boolean;
};
type Run = {
  id: string;
  dataset_id: string;
  config: Config;
  coefficients: Coef[];
  nobs: number;
  r2: number | null;
  adjusted_r2: number | null;
  data_hash: string;
  input_rows: number;
  se_note: string;
  formula: string;
  descriptive: any;
  tests: any[];
  warnings: string[];
  event: any;
  heterogeneity: any[];
  heterogeneity_test: any;
  versions: Record<string, string>;
  entities?: number;
  instruments?: number;
  sample_ids: number[] | null;
  absorbed: string[];
  created?: string;
  df_resid: number | null;
  within?: number;
  between?: number;
  overall?: number;
  inclusive?: number;
};
const INITIAL: Config = {
  name: "基准模型",
  model: "ols",
  mode: "form",
  y: "",
  x: [],
  controls: [],
  formula: "",
  structure: {
    kind: "cross",
    entity: "",
    time: "",
    frequency: "numeric",
    step: 1,
  },
  effects: "twoway",
  se: "HC1",
  cluster: "",
  hac_lags: 1,
  treat: "",
  post: "",
  policy_time: "",
  event_study: true,
  event_before: 4,
  event_after: 4,
  event_base: -1,
  group: "",
  adf_regression: "c",
  adf_autolag: "AIC",
  adf_maxlag: null,
  kpss_lags: "auto",
  gmm: {
    y_lags: 1,
    endogenous: [],
    predetermined: [],
    exogenous: [],
    lag_min: 2,
    lag_max: 3,
    pred_min: 1,
    pred_max: 2,
    collapse: true,
    steps: 2,
    time_dummies: true,
  },
};
const MODELS: Record<string, string> = {
  ols: "普通最小二乘 OLS",
  fe: "固定效应 FE",
  did: "双重差分 DID",
  gmm: "系统 GMM",
};
const PAGES = [
  { id: "data", label: "数据", icon: Database },
  { id: "model", label: "模型设定", icon: SlidersHorizontal },
  { id: "results", label: "基准回归", icon: BarChart3 },
  { id: "diagnostics", label: "诊断检验", icon: Activity },
  { id: "compare", label: "稳健性与异质性", icon: GitCompareArrows },
  { id: "export", label: "报告与导出", icon: FileText },
];
let token = sessionStorage.getItem("econ-token") || "";
async function api(
  path: string,
  body?: unknown,
  method?: string,
): Promise<any> {
  const form = body instanceof FormData;
  const res = await fetch("/api" + path, {
    method: method || (body ? "POST" : "GET"),
    headers: {
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...(!form && body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? (form ? (body as FormData) : JSON.stringify(body)) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail),
    );
  }
  const type = res.headers.get("content-type") || "";
  return type.includes("application/json") ? res.json() : res.blob();
}
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const fmt = (v: unknown, digits = 4) =>
  v === null || v === undefined
    ? "—"
    : typeof v === "number"
      ? v !== 0 && Math.abs(v) < 0.0001
        ? v.toExponential(2)
        : v.toLocaleString("en-US", { maximumFractionDigits: digits })
      : String(v);
const pval = (v: number) => (v < 0.0001 ? "< 0.0001" : v.toFixed(4));
function Tag({
  children,
  kind = "neutral",
}: {
  children: React.ReactNode;
  kind?: string;
}) {
  return <span className={"tag " + kind}>{children}</span>;
}
function Select({
  label,
  value,
  onChange,
  options,
  empty = "请选择",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  empty?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {empty && <option value="">{empty}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
function MultiPick({
  label,
  values,
  onChange,
  columns,
}: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
  columns: Column[];
}) {
  const [query, setQuery] = useState("");
  return (
    <div className="field">
      <span>{label}</span>
      <details className="picker">
        <summary>
          {values.length ? values.join(" · ") : "选择变量"}
          <ChevronDown size={14} />
        </summary>
        <div className="picker-body">
          <input
            aria-label={"搜索" + label}
            placeholder="搜索名称"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {columns
            .filter((c) =>
              (c.name + c.original).toLowerCase().includes(query.toLowerCase()),
            )
            .map((c) => (
              <label className="check" key={c.name}>
                <input
                  type="checkbox"
                  checked={values.includes(c.name)}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...values, c.name]
                        : values.filter((v) => v !== c.name),
                    )
                  }
                />
                <span>
                  {c.name}
                  {c.name !== c.original ? " · " + c.original : ""}
                </span>
              </label>
            ))}
        </div>
      </details>
    </div>
  );
}
function Numeric({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <FlaskConical size={38} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Table({
  rows,
  columns,
}: {
  rows: Record<string, unknown>[];
  columns?: string[];
}) {
  const keys = columns || (rows.length ? Object.keys(rows[0]) : []);
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {keys.map((k) => (
                <td
                  key={k}
                  title={typeof r[k] === "string" ? String(r[k]) : undefined}
                >
                  {fmt(r[k])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="muted">暂无可计算的记录</p>}
    </div>
  );
}
function CoefTable({ rows }: { rows: Coef[] }) {
  return (
    <div className="table-scroll">
      <table className="coefficient-table">
        <thead>
          <tr>
            {["变量", "系数", "标准误", "t / z", "p 值", "95% 置信区间"].map(
              (h) => (
                <th key={h}>{h}</th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.variable}>
              <td className={c.variable === "DID_effect" ? "effect" : ""}>
                {c.variable}
              </td>
              <td className="strong">
                {fmt(c.coefficient)}
                <sup>{c.stars}</sup>
              </td>
              <td>{fmt(c.std_error)}</td>
              <td>{fmt(c.statistic)}</td>
              <td>{pval(c.p_value)}</td>
              <td>
                [{fmt(c.ci_low)}, {fmt(c.ci_high)}]
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function CoefPlot({ rows, event = false }: { rows: Coef[]; event?: boolean }) {
  const shown = rows.filter(
    (c) =>
      Number.isFinite(c.ci_low) &&
      Number.isFinite(c.ci_high) &&
      c.ci_low !== null,
  );
  if (!shown.length) return <p>没有可绘制的区间。</p>;
  let lo = Math.min(0, ...shown.map((r) => r.ci_low)),
    hi = Math.max(0, ...shown.map((r) => r.ci_high));
  const span = hi - lo || 1;
  lo -= span * 0.12;
  hi += span * 0.12;
  const h = shown.length * 40 + 52,
    scale = (x: number) => 180 + ((x - lo) / (hi - lo)) * 540;
  return (
    <svg
      className="coef-plot"
      role="img"
      aria-label={event ? "事件研究置信区间图" : "回归系数 95% 置信区间图"}
      viewBox={`0 0 760 ${h}`}
    >
      <line
        x1={scale(0)}
        x2={scale(0)}
        y1={8}
        y2={h - 35}
        stroke="#9aadb8"
        strokeDasharray="4 5"
      />
      {shown.map((r, i) => (
        <g key={r.variable}>
          <text x={5} y={i * 40 + 28}>
            {event
              ? `t = ${r.period}${r.reference ? "（基准）" : ""}`
              : r.variable}
          </text>
          <line
            x1={scale(r.ci_low)}
            x2={scale(r.ci_high)}
            y1={i * 40 + 23}
            y2={i * 40 + 23}
            stroke={r.reference ? "#94a3b8" : "#13838a"}
            strokeWidth={3}
          />
          <circle
            cx={scale(r.coefficient)}
            cy={i * 40 + 23}
            r={5}
            fill={r.reference ? "#94a3b8" : "#0b6970"}
          />
          <title>
            {r.variable}: {fmt(r.coefficient)} [{fmt(r.ci_low)},{" "}
            {fmt(r.ci_high)}]
          </title>
        </g>
      ))}
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <text
          key={v}
          x={180 + v * 540}
          y={h - 5}
          textAnchor="middle"
          className="axis"
        >
          {fmt(lo + v * (hi - lo), 2)}
        </text>
      ))}
    </svg>
  );
}
function Heatmap({ data }: { data: any }) {
  const cols: string[] = data.columns;
  return (
    <div className="table-scroll">
      <table className="heatmap">
        <thead>
          <tr>
            <th></th>
            {cols.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cols.map((a) => (
            <tr key={a}>
              <th>{a}</th>
              {cols.map((b) => {
                const v = data.correlation[a]?.[b] as number | null;
                return (
                  <td
                    key={b}
                    style={{
                      background:
                        v === null
                          ? "#f1f4f6"
                          : v >= 0
                            ? `rgba(9,119,128,${0.06 + v * 0.83})`
                            : `rgba(224,121,77,${0.08 + Math.abs(v) * 0.78})`,
                      color: v !== null && v > 0.65 ? "white" : "#24424b",
                    }}
                    title={`成对有效观测数 N=${data.pair_n[a]?.[b]}`}
                  >
                    {fmt(v, 2)}
                    <small>N={data.pair_n[a]?.[b]}</small>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function TestCard({ test }: { test: any }) {
  return (
    <article className="test-card">
      <div className="row between">
        <h3>{test.name}</h3>
        <Tag
          kind={
            test.status === "已完成"
              ? "success"
              : test.status === "运行失败"
                ? "danger"
                : "neutral"
          }
        >
          {test.status}
        </Tag>
      </div>
      {test.p_value !== undefined && (
        <div className="test-values">
          <span>
            统计量 <b>{fmt(test.statistic)}</b>
          </span>
          <span>
            p 值{" "}
            <b>{test.p_value === null ? "不可计算" : pval(test.p_value)}</b>
          </span>
        </div>
      )}
      <p>{test.note}</p>
      {test.settings && (
        <small>
          设定：{test.settings}；使用滞后 {test.lags}
        </small>
      )}
      {test.table && <Table rows={test.table} />}
      {test.warnings?.map((w: string) => (
        <p className="warning" key={w}>
          {w}
        </p>
      ))}
    </article>
  );
}

function App() {
  const [hosting, setHosting] = useState({
    deployment_mode: "unknown",
    privacy_notice: "正在确认数据处理位置…",
  });
  const cloud = hosting.deployment_mode === "cloud";
  const [ready, setReady] = useState(false),
    [page, setPage] = useState("data"),
    [dataset, setDataset] = useState<Dataset | null>(null),
    [datasets, setDatasets] = useState<any[]>([]),
    [cfg, setCfg] = useState<Config>(INITIAL),
    [runs, setRuns] = useState<Run[]>([]),
    [active, setActive] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [busy, setBusy] = useState(""),
    [job, setJob] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [desc, setDesc] = useState<any>(null),
    [corr, setCorr] = useState("pearson"),
    [descGroup, setDescGroup] = useState(""),
    [comparison, setComparison] = useState<any>(null),
    [processing, setProcessing] = useState(false),
    [transform, setTransform] = useState<any>({
      op: "log",
      columns: [],
      target: "",
      method: "median",
      value: 0,
      periods: 1,
      lower: 0.01,
      upper: 0.99,
      operator: "eq",
      values: [],
    });
  const uploadRef = useRef<HTMLInputElement>(null),
    fileRef = useRef<File | null>(null),
    cancelRef = useRef(false);
  const result = runs.find((r) => r.id === active) || runs.at(-1);
  const columns = dataset?.columns || [],
    numeric = columns.filter((c) => c.numeric),
    options = columns.map((c) => ({
      value: c.name,
      label: c.name + (c.name !== c.original ? " · " + c.original : ""),
    })),
    numOptions = numeric.map((c) => ({
      value: c.name,
      label: c.name + (c.name !== c.original ? " · " + c.original : ""),
    }));
  const stale =
    result &&
    (result.dataset_id !== dataset?.id ||
      JSON.stringify(result.config) !== JSON.stringify(cfg));
  const change = (key: keyof Config, v: any) =>
    setCfg((old) => ({ ...old, [key]: v, sample_ids: null }));
  const structure = (key: keyof Structure, v: any) =>
    change("structure", { ...cfg.structure, [key]: v });
  const gmm = (key: string, v: any) => change("gmm", { ...cfg.gmm, [key]: v });
  async function guard(action: () => Promise<void>, label = "处理中") {
    setError("");
    setBusy(label);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function refreshDatasets() {
    setDatasets(await api("/datasets"));
  }
  async function getDesc(ds: Dataset, method = corr, group = descGroup) {
    try {
      setDesc(
        await api(`/datasets/${ds.id}/describe`, {
          method,
          group,
          columns: ds.columns
            .filter((c) => c.numeric)
            .slice(0, 15)
            .map((c) => c.name),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const health = await api("/health");
        if (alive) setHosting(health);
        if (token) {
          try {
            const all = await api("/datasets");
            if (alive) {
              setDatasets(all);
              setRuns(await api("/runs"));
            }
          } catch {
            token = "";
          }
        }
        if (!token) {
          const s = await api("/session", {});
          token = s.token;
          sessionStorage.setItem("econ-token", token);
        }
        if (alive) setReady(true);
      } catch (e) {
        if (alive) setError("无法连接统计后端：" + (e as Error).message);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [page]);
  useEffect(() => {
    setComparison(null);
  }, [selected.join(",")]);
  useEffect(() => {
    if (dataset) getDesc(dataset, corr, descGroup);
  }, [dataset?.id, corr, descGroup]);
  useEffect(() => {
    if (!job) return;
    let alive = true;
    const poll = async () => {
      try {
        const state = await api("/jobs/" + job);
        if (!alive) return;
        if (state.status === "completed") {
          setRuns((old) => [
            ...old.filter((r) => r.id !== state.result.id),
            state.result,
          ]);
          setActive(state.result.id);
          setSelected((old) =>
            [
              ...old.filter((i) => i !== state.result.id),
              state.result.id,
            ].slice(-8),
          );
          setPage("results");
          setNotice("估计完成 · 已保存数据版本和模型设置");
          setJob("");
          setBusy("");
        } else if (state.status !== "running") {
          setError(state.error || "任务已停止");
          setJob("");
          setBusy("");
        }
      } catch (e) {
        if (alive) {
          setError((e as Error).message);
          setJob("");
          setBusy("");
        }
      }
    };
    const timer = setInterval(poll, 750);
    poll();
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [job]);
  async function upload(file: File, sheet?: string) {
    fileRef.current = file;
    await guard(async () => {
      const fd = new FormData();
      fd.append("file", file);
      if (sheet) fd.append("sheet", sheet);
      const ds = await api("/upload", fd);
      setDataset(ds);
      setDescGroup("");
      setCfg({ ...INITIAL });
      setPage("data");
      await refreshDatasets();
      setNotice(cloud ? "导入成功 · 数据在服务器会话内处理" : "导入成功 · 原始数据保留在本地会话内");
    }, "读取并检查文件");
  }
  async function loadExample(key: string) {
    await guard(async () => {
      const data = await api("/examples/" + key, {});
      setDataset(data.dataset);
      setCfg(data.config);
      setDescGroup("");
      await refreshDatasets();
      setNotice("已载入合成演示数据及示例配置；点击运行获取真实计算结果。");
    }, "读取合成演示数据");
  }
  async function run() {
    if (!dataset) return;
    setError("");
    setBusy("校验 → 估计 → 诊断");
    try {
      const r = await api("/runs", { dataset_id: dataset.id, config: cfg });
      setJob(r.job_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy("");
    }
  }
  async function cancel() {
    cancelRef.current = true;
    if (job) {
      await api("/jobs/" + job, undefined, "DELETE");
      setJob("");
    }
    setBusy("");
    setNotice("计算已取消。");
  }
  async function exportFile(htmlOnly = false) {
    await guard(async () => {
      const ids = selected.length ? selected : result ? [result.id] : [];
      save(
        await api(htmlOnly ? "/report" : "/export", { run_ids: ids }),
        htmlOnly ? "经济学实证报告.html" : "经济学实证分析与复现.zip",
      );
      setNotice("导出成功。文件包含你主动导出的数据，请按需要保存。");
    }, "生成真实结果与复现文件");
  }
  async function commonSample() {
    await guard(async () => {
      const plan = await api("/common-sample", { run_ids: selected });
      setNotice(`共同有效样本 ${plan.nobs} 行，按原规格依次重估。`);
      cancelRef.current = false;
      for (const spec of plan.specifications) {
        if (cancelRef.current) break;
        const { job_id } = await api("/runs", spec);
        let done = false;
        while (!done) {
          await new Promise((resolve) => setTimeout(resolve, 700));
          if (cancelRef.current) {
            await api("/jobs/" + job_id, undefined, "DELETE");
            break;
          }
          const state = await api("/jobs/" + job_id);
          if (state.status === "completed") {
            setRuns((old) => [...old, state.result]);
            done = true;
          } else if (state.status !== "running") throw new Error(state.error);
        }
      }
      setPage("compare");
    }, "共同样本重估");
  }
  function modelChange(model: string) {
    setCfg((old) => ({
      ...old,
      model,
      se:
        model === "fe" || model === "did"
          ? "cluster"
          : model === "gmm"
            ? "HC1"
            : old.se,
      cluster: old.structure.entity,
      structure:
        model !== "ols" ? { ...old.structure, kind: "panel" } : old.structure,
      sample_ids: null,
    }));
  }
  const configPanel = (
    <aside className="config-panel">
      <div className="config-heading">
        <Settings2 size={18} />
        <h2>估计设置</h2>
        <Tag>可编辑</Tag>
      </div>
      <div className="config-scroll">
        <label className="field">
          <span>模型名称</span>
          <input
            value={cfg.name}
            onChange={(e) => change("name", e.target.value)}
            maxLength={80}
          />
        </label>
        <Select
          label="估计方法"
          value={cfg.model}
          onChange={modelChange}
          options={Object.entries(MODELS).map(([value, label]) => ({
            value,
            label,
          }))}
          empty=""
        />
        <div className="segmented">
          <button
            className={cfg.mode === "form" ? "chosen" : ""}
            onClick={() => change("mode", "form")}
          >
            表单配置
          </button>
          <button
            className={cfg.mode === "formula" ? "chosen" : ""}
            onClick={() => change("mode", "formula")}
            disabled={cfg.model === "gmm"}
          >
            公式配置
          </button>
        </div>
        {cfg.mode === "form" ? (
          <>
            <Select
              label="被解释变量 Y"
              value={cfg.y}
              onChange={(v) => change("y", v)}
              options={numOptions}
            />
            <MultiPick
              label="核心解释变量 X"
              values={cfg.x}
              onChange={(v) => change("x", v)}
              columns={numeric}
            />
            <MultiPick
              label="控制变量"
              values={cfg.controls}
              onChange={(v) => change("controls", v)}
              columns={numeric}
            />
          </>
        ) : (
          <label className="field">
            <span>模型公式</span>
            <textarea
              placeholder="y ~ x1 + x2 + log(x3) + x1:x2"
              value={cfg.formula}
              onChange={(e) => change("formula", e.target.value)}
            />
            <small>
              仅支持
              +、+0、log(x)、sqrt(x)、square(x)、a:b、a*b。使用安全变量名。固定效应单独设置。
            </small>
          </label>
        )}
        <details className="config-details" open>
          <summary>数据结构与索引</summary>
          <Select
            label="数据结构"
            value={cfg.structure.kind}
            onChange={(v) => structure("kind", v)}
            options={[
              { value: "cross", label: "截面" },
              { value: "time", label: "时间序列" },
              { value: "panel", label: "面板" },
            ]}
            empty=""
          />
          {cfg.structure.kind === "panel" && (
            <Select
              label="个体 ID"
              value={cfg.structure.entity}
              onChange={(v) => structure("entity", v)}
              options={options}
            />
          )}
          {cfg.structure.kind !== "cross" && (
            <>
              <Select
                label="时间变量"
                value={cfg.structure.time}
                onChange={(v) => structure("time", v)}
                options={options}
              />
              <div className="two-fields">
                <Select
                  label="确认时间频率"
                  value={cfg.structure.frequency}
                  onChange={(v) => structure("frequency", v)}
                  options={[
                    { value: "numeric", label: "数值时间" },
                    { value: "Y", label: "年" },
                    { value: "Q", label: "季" },
                    { value: "M", label: "月" },
                    { value: "D", label: "日" },
                  ]}
                  empty=""
                />
                {cfg.structure.frequency === "numeric" && (
                  <Numeric
                    label="一期的步长"
                    value={cfg.structure.step}
                    min={0.0001}
                    onChange={(v) => structure("step", v)}
                  />
                )}
              </div>
            </>
          )}
        </details>
        {cfg.model === "fe" && (
          <Select
            label="固定效应"
            value={cfg.effects}
            onChange={(v) => change("effects", v)}
            options={[
              { value: "entity", label: "个体固定效应" },
              { value: "time", label: "时间固定效应" },
              { value: "twoway", label: "个体 + 时间双向固定效应" },
            ]}
            empty=""
          />
        )}
        {cfg.model !== "gmm" && (
          <>
            <Select
              label="标准误口径"
              value={cfg.se}
              onChange={(v) => change("se", v)}
              options={(cfg.model === "ols"
                ? ["classic", "HC1", "HC3", "cluster", "HAC"]
                : ["classic", "HC1", "cluster"]
              ).map((value) => ({
                value,
                label: (
                  {
                    classic: "常规标准误",
                    HC1: "HC1 异方差稳健",
                    HC3: "HC3 异方差稳健",
                    cluster: "单向聚类稳健",
                    HAC: "HAC 时间序列稳健",
                  } as Record<string, string>
                )[value],
              }))}
              empty=""
            />
            {cfg.se === "cluster" && (
              <Select
                label="聚类层级"
                value={cfg.cluster}
                onChange={(v) => change("cluster", v)}
                options={options}
              />
            )}
            {cfg.se === "HAC" && (
              <Numeric
                label="HAC 最大滞后"
                value={cfg.hac_lags}
                onChange={(v) => change("hac_lags", v)}
                min={0}
                max={50}
              />
            )}
          </>
        )}
        {cfg.model === "did" && (
          <div className="method-box">
            <h3>共同政策时点 DID</h3>
            <Select
              label="处理组变量（固定 0/1）"
              value={cfg.treat}
              onChange={(v) => change("treat", v)}
              options={numOptions}
            />
            <Select
              label="共同 post 变量（可选）"
              value={cfg.post}
              onChange={(v) => change("post", v)}
              options={numOptions}
              empty="用政策实施时间"
            />
            {!cfg.post && (
              <label className="field">
                <span>政策实施时间</span>
                <input
                  placeholder="例如 2016"
                  value={cfg.policy_time}
                  onChange={(e) => change("policy_time", e.target.value)}
                />
              </label>
            )}
            <label className="check">
              <input
                type="checkbox"
                checked={cfg.event_study}
                onChange={(e) => change("event_study", e.target.checked)}
              />
              运行事件研究
            </label>
            {cfg.event_study && (
              <>
                <div className="two-fields">
                  <Numeric
                    label="政策前期数"
                    value={cfg.event_before}
                    onChange={(v) => change("event_before", v)}
                    min={2}
                    max={10}
                  />
                  <Numeric
                    label="政策后期数"
                    value={cfg.event_after}
                    onChange={(v) => change("event_after", v)}
                    min={1}
                    max={10}
                  />
                </div>
                <Numeric
                  label="基准相对期"
                  value={cfg.event_base}
                  onChange={(v) => change("event_base", v)}
                  min={-10}
                  max={-1}
                />
              </>
            )}
            <small>
              自动使用双向固定效应。端点外相对期合并。分期政策方法尚未实现，会拒绝检测到的不一致处理状态。
            </small>
          </div>
        )}
        {cfg.model === "gmm" && (
          <div className="method-box">
            <h3>动态面板 · 系统 GMM</h3>
            <Numeric
              label="Y 的滞后阶数"
              value={cfg.gmm.y_lags}
              min={1}
              max={4}
              onChange={(v) => gmm("y_lags", v)}
            />
            {(["endogenous", "predetermined", "exogenous"] as const).map(
              (role, i) => (
                <MultiPick
                  key={role}
                  label={["内生变量", "预定变量", "严格外生变量"][i]}
                  values={cfg.gmm[role]}
                  onChange={(v) => gmm(role, v)}
                  columns={numeric.filter((c) =>
                    [...cfg.x, ...cfg.controls].includes(c.name),
                  )}
                />
              ),
            )}
            <small>
              上方所有 X 与控制变量必须各归入一类。Y 自动作为动态内生变量。
            </small>
            <div className="two-fields">
              <Numeric
                label="Y/内生工具最小滞后"
                value={cfg.gmm.lag_min}
                min={2}
                max={10}
                onChange={(v) => gmm("lag_min", v)}
              />
              <Numeric
                label="最大滞后"
                value={cfg.gmm.lag_max}
                min={2}
                max={15}
                onChange={(v) => gmm("lag_max", v)}
              />
            </div>
            <div className="two-fields">
              <Numeric
                label="预定工具最小滞后"
                value={cfg.gmm.pred_min}
                min={1}
                max={10}
                onChange={(v) => gmm("pred_min", v)}
              />
              <Numeric
                label="最大滞后"
                value={cfg.gmm.pred_max}
                min={1}
                max={15}
                onChange={(v) => gmm("pred_max", v)}
              />
            </div>
            <Select
              label="估计步数"
              value={String(cfg.gmm.steps)}
              onChange={(v) => gmm("steps", Number(v))}
              options={[
                { value: "1", label: "一步稳健" },
                { value: "2", label: "两步 + Windmeijer 修正" },
              ]}
              empty=""
            />
            <label className="check">
              <input
                type="checkbox"
                checked={cfg.gmm.collapse}
                onChange={(e) => gmm("collapse", e.target.checked)}
              />
              折叠工具变量
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={cfg.gmm.time_dummies}
                onChange={(e) => gmm("time_dummies", e.target.checked)}
              />
              加入时间虚拟变量
            </label>
          </div>
        )}
        <details className="config-details">
          <summary>异质性与时间序列检验</summary>
          <Select
            label="异质性分组（可选）"
            value={cfg.group}
            onChange={(v) => change("group", v)}
            options={options}
            empty="不运行分组回归"
          />
          <Select
            label="ADF / KPSS 确定性项"
            value={cfg.adf_regression}
            onChange={(v) => change("adf_regression", v)}
            options={[
              { value: "c", label: "常数" },
              { value: "ct", label: "常数 + 趋势" },
            ]}
            empty=""
          />
          <Select
            label="ADF 滞后选择"
            value={cfg.adf_autolag}
            onChange={(v) => change("adf_autolag", v)}
            options={["AIC", "BIC", "t-stat"].map((v) => ({
              value: v,
              label: v,
            }))}
            empty=""
          />
          <label className="field">
            <span>ADF 最大滞后（留空自动）</span>
            <input
              type="number"
              min="0"
              max="40"
              value={cfg.adf_maxlag ?? ""}
              onChange={(e) =>
                change(
                  "adf_maxlag",
                  e.target.value === "" ? null : Number(e.target.value),
                )
              }
            />
          </label>
          <Select
            label="KPSS 带宽选择"
            value={cfg.kpss_lags}
            onChange={(v) => change("kpss_lags", v)}
            options={[
              { value: "auto", label: "自动 auto" },
              { value: "legacy", label: "传统 legacy" },
            ]}
            empty=""
          />
        </details>
      </div>
      <div className="run-footer">
        <button
          className="primary run-button"
          disabled={!dataset || !!busy || !ready}
          onClick={run}
        >
          {busy ? (
            <LoaderCircle size={18} className="spin" />
          ) : (
            <Play size={17} />
          )}
          运行估计
        </button>
        <small>结果来自当前数据和设置 · 不自动筛选显著性</small>
      </div>
    </aside>
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Activity size={25} />
          </div>
          <div>
            <b>经纬</b>
            <small>经济学实证工作台</small>
          </div>
        </div>
        <div className="workspace-label">
          研究工作区 <span>{cloud ? "ONLINE" : hosting.deployment_mode === "local" ? "LOCAL" : "…"}</span>
        </div>
        <nav>
          {PAGES.map((p, i) => (
            <button
              key={p.id}
              className={page === p.id ? "active" : ""}
              onClick={() => setPage(p.id)}
            >
              <p.icon size={19} />
              <span>{p.label}</span>
              <small>0{i + 1}</small>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck size={20} />
          <p>
            {cloud ? "数据在服务器计算" : hosting.deployment_mode === "local" ? "数据在本机计算" : "正在连接统计服务"}<small>无需 API 密钥 · 不发送至 AI 服务</small>
          </p>
          <button
            onClick={() =>
              guard(async () => {
                await api("/session", undefined, "DELETE");
                sessionStorage.removeItem("econ-token");
                token = "";
                location.reload();
              }, "清理会话")
            }
            disabled={!!busy}
            title="删除本会话数据和结果"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            研究工作区 <span>/</span> {PAGES.find((p) => p.id === page)?.label}
          </div>
          <div className="row">
            <button
              className="button small mobile-config"
              onClick={() =>
                document
                  .querySelector(".config-panel")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              配置模型
            </button>
            <Tag kind={ready ? "success" : "neutral"}>
              {ready ? (cloud ? "在线引擎已连接" : "本地引擎已连接") : "连接统计引擎"}
            </Tag>
            <button
              className="button small"
              onClick={() => exportFile()}
              disabled={!runs.length || !!busy}
            >
              <ArrowDownToLine size={15} />
              导出分析
            </button>
          </div>
        </header>
        <div className="workspace-body">
          <main className="main">
            <div className="page-title">
              <div>
                <div className="eyebrow">ECONOMETRICS / WORKBENCH</div>
                <h1>{PAGES.find((p) => p.id === page)?.label}</h1>
              </div>
              {dataset && <Tag>{dataset.name}</Tag>}
            </div>
            {error && (
              <div className="message error" role="alert">
                <CircleAlert size={19} />
                <span>{error}</span>
                <button onClick={() => setError("")} aria-label="关闭错误">
                  <X size={16} />
                </button>
              </div>
            )}
            {notice && (
              <div className="message notice" role="status">
                <Check size={18} />
                <span>{notice}</span>
                <button onClick={() => setNotice("")} aria-label="关闭提示">
                  <X size={16} />
                </button>
              </div>
            )}
            {busy && (
              <div className="message loading" role="status">
                <LoaderCircle className="spin" size={18} />
                <span>{busy}。统计任务最长 180 秒。</span>
                {(job || busy === "共同样本重估") && (
                  <button onClick={cancel}>取消计算</button>
                )}
              </div>
            )}
            {(page === "data" || page === "model") && (
              <>
                <section className="card import-card">
                  <div className="section-heading">
                    <div>
                      <h2>从你的数据开始</h2>
                      <p>CSV、Excel 或 Stata 文件 · 最大 20 MB</p>
                    </div>
                    <FolderOpen size={23} />
                  </div>
                  <div
                    className="upload-zone"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (ready && !busy && e.dataTransfer.files[0])
                        upload(e.dataTransfer.files[0]);
                    }}
                  >
                    <Upload size={25} />
                    <div>
                      <b>拖放文件到这里</b>
                      <span>UTF-8 / GB18030 CSV、.xlsx、.dta</span>
                    </div>
                    <button
                      className="button"
                      disabled={!ready || !!busy}
                      onClick={() => uploadRef.current?.click()}
                    >
                      选择文件
                    </button>
                    <input
                      ref={uploadRef}
                      aria-label="上传数据文件"
                      type="file"
                      accept=".csv,.xlsx,.dta"
                      hidden
                      onChange={(e) => {
                        if (e.target.files?.[0]) upload(e.target.files[0]);
                        e.target.value = "";
                      }}
                    />
                  </div>
                  <p className="hint" role="note">{hosting.privacy_notice}</p>
                  <div className="examples">
                    <span>用合成数据体验</span>
                    {["cross", "time", "panel", "did", "gmm"].map((k, i) => (
                      <button
                        key={k}
                        disabled={!ready || !!busy}
                        onClick={() => loadExample(k)}
                      >
                        {["截面", "时间序列", "不平衡面板", "DID", "GMM"][i]}
                        <ArrowRight size={12} />
                      </button>
                    ))}
                  </div>
                  {datasets.length > 0 && (
                    <Select
                      label="已导入 / 历史数据版本"
                      value={dataset?.id || ""}
                      onChange={(id) =>
                        guard(async () => {
                          const ds = await api(
                            `/datasets/${id}/inspect`,
                            cfg.structure,
                          );
                          setDataset(ds);
                          setDescGroup("");
                        })
                      }
                      options={datasets.map((d) => ({
                        value: d.id,
                        label: `${d.name} · ${d.rows} 行 · ${d.steps} 次处理 · ${d.id.slice(0, 6)}`,
                      }))}
                    />
                  )}
                  {dataset && dataset.sheets.length > 0 && (
                    <Select
                      label="Excel 工作表"
                      value={dataset.sheet}
                      onChange={(v) => {
                        if (fileRef.current) upload(fileRef.current, v);
                        else setError("切换工作表需要重新选择原 Excel 文件。");
                      }}
                      options={dataset.sheets.map((s) => ({
                        value: s,
                        label: s,
                      }))}
                      empty=""
                    />
                  )}
                </section>
                {dataset && page === "data" && (
                  <>
                    <div className="metrics">
                      <Metric
                        label="观测值"
                        value={fmt(dataset.rows, 0)}
                        detail="当前数据版本"
                      />
                      <Metric
                        label="变量"
                        value={String(columns.length)}
                        detail={`${numeric.length} 个数值变量`}
                      />
                      <Metric
                        label="缺失单元格"
                        value={fmt(
                          columns.reduce((s, c) => s + c.missing, 0),
                          0,
                        )}
                        detail="未自动删除或填补"
                      />
                      <Metric
                        label="重复行"
                        value={fmt(dataset.duplicate_rows, 0)}
                        detail="保留并提示"
                      />
                    </div>
                    <section className="card">
                      <div className="section-heading">
                        <div>
                          <h2>结构与质量检查</h2>
                          <p>先在右侧确认数据结构、索引和频率</p>
                        </div>
                        <button
                          className="button small"
                          disabled={!!busy}
                          onClick={() =>
                            guard(
                              async () =>
                                setDataset(
                                  await api(
                                    `/datasets/${dataset.id}/inspect`,
                                    cfg.structure,
                                  ),
                                ),
                              "检查索引与时间",
                            )
                          }
                        >
                          检查索引
                        </button>
                      </div>
                      {dataset.panel && (
                        <div
                          className={
                            dataset.panel.error
                              ? "message error"
                              : "panel-summary"
                          }
                        >
                          {dataset.panel.error ? (
                            dataset.panel.error
                          ) : (
                            <>
                              <Tag>
                                {dataset.panel.balanced ? "平衡" : "不平衡"}
                              </Tag>
                              <span>
                                {dataset.panel.entities} 个体 /{" "}
                                {dataset.panel.periods} 时期
                              </span>
                              <span>
                                {dataset.panel.missing_periods} 个组内缺失时期
                              </span>
                              <span>
                                {dataset.panel.sorted
                                  ? "输入已排序"
                                  : "估计时按索引排序"}
                              </span>
                              <span>{dataset.panel.range?.join(" — ")}</span>
                            </>
                          )}
                        </div>
                      )}
                      <Table
                        rows={columns.map((c) => ({
                          安全变量名: c.name,
                          原始列名: c.original,
                          类型: c.dtype,
                          缺失数: c.missing,
                          "缺失 %": c.missing_pct,
                          无穷值: c.infinite,
                          非数值内容: c.nonnumeric,
                          唯一值: c.unique,
                        }))}
                      />
                    </section>
                    <section className="card">
                      <div className="section-heading">
                        <div>
                          <h2>数据预览</h2>
                          <p>前 25 行 · 原始行号保留用于样本追踪</p>
                        </div>
                        <Table2 size={20} />
                      </div>
                      <Table rows={dataset.preview} />
                    </section>
                    <section className="card">
                      <div className="section-heading">
                        <div>
                          <h2>数据处理</h2>
                          <p>每次处理创建新版本，保留原始列与处理规则</p>
                        </div>
                        <button
                          className="button small"
                          onClick={() => setProcessing(!processing)}
                        >
                          <Plus size={15} />
                          {processing ? "收起操作" : "添加操作"}
                        </button>
                      </div>
                      {processing && (
                        <div className="transform-form">
                          <div className="two-fields">
                            <Select
                              label="处理方式"
                              value={transform.op}
                              onChange={(op) =>
                                setTransform({ ...transform, op, target: "" })
                              }
                              options={Object.entries({
                                log: "自然对数",
                                lag: "滞后项",
                                diff: "差分",
                                center: "中心化",
                                standardize: "标准化",
                                interaction: "交互项",
                                winsor: "分位缩尾",
                                drop_missing: "删除指定变量缺失行",
                                impute: "显式填补缺失",
                                numeric: "转数值（无效内容→缺失）",
                                filter: "条件筛选",
                              }).map(([value, label]) => ({ value, label }))}
                              empty=""
                            />
                            <MultiPick
                              label="处理变量"
                              values={transform.columns}
                              onChange={(v) =>
                                setTransform({ ...transform, columns: v })
                              }
                              columns={columns}
                            />
                          </div>
                          {!["filter", "drop_missing"].includes(
                            transform.op,
                          ) && (
                            <label className="field">
                              <span>新变量名（留空自动命名）</span>
                              <input
                                value={transform.target}
                                placeholder={`${transform.op}_${transform.columns[0] || "x"}`}
                                onChange={(e) =>
                                  setTransform({
                                    ...transform,
                                    target: e.target.value,
                                  })
                                }
                              />
                            </label>
                          )}
                          {["lag", "diff"].includes(transform.op) && (
                            <Numeric
                              label="滞后期数"
                              value={transform.periods}
                              onChange={(v) =>
                                setTransform({ ...transform, periods: v })
                              }
                              min={1}
                              max={20}
                            />
                          )}
                          {transform.op === "winsor" && (
                            <div className="two-fields">
                              <Numeric
                                label="下分位（0 到 1）"
                                value={transform.lower}
                                onChange={(v) =>
                                  setTransform({ ...transform, lower: v })
                                }
                              />
                              <Numeric
                                label="上分位（0 到 1）"
                                value={transform.upper}
                                onChange={(v) =>
                                  setTransform({ ...transform, upper: v })
                                }
                              />
                            </div>
                          )}
                          {transform.op === "impute" && (
                            <>
                              <Select
                                label="填补规则"
                                value={transform.method}
                                onChange={(method) =>
                                  setTransform({ ...transform, method })
                                }
                                options={[
                                  { value: "median", label: "中位数" },
                                  { value: "mean", label: "均值" },
                                  { value: "constant", label: "指定常数" },
                                ]}
                                empty=""
                              />
                              {transform.method === "constant" && (
                                <Numeric
                                  label="填补值"
                                  value={Number(transform.value)}
                                  onChange={(value) =>
                                    setTransform({ ...transform, value })
                                  }
                                />
                              )}
                            </>
                          )}
                          {transform.op === "filter" && (
                            <div className="two-fields">
                              <Select
                                label="条件"
                                value={transform.operator}
                                onChange={(operator) =>
                                  setTransform({ ...transform, operator })
                                }
                                options={Object.entries({
                                  eq: "等于",
                                  ne: "不等于",
                                  gt: "大于",
                                  ge: "大于等于",
                                  lt: "小于",
                                  le: "小于等于",
                                }).map(([value, label]) => ({ value, label }))}
                                empty=""
                              />
                              <label className="field">
                                <span>条件值</span>
                                <input
                                  value={transform.value}
                                  onChange={(e) =>
                                    setTransform({
                                      ...transform,
                                      value: e.target.value,
                                    })
                                  }
                                />
                              </label>
                            </div>
                          )}
                          <button
                            className="primary"
                            disabled={!!busy || !transform.columns.length}
                            onClick={() =>
                              guard(async () => {
                                const ds = await api(
                                  `/datasets/${dataset.id}/transform`,
                                  { transform, structure: cfg.structure },
                                );
                                setDataset(ds);
                                await refreshDatasets();
                                setNotice(
                                  `新版本已保存，受影响 ${ds.log.at(-1).affected} 行。`,
                                );
                              }, "生成数据新版本")
                            }
                          >
                            应用并记录
                          </button>
                        </div>
                      )}
                      {dataset.log.length ? (
                        <div className="logs">
                          {dataset.log.map((l, i) => (
                            <div className="log" key={i}>
                              <span className="step-number">{i + 1}</span>
                              <div>
                                <b>
                                  {l.spec.op} · {l.spec.columns.join(", ")}
                                </b>
                                <p>
                                  {l.before} → {l.after} 行 · 受影响{" "}
                                  {l.affected} 行
                                </p>
                                <details>
                                  <summary>查看规则与阈值</summary>
                                  <pre>{JSON.stringify(l, null, 2)}</pre>
                                </details>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="muted">
                          尚无处理操作。回归会明确记录完整案例规则排除的行数。
                        </p>
                      )}
                    </section>
                  </>
                )}
                {page === "model" && (
                  <section className="card">
                    <h2>运行前说明</h2>
                    <p>
                      在右侧选择变量及估计方法。所有变量和公式会校验类型、共线性、有效样本及必要索引。每次运行保存独立结果，修改设置后需要重新运行。
                    </p>
                    <div className="method-grid">
                      {Object.entries(MODELS).map(([k, v]) => (
                        <button
                          key={k}
                          className={
                            "method-choice " + (cfg.model === k ? "chosen" : "")
                          }
                          onClick={() => modelChange(k)}
                        >
                          <b>{v}</b>
                          <span>
                            {
                              (
                                {
                                  ols: "截面或规则时间序列的条件相关",
                                  fe: "个体、时间与双向固定效应",
                                  did: "共同政策时点、处理组和对照组",
                                  gmm: "动态面板、差分与水平方程矩条件",
                                } as Record<string, string>
                              )[k]
                            }
                          </span>
                        </button>
                      ))}
                    </div>
                  </section>
                )}
                {dataset && desc && page === "data" && (
                  <section className="card">
                    <div className="section-heading">
                      <div>
                        <h2>描述统计与相关性</h2>
                        <p>当前数据版本 · {desc.note}</p>
                      </div>
                    </div>
                    <div className="two-fields">
                      <Select
                        label="相关系数"
                        value={corr}
                        onChange={setCorr}
                        options={[
                          { value: "pearson", label: "Pearson" },
                          { value: "spearman", label: "Spearman" },
                        ]}
                        empty=""
                      />
                      <Select
                        label="分组描述统计"
                        value={descGroup}
                        onChange={setDescGroup}
                        options={options}
                        empty="全样本"
                      />
                    </div>
                    <Table rows={desc.table} />
                    <h3>
                      相关性矩阵 <small>悬停查看每对有效 N</small>
                    </h3>
                    <Heatmap data={desc} />
                    {desc.grouped?.map((g: any) => (
                      <details className="group-details" key={g.group}>
                        <summary>
                          {g.group} · {g.rows} 行
                        </summary>
                        <Table rows={g.table} />
                      </details>
                    ))}
                  </section>
                )}
              </>
            )}
            {!["data", "model"].includes(page) && !result && (
              <Empty title="还没有估计结果">
                导入你的文件或选择合成示例，然后在右侧配置并运行模型。这里不会填入演示数值。
              </Empty>
            )}
            {result && !["data", "model"].includes(page) && (
              <>
                <div className="result-toolbar">
                  <Select
                    label="查看保存的模型"
                    value={result.id}
                    onChange={setActive}
                    options={runs.map((r, i) => ({
                      value: r.id,
                      label: `(${i + 1}) ${r.config.name} · N=${r.nobs}`,
                    }))}
                    empty=""
                  />
                  <button
                    className="button small"
                    onClick={() =>
                      guard(async () => {
                        setCfg(result.config);
                        setDataset(
                          await api(
                            `/datasets/${result.dataset_id}/inspect`,
                            result.config.structure,
                          ),
                        );
                        setNotice("已恢复此结果对应的数据版本和配置。");
                      })
                    }
                  >
                    <History size={15} />
                    恢复配置
                  </button>
                </div>
                {stale && (
                  <div className="message warning">
                    <History size={18} />
                    <span>
                      当前显示的是已保存结果，右侧设置或数据版本已改变。重新运行后才会生成新结果。
                    </span>
                  </div>
                )}
                {page === "results" && (
                  <>
                    <div className="metrics">
                      <Metric
                        label="有效观测"
                        value={fmt(result.nobs, 0)}
                        detail={`输入 ${result.input_rows} 行`}
                      />
                      <Metric
                        label={
                          result.config.model === "gmm" ? "工具变量数" : "R²"
                        }
                        value={fmt(
                          result.config.model === "gmm"
                            ? result.instruments
                            : result.r2,
                        )}
                        detail={
                          result.config.model === "ols"
                            ? "OLS 拟合口径"
                            : result.config.model === "gmm"
                              ? "需防止工具增殖"
                              : "吸收固定效应后"
                        }
                      />
                      <Metric
                        label="估计方法"
                        value={result.config.model.toUpperCase()}
                        detail={
                          result.config.model === "gmm"
                            ? `${result.config.gmm.steps} 步系统 GMM`
                            : result.config.se
                        }
                      />
                      <Metric
                        label="数据版本"
                        value={result.data_hash.slice(0, 8)}
                        detail="SHA-256 指纹"
                      />
                    </div>
                    <section className="card">
                      <div className="section-heading">
                        <div>
                          <h2>{result.config.name}</h2>
                          <p className="formula">{result.formula}</p>
                        </div>
                        <Tag kind="success">已完成</Tag>
                      </div>
                      <CoefTable rows={result.coefficients} />
                      <p className="fit-stats">
                        残差自由度：{fmt(result.df_resid, 0)}
                        {result.config.model === "ols"
                          ? ` · 调整 R²：${fmt(result.adjusted_r2)}`
                          : result.config.model !== "gmm"
                            ? ` · within R²：${fmt(result.within)} · overall R²：${fmt(result.overall)} · inclusive R²：${fmt(result.inclusive)}`
                            : " · GMM 不提供 R²"}
                      </p>
                      <p className="table-note">
                        *** p&lt;0.01，** p&lt;0.05，* p&lt;0.10。
                        {result.se_note}
                      </p>
                    </section>
                    <section className="card">
                      <div className="section-heading">
                        <div>
                          <h2>系数与不确定性</h2>
                          <p>点为估计系数，线为 95% 置信区间</p>
                        </div>
                      </div>
                      <CoefPlot rows={result.coefficients} />
                    </section>
                    {result.event && (
                      <section className="card">
                        <div className="row between">
                          <h2>政策事件研究</h2>
                          <Tag>{result.event.status}</Tag>
                        </div>
                        <p>{result.event.note}</p>
                        {result.event.table && (
                          <CoefPlot rows={result.event.table} event />
                        )}
                        {result.event.joint && (
                          <TestCard test={result.event.joint} />
                        )}
                      </section>
                    )}
                    <section className="card">
                      <h2>有效样本描述统计</h2>
                      <p>{result.descriptive.note}</p>
                      <Table rows={result.descriptive.table} />
                      <Heatmap data={result.descriptive} />
                    </section>
                    <section className="card">
                      <h2>估计说明</h2>
                      <ul className="notes">
                        {result.warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                      <details>
                        <summary>查看完整估计配置与软件版本</summary>
                        <pre>
                          {JSON.stringify(
                            {
                              config: result.config,
                              versions: result.versions,
                            },
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                    </section>
                  </>
                )}
                {page === "diagnostics" && (
                  <>
                    <div className="message info">
                      <Activity size={18} />
                      <span>
                        每项检验单独判断适用性。“未拒绝原假设”不等于证明假设成立。
                      </span>
                    </div>
                    <div className="tests-grid">
                      {result.tests.map((test, i) => (
                        <TestCard key={i} test={test} />
                      ))}
                    </div>
                    {result.event?.joint && (
                      <TestCard test={result.event.joint} />
                    )}
                  </>
                )}
                {(page === "compare" || page === "export") && (
                  <section className="card">
                    <div className="section-heading">
                      <div>
                        <h2>论文回归总表</h2>
                        <p>
                          主动选择要比较或导出的规格，最多 8 个；按运行顺序保留
                        </p>
                      </div>
                      <GitCompareArrows size={22} />
                    </div>
                    <div className="run-list">
                      {runs.map((r, i) => (
                        <label
                          key={r.id}
                          className={
                            "run-item " +
                            (selected.includes(r.id) ? "selected" : "")
                          }
                        >
                          <input
                            type="checkbox"
                            checked={selected.includes(r.id)}
                            onChange={(e) =>
                              setSelected(
                                e.target.checked
                                  ? [...selected, r.id].slice(-8)
                                  : selected.filter((v) => v !== r.id),
                              )
                            }
                          />
                          <span>
                            <b>
                              ({i + 1}) {r.config.name}
                            </b>
                            <small>
                              {r.config.model.toUpperCase()} · {r.config.se} ·
                              N={r.nobs} · 数据 {r.data_hash.slice(0, 8)}
                            </small>
                          </span>
                        </label>
                      ))}
                    </div>
                    <div className="row wrap">
                      <button
                        className="button"
                        disabled={selected.length < 2 || !!busy}
                        onClick={() =>
                          guard(
                            async () =>
                              setComparison(
                                await api("/compare", { run_ids: selected }),
                              ),
                            "生成并列表格",
                          )
                        }
                      >
                        生成比较表
                      </button>
                      <button
                        className="button"
                        disabled={selected.length < 2 || !!busy}
                        onClick={commonSample}
                      >
                        按共同样本重估
                      </button>
                    </div>
                    {comparison && (
                      <>
                        <p className="message info">{comparison.note}</p>
                        <Table rows={comparison.table} />
                        <p className="table-note">
                          *** p&lt;0.01，** p&lt;0.05，*
                          p&lt;0.10；括号内为标准误。
                        </p>
                      </>
                    )}
                  </section>
                )}
                {page === "compare" && (
                  <>
                    <section className="card">
                      <h2>创建稳健性方案</h2>
                      <p>
                        恢复任一已保存模型后，修改名称、标准误、变量或控制变量，再运行一次。缩尾和样本筛选在“数据”页创建新版本。每个方案均独立保存，不以显著性保留作为唯一标准。
                      </p>
                      <button
                        className="button"
                        onClick={() => {
                          change("name", result.config.name + " · 稳健性方案");
                          setPage("model");
                        }}
                      >
                        配置下一方案 <ArrowRight size={15} />
                      </button>
                    </section>
                    <section className="card">
                      <h2>分组异质性</h2>
                      <p>
                        右侧可选择分组变量。比较效应需要差异检验，不能只比较各组
                        p 值。
                      </p>
                      {result.heterogeneity.length ? (
                        result.heterogeneity.map((g: any, i: number) => (
                          <div className="group-result" key={i}>
                            <div className="row between">
                              <h3>
                                {g.group}{" "}
                                <small>
                                  输入 {g.input_rows} 行
                                  {g.result
                                    ? ` / 有效 ${g.result.nobs} 行`
                                    : ""}
                                </small>
                              </h3>
                              <Tag>{g.status}</Tag>
                            </div>
                            {g.result ? (
                              <CoefTable rows={g.result.coefficients} />
                            ) : (
                              <p>{g.note}</p>
                            )}
                          </div>
                        ))
                      ) : (
                        <p className="muted">此模型未运行异质性分析。</p>
                      )}
                      {result.heterogeneity_test && (
                        <TestCard test={result.heterogeneity_test} />
                      )}
                    </section>
                  </>
                )}
                {page === "export" && (
                  <>
                    <section className="card export-card">
                      <div className="export-icon">
                        <ArrowDownToLine size={30} />
                      </div>
                      <h2>把结果和研究过程一起保存</h2>
                      <p>
                        包含真实结果、原始数据的安全列名副本、全部处理规则、模型设置与软件版本。
                      </p>
                      <div className="export-grid">
                        {[
                          "Excel 结果工作簿",
                          "CSV 系数与论文总表",
                          "HTML 研究辅助报告",
                          "LaTeX 回归表",
                          "SVG 系数 / 相关 / 事件图",
                          "独立 Python 复现脚本",
                        ].map((t) => (
                          <span key={t}>
                            <Check size={16} />
                            {t}
                          </span>
                        ))}
                      </div>
                      <div className="row wrap">
                        <button
                          className="primary"
                          disabled={!!busy}
                          onClick={() => exportFile()}
                        >
                          <ArrowDownToLine size={17} />
                          下载完整分析包
                        </button>
                        <button
                          className="button"
                          disabled={!!busy}
                          onClick={() => exportFile(true)}
                        >
                          <FileText size={17} />
                          下载 HTML 报告
                        </button>
                      </div>
                      <small>
                        导出为你选中的模型；未勾选时导出当前模型。会话闲置 2
                        小时或服务停止后数据清除。
                      </small>
                    </section>
                    <section className="card">
                      <h2>报告的边界</h2>
                      <p>
                        报告是规则模板生成的研究辅助初稿。它区分统计显著性与经济意义，不把一般回归写成因果关系，不将不显著写成“没有影响”，也不会给未运行的检验编造结论。
                      </p>
                      <p>
                        DID 需要平行趋势等识别假设；系统 GMM
                        需要有效矩条件与初始条件假设。最终解释仍需结合研究问题、单位和研究设计。
                      </p>
                    </section>
                  </>
                )}
              </>
            )}
            <footer className="main-footer">
              <span>经纬 v0.1.0 · 开源 / {cloud ? "在线" : "本地"} / 可复现</span>
              <span>模型提供证据，研究设计决定解释</span>
            </footer>
          </main>
          {configPanel}
        </div>
      </div>
    </div>
  );
}
function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <b>{value}</b>
      <small>{detail}</small>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
