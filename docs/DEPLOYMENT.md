# 分享链接的在线部署

推荐首次使用 **Render Docker Web Service**：一个服务同时提供网页和 Python API，平台提供公开 HTTPS 地址，不必购买域名或自己维护 Linux。访客只需浏览器。

**目前是部署准备完成，尚未上线。** 公共网址须在你的账号实际部署成功后获得，不能分享 `127.0.0.1` 或一个编造的域名。

## 推荐配置与费用

根目录 `render.yaml` 指定新加坡、1 CPU / 2 GB 内存（当前 Blueprint ID `1c-2g`）、单实例、单 Python worker，并关闭自动部署。这是**付费实例**，可能另有构建与流量用量费用。请在创建服务时核对平台最新报价并确认预算；准备配置文件本身不会购买资源。

不推荐免费实例作为完整 GMM 的稳定托管方案：免费资源较小且会闲置休眠；本应用内存中的未导出工作会在重启/休眠时丢失。2 GB 是小规模试用起点，不是任何数据量下的性能保证。正式分享前应从访客所在地区验证访问速度。

## 第一次发布

1. 注册/登录 [GitHub](https://github.com/)，创建**私有**仓库，将项目文件放在仓库根目录。根目录应直接含 `Dockerfile` 和 `render.yaml`。不要上传 `node_modules`、`.venv`、自己的研究数据、密钥或 `.env`。
2. 注册/登录 [Render](https://dashboard.render.com/)，连接这个仓库。条款、支付资料和仓库授权由账号持有人操作，不在聊天中发送密码或银行卡信息。
3. 创建 Blueprint，选择仓库并读取 `render.yaml`。确认只创建一个 Web Service，无数据库或额外工作区升级；核对费用后再发布。
4. 等待构建和健康检查成功，复制服务面板实际给出的 HTTPS URL。仓库可以私有，网站仍可公开。
5. 通过下方验收后分享网址。访客无需 GitHub/Render 账号。

如改用普通 Web Service 表单，选择 Docker，健康检查路径 `/api/health`，逐项复制 `render.yaml` 中的环境变量；保持一个实例。容器入口自动读取 `PORT`。

## 资源与隐私

| 环境变量 | 部署值 | 用途 |
| --- | ---: | --- |
| ECON_DEPLOYMENT_MODE | cloud | 显示“上传到服务器计算”，避免误称浏览器本机计算 |
| ECON_MAX_SESSIONS | 6 | 最多保留 6 个浏览器会话 |
| ECON_MAX_CONCURRENT_JOBS | 1 | 一个统计任务执行；其他用户收到忙碌提示并可重试 |
| ECON_SESSION_DATA_MB | 64 | 单会话原始及处理后 DataFrame 预算 |
| ECON_TOTAL_DATA_MB | 256 | 所有会话 DataFrame 总预算，共享原始对象不重复计数 |
| PORT | 8000 | 内部监听端口 |

会话通过随机 token 隔离。闲置两小时、主动清理或服务重启后删除；必须及时导出。统计子进程、结果、依赖和解析器需要额外内存，DataFrame 预算不等于整个服务的硬内存上限。仍限制上传 20 MB、任务 180 秒。分享版默认值与本地默认值不同。

这是小规模匿名分享：知道网址即可使用，网址可以转发，不是密码。不含账户、永久云存储或滥用防护保证。公开推广前应增加边缘限流和相应身份/访问规则。不要承诺网站运营者无法接触服务器上的数据。

不要启用横向扩容或多个 Uvicorn worker；内存会话不跨实例共享。多人规模扩大后需先改为共享会话和外部任务队列。

## 发布验收与更新

在已安装项目依赖的 Python 环境执行，替换为实际网址：

```sh
python scripts/verify_deployment.py https://你的实际服务域名
```

脚本创建自己的会话，用合成数据实际上传 CSV，运行 OLS、FE、DID、系统 GMM，核对 N 和导出包的系数，最后仅删除测试会话。再在浏览器检查上传提示、运行和下载。

代码更新后手动部署；服务重启会清空会话，请先提醒使用者导出。目前未连接 Render 账号，未执行远端容器构建、跨互联网验收或压力测试。已有本地验证见 `VALIDATION.md`。

官方依据（2026-09-24 查阅）：[Blueprint](https://render.com/docs/blueprint-spec)、[Docker](https://render.com/docs/docker)、[Web Service](https://render.com/docs/web-services)、[免费限制](https://render.com/docs/free)。费用以 [价格页](https://render.com/pricing) 和创建服务时报价为准。
