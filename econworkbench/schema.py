from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Structure(StrictModel):
    kind: Literal["cross", "time", "panel"] = "cross"
    entity: str = ""
    time: str = ""
    frequency: Literal["numeric", "Y", "Q", "M", "D"] = "numeric"
    step: float = Field(1, gt=0)


class Transform(StrictModel):
    op: Literal["drop_missing", "impute", "numeric", "log", "diff", "lag", "center", "standardize", "interaction", "winsor", "filter"]
    columns: list[str] = Field(default_factory=list, max_length=150)
    target: str = ""
    method: Literal["mean", "median", "constant"] = "median"
    value: float | str = 0.0
    periods: int = Field(1, ge=1, le=20)
    lower: float = Field(.01, ge=0, lt=1)
    upper: float = Field(.99, gt=0, le=1)
    operator: Literal["eq", "ne", "gt", "ge", "lt", "le", "in"] = "eq"
    values: list[str | float] = Field(default_factory=list, max_length=1000)


class GMM(StrictModel):
    y_lags: int = Field(1, ge=1, le=4)
    endogenous: list[str] = Field(default_factory=list)
    predetermined: list[str] = Field(default_factory=list)
    exogenous: list[str] = Field(default_factory=list)
    lag_min: int = Field(2, ge=2, le=10)
    lag_max: int = Field(3, ge=2, le=15)
    pred_min: int = Field(1, ge=1, le=10)
    pred_max: int = Field(2, ge=1, le=15)
    collapse: bool = True
    steps: Literal[1, 2] = 2
    time_dummies: bool = True


class ModelConfig(StrictModel):
    name: str = Field("基准模型", max_length=80)
    model: Literal["ols", "fe", "did", "gmm"] = "ols"
    mode: Literal["form", "formula"] = "form"
    y: str = ""
    x: list[str] = Field(default_factory=list, max_length=30)
    controls: list[str] = Field(default_factory=list, max_length=30)
    formula: str = Field("", max_length=2000)
    structure: Structure = Field(default_factory=Structure)
    effects: Literal["entity", "time", "twoway"] = "twoway"
    se: Literal["classic", "HC1", "HC3", "cluster", "HAC"] = "HC1"
    cluster: str = ""
    hac_lags: int = Field(1, ge=0, le=50)
    treat: str = ""
    post: str = ""
    policy_time: str = ""
    event_study: bool = True
    event_before: int = Field(4, ge=2, le=10)
    event_after: int = Field(4, ge=1, le=10)
    event_base: int = Field(-1, ge=-10, le=-1)
    group: str = ""
    adf_regression: Literal["c", "ct"] = "c"
    adf_autolag: Literal["AIC", "BIC", "t-stat"] = "AIC"
    adf_maxlag: int | None = Field(None, ge=0, le=40)
    kpss_lags: Literal["auto", "legacy"] = "auto"
    gmm: GMM = Field(default_factory=GMM)
    sample_ids: list[int] | None = None


class RunRequest(StrictModel):
    dataset_id: str
    config: ModelConfig


class TransformRequest(StrictModel):
    transform: Transform
    structure: Structure = Field(default_factory=Structure)


class CompareRequest(StrictModel):
    run_ids: list[str] = Field(min_length=2, max_length=8)


class DescribeRequest(StrictModel):
    columns: list[str] = Field(default_factory=list, max_length=40)
    group: str = ""
    method: Literal["pearson", "spearman"] = "pearson"
