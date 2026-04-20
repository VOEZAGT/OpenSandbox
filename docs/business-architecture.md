# OpenSandbox 业务逻辑架构图

## 系统总览

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              用户 / AI Agent / 开发者                                      │
└────────────┬──────────────────────────┬──────────────────────────┬──────────────────────┘
             │                          │                          │
             ▼                          ▼                          ▼
┌────────────────────┐   ┌──────────────────────┐   ┌──────────────────────────┐
│     CLI (osb)      │   │   多语言 SDK          │   │     MCP Server           │
│  Python / Click    │   │ Python/Java/TS/C#/Go  │   │  (AI Agent 集成)         │
└────────┬───────────┘   └──────────┬───────────┘   └──────────┬───────────────┘
         │                          │                           │
         └──────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                         OpenSandbox Server (控制平面)                                       │
│                         Python / FastAPI / Port 8080                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ Lifecycle   │  │ Proxy/       │  │ Pool         │  │ Extension    │  │ Auth       │  │
│  │ API         │  │ Endpoint API │  │ API (K8s)    │  │ Service      │  │ Middleware │  │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────────┘  │
│         │                 │                 │                  │                           │
│  ┌──────┴─────────────────┴─────────────────┴──────────────────┴───────────────────────┐  │
│  │                         Service Layer (业务逻辑层)                                    │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────────┐   │  │
│  │  │ Docker Service   │  │ K8s Service      │  │ Runtime Resolver (运行时路由)     │   │  │
│  │  │ (本地容器管理)    │  │ (集群容器管理)    │  │                                  │   │  │
│  │  └────────┬─────────┘  └────────┬─────────┘  └──────────────────────────────────┘   │  │
│  └───────────┼──────────────────────┼───────────────────────────────────────────────────┘  │
└──────────────┼──────────────────────┼─────────────────────────────────────────────────────┘
               │                      │
               ▼                      ▼
┌──────────────────────┐   ┌──────────────────────────────────────────────────────────────┐
│   Docker Engine      │   │              Kubernetes Cluster                               │
│                      │   │  ┌────────────────────────────────────────────────────────┐  │
│  ┌────────────────┐  │   │  │  OpenSandbox Kubernetes Controller (Operator)          │  │
│  │ Sandbox 容器    │  │   │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │  │
│  │ ┌────────────┐ │  │   │  │  │ BatchSandbox │ │ Pool         │ │ Task         │  │  │
│  │ │  execd     │ │  │   │  │  │ Controller   │ │ Controller   │ │ Scheduler    │  │  │
│  │ │  (执行守护) │ │  │   │  │  └──────────────┘ └──────────────┘ └──────────────┘  │  │
│  │ ├────────────┤ │  │   │  └────────────────────────────────────────────────────────┘  │
│  │ │  egress    │ │  │   │                                                              │
│  │ │  (出口控制) │ │  │   │  ┌────────────────────────────────────────────────────────┐  │
│  │ ├────────────┤ │  │   │  │  Sandbox Pod                                           │  │
│  │ │  用户进程   │ │  │   │  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │  │
│  │ └────────────┘ │  │   │  │  │  execd   │  │  egress  │  │  用户应用容器         │ │  │
│  └────────────────┘  │   │  │  │  sidecar  │  │  sidecar │  │                      │ │  │
└──────────────────────┘   │  │  └──────────┘  └──────────┘  └──────────────────────┘ │  │
                           │  └────────────────────────────────────────────────────────┘  │
                           └──────────────────────────────────────────────────────────────┘
                                                    ▲
                                                    │
                           ┌────────────────────────┴──────────────────────────────────────┐
                           │                    Ingress Gateway                             │
                           │              Go / HTTP Reverse Proxy                           │
                           │         Header Mode / URI Mode 路由                            │
                           └───────────────────────────────────────────────────────────────┘
```

---

## 组件详细说明

### 1. SDK 层 (客户端接入)

| 组件 | 语言 | 功能 |
|------|------|------|
| **Sandbox SDK** | Python, Java/Kotlin, TypeScript, C#/.NET, Go | 沙箱生命周期管理 + 文件/命令/代码执行 |
| **Code Interpreter SDK** | Python, Java/Kotlin, TypeScript, C# | 有状态代码执行（Jupyter 协议） |
| **MCP Server** | TypeScript | AI Agent 通过 Model Context Protocol 接入沙箱 |
| **CLI (osb)** | Python (Click) | 终端交互式沙箱管理工具 |

**关键路径**: SDK → HTTP REST → Server Lifecycle API → 获取 sandbox endpoint → SDK → HTTP REST → execd API

---

### 2. Server (控制平面)

**技术栈**: Python 3.10+ / FastAPI / TOML 配置

**内部模块结构**:

```
opensandbox_server/
├── api/
│   ├── lifecycle.py        # 沙箱 CRUD + 状态管理路由
│   ├── proxy.py            # 代理转发路由
│   ├── pool.py             # K8s 资源池管理路由
│   ├── devops.py           # 运维诊断路由
│   └── schema.py           # 请求/响应模型
├── services/
│   ├── sandbox_service.py  # 核心业务逻辑（运行时无关）
│   ├── docker.py           # Docker 运行时实现
│   ├── runtime_resolver.py # 运行时路由选择
│   ├── factory.py          # 服务工厂
│   ├── validators.py       # 请求校验
│   ├── endpoint_auth.py    # Endpoint 鉴权
│   └── k8s/               # Kubernetes 运行时实现
│       ├── kubernetes_service.py    # K8s 主服务
│       ├── batchsandbox_provider.py # BatchSandbox CR 管理
│       ├── agent_sandbox_provider.py# AgentSandbox CR 管理
│       ├── pool_service.py          # 资源池服务
│       ├── informer.py              # K8s Watch 事件监听
│       └── template_manager.py      # 模板渲染
├── middleware/             # 认证、日志等中间件
├── extensions/             # 扩展点（如 auto-renew）
├── integrations/           # 外部集成（Redis 等）
├── config.py              # TOML 配置解析
└── main.py                # FastAPI 应用入口
```

**核心 API 端点**:

| 端点 | 方法 | 功能 |
|------|------|------|
| `/v1/sandboxes` | POST | 创建沙箱（指定镜像、资源、TTL） |
| `/v1/sandboxes` | GET | 列出沙箱（支持过滤、分页） |
| `/v1/sandboxes/{id}` | GET | 获取沙箱详情 |
| `/v1/sandboxes/{id}` | DELETE | 删除沙箱 |
| `/v1/sandboxes/{id}/pause` | POST | 暂停沙箱 |
| `/v1/sandboxes/{id}/resume` | POST | 恢复沙箱 |
| `/v1/sandboxes/{id}/renew-expiration` | POST | 续期 TTL |
| `/v1/sandboxes/{id}/endpoints/{port}` | GET | 获取服务端点 URL |
| `/health` | GET | 健康检查 |

**关键实现路径**:
1. 请求 → Auth Middleware → API Router → Service Layer → Runtime (Docker/K8s)
2. 异步创建: 后台任务拉取镜像 → 注入 execd → 启动容器 → 轮询状态至 Running
3. TTL 管理: 定时器 → 过期检查 → 自动清理（支持重启后恢复）

---

### 3. execd (沙箱内执行守护进程)

**技术栈**: Go 1.24+ / Beego 框架 / 端口 44772

**职责**: 每个沙箱容器内运行的守护进程，将外部 HTTP 请求转化为容器内操作。

```
execd 内部架构:
┌─────────────────────────────────────────────────────────┐
│                    HTTP Server (Beego)                   │
│                      Port 44772                         │
├─────────────┬──────────────┬──────────────┬─────────────┤
│ Code        │ Command      │ Filesystem   │ Metrics     │
│ Controller  │ Controller   │ Controller   │ Controller  │
├─────────────┴──────────────┴──────────────┴─────────────┤
│                   Runtime Dispatcher                     │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌────────────────────────────┐   │
│  │ Jupyter Client   │  │ Shell Executor             │   │
│  │ (WebSocket)      │  │ (Process Groups + Signals) │   │
│  └────────┬─────────┘  └────────────────────────────┘   │
│           │                                             │
│           ▼                                             │
│  ┌──────────────────┐                                   │
│  │ Jupyter Server   │  ← 管理多语言 Kernel              │
│  │ Port 54321       │                                   │
│  └──────────────────┘                                   │
└─────────────────────────────────────────────────────────┘
```

**核心 API**:

| 类别 | 端点 | 功能 |
|------|------|------|
| 代码执行 | `POST /code/context` | 创建执行上下文（绑定语言和 Kernel） |
| 代码执行 | `POST /code` | 执行代码（SSE 流式输出） |
| 代码执行 | `DELETE /code` | 中断执行 |
| 命令执行 | `POST /command` | 执行 Shell 命令（前台/后台） |
| 命令执行 | `GET /command/status/{session}` | 查询命令状态 |
| 文件系统 | `POST /files/upload` | 上传文件（分块） |
| 文件系统 | `GET /files/download` | 下载文件（支持 Range） |
| 文件系统 | `GET /files/search` | Glob 模式搜索文件 |
| 监控 | `GET /metrics` | CPU/内存/运行时间 |

**支持语言**: Python, Java, JavaScript, TypeScript, Go, Bash

**关键实现路径**:
1. 代码执行: HTTP → Controller → Runtime Dispatcher → Jupyter Client (WebSocket) → Kernel → SSE 流式返回
2. 命令执行: HTTP → Controller → Shell Executor → Process Group → stdout/stderr 流式返回
3. PTY 交互: WebSocket → PTY Session → Bash (支持断线重连 replay)

---

### 4. Ingress Gateway (入口网关)

**技术栈**: Go / HTTP Reverse Proxy

**职责**: 将外部请求路由到正确的沙箱实例。

```
外部请求 → Ingress Gateway → 解析目标沙箱 → 反向代理 → Sandbox Pod/Container
```

**路由模式**:

| 模式 | 格式 | 适用场景 |
|------|------|----------|
| **Header** | `OpenSandbox-Ingress-To: <sandbox-id>-<port>` | 可控制 HTTP Header 的客户端 |
| **URI** | `/<sandbox-id>/<port>/<path>` | 无法修改 Header 的场景 |

**关键特性**:
- 监听 Kubernetes CR（BatchSandbox / AgentSandbox）获取沙箱端点
- 支持 HTTP 和 WebSocket 代理
- Auto-Renew on Access (OSEP-0009): 访问时自动续期，通过 Redis 发布 renew-intent 事件

**关键实现路径**:
1. 启动 → 初始化 K8s Client → Watch BatchSandbox/AgentSandbox CR → 构建路由表
2. 请求到达 → 解析 Header/URI → 查找路由表 → 反向代理到目标 Pod
3. 续期: 代理成功 → 发布 renew-intent 到 Redis → Server 消费并续期

---

### 5. Egress Sidecar (出口控制)

**技术栈**: Go / iptables + nftables / DNS Proxy

**职责**: 控制沙箱的出站网络流量，基于 FQDN 的白名单/黑名单策略。

```
沙箱内应用发起网络请求:

┌─────────────────────────────────────────────────────────────┐
│  Sandbox Network Namespace                                  │
│                                                             │
│  App → DNS Query (port 53)                                  │
│         │                                                   │
│         ▼ (iptables REDIRECT)                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Egress DNS Proxy (127.0.0.1:15353)                  │   │
│  │  ┌─────────────────────────────────────────────────┐ │   │
│  │  │ 1. 检查 FQDN 是否在允许列表                      │ │   │
│  │  │ 2. 允许 → 转发到上游 DNS → 返回真实 IP           │ │   │
│  │  │    (dns+nft 模式: 将 IP 加入 nftables allow set) │ │   │
│  │  │ 3. 拒绝 → 返回 NXDOMAIN                         │ │   │
│  │  │    (可选: 触发 deny webhook)                     │ │   │
│  │  └─────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  App → TCP/UDP 连接 (port != 53)                            │
│         │                                                   │
│         ▼ (nftables 检查, dns+nft 模式)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  nftables: 目标 IP 在 allow set 中?                  │   │
│  │  是 → 放行    否 → DROP                              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**运行模式**:

| 模式 | 说明 |
|------|------|
| `dns` | 仅 DNS 代理过滤（默认） |
| `dns+nft` | DNS 代理 + nftables IP 层强制执行 |

**运行时 API** (端口 18080):

| 端点 | 方法 | 功能 |
|------|------|------|
| `/policy` | GET | 获取当前策略 |
| `/policy` | POST | 替换策略（空 body 重置为 deny-all） |
| `/policy` | PATCH | 追加/合并规则 |

**关键实现路径**:
1. 启动 → 读取 `OPENSANDBOX_EGRESS_RULES` 或策略文件 → 配置 iptables 重定向 → 启动 DNS Proxy
2. DNS 请求 → iptables 重定向到 15353 → 策略匹配 → 允许/拒绝
3. dns+nft 模式: 允许的域名解析后 → IP 加入 nftables 动态 set（带 TTL）→ 后续 TCP 连接直接放行

---

### 6. Kubernetes Controller (集群调度)

**技术栈**: Go / Kubernetes Operator / Custom Resources

**自定义资源 (CRD)**:

| CRD | 功能 |
|-----|------|
| **BatchSandbox** | 批量沙箱管理（支持 replicas、TTL、任务调度） |
| **Pool** | 预热资源池（快速分配、自动扩缩） |

**关键特性**:
- 资源池预热: 维护 warm pods，创建沙箱时直接分配，毫秒级交付
- 批量创建: 单次请求创建 N 个沙箱（适用于 RL 训练场景）
- 任务调度: 可选的 Task 模板，支持异构任务分发
- Pod 驱逐: 优雅驱逐 + 自动补充

---

### 7. Sandbox 环境 (Code Interpreter)

**基础镜像**: Ubuntu 24.04 (amd64 + arm64)

**预装环境**:

| 语言 | 版本 | 安装路径 |
|------|------|----------|
| Python | 3.10, 3.11, 3.12, 3.13, 3.14 | `/opt/python/versions` |
| Java | 8, 11, 17, 21 (OpenJDK) | `/usr/lib/jvm` |
| Node.js | 18, 20, 22 | `/opt/node` |
| Go | 1.23, 1.24, 1.25 | `/opt/go` |

**特性**: 运行时版本切换、Jupyter 多语言 Kernel、clone3 兼容性

---

## 核心业务流程

### 流程 1: 创建并使用沙箱（完整链路）

```
1. 用户/Agent 调用 SDK
   sdk.sandbox.create(image="opensandbox/code-interpreter", timeout="30m", resources={cpu: 2, memory: "4Gi"})

2. SDK → Server (POST /v1/sandboxes)
   Server 验证请求 → 选择运行时 (Docker/K8s)

3. Server → Runtime
   Docker: docker create + docker start (注入 execd 二进制)
   K8s: 创建 BatchSandbox CR → Controller 从 Pool 分配 Pod

4. 容器启动
   execd 启动 → Jupyter Server 启动 → 用户 entrypoint 执行
   egress sidecar 启动 → iptables 规则生效

5. Server 返回 sandbox_id + 状态 (Running)

6. SDK 获取 endpoint
   GET /v1/sandboxes/{id}/endpoints/44772 → 返回 execd 访问地址

7. SDK → execd (代码执行)
   POST /code/context → 创建 Python context
   POST /code {code: "print('hello')"} → SSE 流式返回结果

8. TTL 到期 → Server 自动清理容器
```

### 流程 2: 网络策略控制

```
1. 创建沙箱时指定 networkPolicy
   POST /v1/sandboxes { networkPolicy: { defaultAction: "deny", egress: [{action: "allow", target: "*.github.com"}] } }

2. Server 将策略注入 egress sidecar 环境变量 (OPENSANDBOX_EGRESS_RULES)

3. 沙箱内应用尝试访问 api.github.com
   → DNS 查询被 iptables 重定向到 egress proxy
   → 匹配 *.github.com 规则 → 允许 → 返回真实 IP

4. 沙箱内应用尝试访问 evil.com
   → DNS 查询被重定向到 egress proxy
   → 不匹配任何允许规则 → 返回 NXDOMAIN
   → (可选) 触发 deny webhook 通知
```

### 流程 3: Kubernetes 资源池快速交付

```
1. 管理员创建 Pool CR
   Pool: { image: "opensandbox/code-interpreter", minBuffer: 5, maxBuffer: 20, capacity: 100 }

2. Controller 预创建 5 个 warm pods (minBuffer)

3. 用户请求创建沙箱
   POST /v1/sandboxes → Server → K8s Service → 从 Pool 分配已有 Pod

4. Pod 立即可用（无需等待镜像拉取和容器启动）
   交付延迟: 秒级 → 毫秒级

5. Pool Controller 检测到 buffer 减少 → 自动补充新 Pod
```

---

## 安全架构

```
┌─────────────────────────────────────────────────────────────┐
│                      安全层次                                 │
├─────────────────────────────────────────────────────────────┤
│ L1: API 认证     │ OPEN-SANDBOX-API-KEY (Server)            │
│                  │ X-EXECD-ACCESS-TOKEN (execd)             │
├──────────────────┼──────────────────────────────────────────┤
│ L2: 网络隔离     │ Ingress Gateway (入口统一管控)            │
│                  │ Egress Sidecar (出口 FQDN 白名单)        │
│                  │ Bridge 网络模式 (容器间隔离)              │
├──────────────────┼──────────────────────────────────────────┤
│ L3: 运行时隔离   │ gVisor (用户态内核)                      │
│                  │ Kata Containers (轻量级 VM)              │
│                  │ Firecracker microVM                      │
├──────────────────┼──────────────────────────────────────────┤
│ L4: 资源限制     │ CPU/Memory Quota                         │
│                  │ TTL 自动过期                              │
│                  │ Egress 规则数量上限 (MAX_RULES)           │
└──────────────────┴──────────────────────────────────────────┘
```

---

## 技术栈总结

| 组件 | 语言 | 框架 | 通信协议 |
|------|------|------|----------|
| Server | Python 3.10+ | FastAPI | REST / HTTP |
| execd | Go 1.24+ | Beego | REST / SSE / WebSocket |
| Ingress | Go | net/http (reverse proxy) | HTTP / WebSocket |
| Egress | Go | 自研 | DNS / iptables / nftables |
| K8s Controller | Go | controller-runtime | K8s API / CRD |
| CLI | Python | Click | HTTP (调用 Server API) |
| SDKs | 多语言 | 各语言 HTTP 客户端 | REST / SSE |
| Code Interpreter | Shell/Python | Jupyter | Jupyter Wire Protocol |
