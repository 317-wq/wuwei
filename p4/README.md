# P4：FastAPI 流式 API 演示

> 笔试题实现：用 **FastAPI** 实现一个可以直接运行的流式 API Demo。
> 这里的 streaming 指服务端以分块传输 / SSE 的方式持续向客户端推送响应（LLM 对话的典型形态）。
> 不依赖任何外部模型服务，一条命令即可启动，自带可视化演示页、Swagger 文档和 18 个自动化测试。

演示页（启动后访问 <http://127.0.0.1:8000/>）可以实时看到文字逐字出现，
并对比 **SSE / NDJSON / 一次性 JSON** 三种返回方式的差异。

---

## 1. 题目要求与实现对照

| 要求 | 实现 | 位置 |
| --- | --- | --- |
| 使用 FastAPI | FastAPI + Uvicorn，Pydantic v2 做参数校验 | `app/main.py`、`app/models.py` |
| 实现流式 API | SSE、NDJSON、纯文本三种流式响应 | `app/main.py`、`app/service.py` |
| 有演示效果 | 异步生成器逐 token 输出，可调速度；自带前端页面 | `app/llm.py`、`static/index.html` |
| 代码注释 | 关键逻辑均配有中文注释（SSE 帧格式、心跳、断连、TTFT 等） | 全部源码 |
| 可直接运行 | `requirements.txt` + 启动命令 + Dockerfile | 见第 4 节 |

## 2. 功能一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 可视化演示页（原生 HTML/JS，无构建步骤） |
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/chat/stream` | **SSE** 流式对话，`text/event-stream` |
| `POST` | `/api/chat/stream/ndjson` | **NDJSON** 流式对话，`application/x-ndjson` |
| `GET` | `/api/stream/echo` | 纯文本分块输出，最简单的 `StreamingResponse` 示例 |
| `POST` | `/api/chat` | 非流式对照接口，一次性返回完整 JSON |
| `GET` | `/docs` | Swagger UI（FastAPI 自动生成） |

三种流式形态的取舍：

| 方案 | 优点 | 局限 | 适用场景 |
| --- | --- | --- | --- |
| SSE | 协议简单、浏览器 `EventSource` 原生支持、自带重连语义 | 标准 `EventSource` 只支持 GET；单向 | LLM 对话、通知、日志推送 |
| NDJSON | 一行一个 JSON，任何语言都好解析 | 没有统一的浏览器 API，需要自己按行切分 | 服务间数据流、批量导出 |
| 纯文本分块 | 最直观，`curl -N` 就能看 | 无事件结构，错误/元信息不好表达 | 简单日志、进度条 |

> 本题是「客户端发一个请求，服务端持续返回」的单向流，用 HTTP 流式响应即可，
> 不需要引入 WebSocket 的双向通道。

## 3. 目录结构

```text
p4/
├── app/
│   ├── main.py        # FastAPI 应用、路由、CORS、静态页、异常处理
│   ├── service.py     # 核心：聊天事件流（start/ping/token/usage/done/error）
│   ├── llm.py         # 假模型：把固定文案切成 token 逐个产出
│   ├── sse.py         # SSE / NDJSON 协议帧编码
│   ├── models.py      # Pydantic 请求/响应模型
│   └── config.py      # 环境变量配置
├── static/
│   └── index.html     # 可视化演示页（SSE/NDJSON/JSON 对比、TTFT、原始事件）
├── tests/
│   └── test_api.py    # 18 个接口/异常/断连测试
├── api.http           # IDEA / VS Code REST Client 可直接执行的请求集
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── Dockerfile
└── README.md
```

## 4. 快速开始

要求 Python 3.10+（开发和测试使用 Python 3.12）。

```bash
cd p4

# 1. 创建虚拟环境（可选，但推荐）
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
uvicorn app.main:app --reload --port 8000
```

也可以直接：

```bash
python -m app.main
```

启动后：

- 演示页：<http://127.0.0.1:8000/>
- Swagger：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

Docker 方式：

```bash
docker build -t fastapi-stream-demo .
docker run --rm -p 8000:8000 fastapi-stream-demo
```

## 5. 接口说明

### 5.1 `POST /api/chat/stream`（SSE）

请求体（`Content-Type: application/json`）：

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `prompt` | string | 必填 | 问题，1 ~ 2000 字符，不能为空白 |
| `model` | string | `demo-1` | 模型名（演示用） |
| `max_tokens` | int | `300` | 最多生成 token 数，1 ~ 512 |
| `token_delay_ms` | int \| null | `20` | 每个 token 的间隔，可覆盖默认值，0 表示全速 |
| `first_token_delay_ms` | int \| null | `500` | 首 token 前的等待，模拟 prefill/排队，最大 10000 |

请求示例：

```json
{
  "prompt": "用三句话解释 FastAPI 的流式响应是怎么实现的",
  "max_tokens": 300,
  "token_delay_ms": 20,
  "first_token_delay_ms": 500
}
```

响应头：

```text
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-transform
X-Accel-Buffering: no
X-Request-ID: req_4c826ad87aac
```

事件顺序：`start` →（`ping`）→（`token`）→ `usage` → `done`；
如果生成中途失败，`token` 之后会收到 `error`，不会再收到 `done`。

| 事件 | 数据 | 说明 |
| --- | --- | --- |
| `start` | `request_id`、`model`、`created`、`max_tokens` | 连接建立，开始生成 |
| `ping` | `request_id`、`ts` | 心跳；仅在首 token 等待超过心跳周期时出现 |
| `token` | `index`、`delta` | 增量文本；`id` 严格递增 |
| `usage` | `usage`、`ttft_ms`、`elapsed_ms`、`tokens_per_second` | 结束前的统计 |
| `done` | `finish_reason`（`stop` / `length`） | 正常结束 |
| `error` | `code`、`message` | 流内错误，终止本次流 |

原始帧示例：

```text
retry: 3000

id: 0
event: start
data: {"request_id":"req_4c826ad87aac","model":"demo-1","created":1794393158,"max_tokens":8}

id: 1
event: token
data: {"index":0,"delta":"关"}

id: 2
event: token
data: {"index":1,"delta":"于"}

id: 9
event: usage
data: {"request_id":"req_4c826ad87aac","usage":{"prompt_tokens":3,"completion_tokens":8,"total_tokens":11},"ttft_ms":302.5,"elapsed_ms":1527.1,"tokens_per_second":6.53}

id: 10
event: done
data: {"request_id":"req_4c826ad87aac","finish_reason":"length","created":1794393158}
```

### 5.2 `POST /api/chat/stream/ndjson`（NDJSON）

请求体与 SSE 接口完全一致，响应头为 `Content-Type: application/x-ndjson`。
每行是一个完整 JSON：

```text
{"event":"start","data":{"request_id":"req_e2ba8911604c","model":"demo-1","created":1794393163,"max_tokens":5}}
{"event":"token","data":{"index":0,"delta":"你"}}
{"event":"token","data":{"index":1,"delta":"问"}}
{"event":"usage","data":{"request_id":"req_e2ba8911604c","usage":{"prompt_tokens":3,"completion_tokens":5,"total_tokens":8},"ttft_ms":102.5,"elapsed_ms":610.9,"tokens_per_second":9.83}}
{"event":"done","data":{"request_id":"req_e2ba8911604c","finish_reason":"length","created":1794393163}}
```

> `finish_reason=length` 表示被 `max_tokens` 截断，`stop` 表示自然结束。

### 5.3 `GET /api/stream/echo`（纯文本分块）

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `text` | `Hello, streaming world!` | 要输出的文本，最长 200 字符 |
| `repeat` | `3` | 重复行数，1 ~ 20 |
| `interval_ms` | `120` | 每个字符的间隔，0 ~ 1000 毫秒 |

响应为 `text/plain; charset=utf-8`，服务端逐个字符 `yield`，用来验证「响应体不是一次性生成」最直观。

### 5.4 `POST /api/chat`（非流式对照）

请求体同 5.1，但忽略两个延迟参数。响应示例：

```json
{
  "request_id": "req_xxx",
  "model": "demo-1",
  "content": "关于「...」，这是一个用 FastAPI 实现的流式接口演示。...",
  "finish_reason": "stop",
  "usage": {"prompt_tokens": 20, "completion_tokens": 261, "total_tokens": 281},
  "created": 1794393000,
  "elapsed_ms": 0.4
}
```

同一个错误在非流式接口上会返回 **HTTP 502**；而流式接口因为响应头已经发出，
只能返回 HTTP 200 + 流内 `error` 事件。这个对比在演示页里可以直接看到。

## 6. curl 实测

### 6.1 SSE

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"stream test","max_tokens":8,"token_delay_ms":150,"first_token_delay_ms":300}'
```

`-N` 关闭 curl 自身的缓冲，否则可能等响应结束才一次性打印。
实测时间线（首 token 约 300ms，之后每 150ms 一个 token）：

```text
... start ...                       t=0.000s
... token delta=关 ...              t=0.303s
... token delta=于 ...              t=0.454s
... token delta=「 ...              t=0.605s
...
... usage ttft_ms=302.5 ...         t=1.527s
... done finish_reason=length ...
```

### 6.2 NDJSON

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream/ndjson \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"ndjson test","max_tokens":5,"token_delay_ms":100}'
```

### 6.3 纯文本

```bash
curl -N 'http://127.0.0.1:8000/api/stream/echo?text=Hello&repeat=2&interval_ms=50'
```

### 6.4 流内错误

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"explain __error__","max_tokens":10,"token_delay_ms":0}'
```

会先收到若干 `token`，然后收到：

```text
event: error
data: {"request_id":"req_ae799ad74b5e","code":"generation_failed","message":"模拟上游模型在生成过程中失败"}
```

### 6.5 参数校验

```bash
curl -i -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' -d '{"prompt":"   "}'
# HTTP/1.1 422 Unprocessable Entity
```

> Windows PowerShell 里 `curl` 可能是 `Invoke-WebRequest` 的别名，
> 需要写成 `curl.exe -N ...`。

## 7. 可视化演示页

`static/index.html` 是一个零依赖的单页应用，包含：

- **三种协议切换**：SSE、NDJSON、一次性 JSON；
- **手动消费流**：用 `fetch` + `ReadableStream` + `TextDecoder`，自己实现 SSE 帧解析和 NDJSON 按行解析，
  而不是用 `EventSource`（因为接口是 POST）；
- **实时指标**：首字延迟 TTFT、总耗时、token 数、tok/s；
- **原始事件面板**：展示最近 20 条事件，方便对照协议格式；
- **中断请求**：`AbortController` 断开连接，可观察服务端日志中的 `disconnected` / `cancelled`；
- **错误演示**：prompt 里带 `__error__` 即可看到流内错误。

## 8. 关键实现说明

### 8.1 异步生成器 + `StreamingResponse`

核心只有两行职责：生成器负责「产出」，`StreamingResponse` 负责「发送」。

```python
async def event_stream():
    async for event, data, event_id in chat_events(payload, request, request_id):
        yield sse_event(event, data, event_id)

return StreamingResponse(event_stream(), media_type="text/event-stream")
```

注意不要写成普通 `def` 里 `time.sleep`，也不要在生成器里先 `"".join(...)` 拼完整结果，
否则流式就退化成了「一次性响应」。所有等待都必须是 `await asyncio.sleep(...)`。

### 8.2 SSE 帧格式

SSE 不是「JSON 数组」，而是一种按行组织的文本协议：

- `event: <名称>` 指定事件类型；
- `data: <一行>` 携带数据，多行数据要写多个 `data:`；
- `id: <编号>` 让客户端记录最后收到的事件；
- 空行表示一帧结束；
- `retry: 3000` 告诉浏览器断线后 3 秒重连。

代码里把 JSON 压成一行再写 `data:`，避免内容中的换行破坏帧结构：

```python
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
lines.append(f"event: {event}")
lines.extend(f"data: {line}" for line in payload.split("\n"))
```

同时设置 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no`，
防止浏览器或 Nginx 把流缓存/攒包；如果前面有 Nginx，还需要 `proxy_buffering off`（见第 10 节）。

### 8.3 首 token 延迟与心跳

真实模型在首 token 前可能等待数秒。如果这段时间连接上一个字节都没有，
中间的负载均衡、网关可能判定连接空闲并断开。实现里把首 token 等待切成多个
心跳周期，每过一个周期发一次 `ping`：

```python
async for _ in _sleep_with_heartbeat(first_delay, request):
    yield ("ping", {"request_id": request_id, "ts": _epoch_ms()}, None)
```

### 8.4 客户端断开与取消

客户端断连后继续生成纯属浪费算力，因此做了两层处理：

1. **协作式检查**：每个 token 前后调用 `await request.is_disconnected()`，发现断开立即停止；
2. **取消信号**：ASGI 服务器（Uvicorn/Starlette）在连接断开时可能直接取消任务，
   生成器里会收到 `asyncio.CancelledError`，记录日志后**重新抛出**，不能吞掉取消信号。

实测用 `timeout 1 curl -N ...` 中断一个 100 token 的流，日志输出：

```text
stream start request_id=req_9d466fe8351b model=demo-1 max_tokens=100
stream cancelled request_id=req_9d466fe8351b tokens=10
stream end request_id=req_9d466fe8351b outcome=cancelled tokens=10
```

服务端只生成了 10 个 token 就停止，不会把剩下的 90 个跑完。

### 8.5 流内错误

HTTP 响应头一旦发出，状态码就不能再改。因此流式接口的错误处理原则是：

- 参数错误、鉴权失败等**响应头发出前**的错误 → 正常返回 4xx/5xx；
- 生成过程中的错误 → HTTP 200 + `event: error`，由客户端根据事件类型处理。

演示里用 prompt 包含 `__error__` 稳定触发第 4 个 token 处失败，方便复现。
非流式接口则直接抛异常，由全局异常处理器返回 502。

### 8.6 TTFT、吞吐与 usage

- **TTFT**：从请求开始到第一个 `token` 产出之间的毫秒数；
- **tokens_per_second**：只在真正生成阶段计时（排除首 token 等待），避免被 prefill 拉低；
- **usage**：prompt/completion/total 三个计数，字段风格对齐 OpenAI，方便客户端复用。

### 8.7 生成与协议解耦

`service.chat_events()` 只产出 `(event, data, event_id)` 三元组，
SSE 路由和 NDJSON 路由各自只做编码。这样：

- 新增一种协议不用改业务逻辑；
- 单元测试可以直接消费 `chat_events()`，不依赖 HTTP；
- 心跳、断连、错误处理只写一遍。

### 8.8 背压

`StreamingResponse` 会 `await send(...)` 把每个 chunk 交给 ASGI 服务器；
客户端读得慢时，发送协程会被自然阻塞，不会在内存里无限堆积。
这也是为什么不应该在生成器外面再套一个无界 `asyncio.Queue`。

## 9. 测试

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

结果（Python 3.12 + FastAPI 0.162.4 + Uvicorn 0.54.0）：

```text
..................                                                       [100%]
18 passed
```

覆盖内容：

- 健康检查、演示页、Swagger/OpenAPI；
- SSE 事件顺序、`retry` 帧、`Content-Type`、`Cache-Control`、`X-Request-ID`；
- SSE token 事件 `id` 严格递增；
- NDJSON 逐行解析、首尾事件；
- 流式与非流式文本一致、`finish_reason` 一致；
- `max_tokens` 截断（`length`）与自然结束（`stop`）；
- 流内错误事件、非流式 502；
- 空白 prompt、非法 `max_tokens`、超长 prompt 的 422；
- 纯文本分块输出；
- CORS 响应头；
- 客户端断开后生成器立即停止（用假 Request 单元测试）；
- 首 token 等待期间的心跳。

`TestClient` 会缓冲响应体，适合验证「内容是否正确」；
真正的「是否逐块到达」用第 6 节的 `curl -N` + 时间戳验证。

## 10. 参数与配置

### 10.1 请求参数

见 5.1 节的表格。所有参数都会经过 Pydantic 校验，非法值返回 422。

### 10.2 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEMO_FIRST_TOKEN_DELAY_MS` | `500` | 首 token 默认等待 |
| `DEMO_TOKEN_DELAY_MS` | `20` | 默认 token 间隔 |
| `DEMO_HEARTBEAT_INTERVAL_S` | `5` | 心跳周期（秒） |
| `DEMO_SSE_RETRY_MS` | `3000` | SSE 重连间隔 |
| `DEMO_MAX_PROMPT_CHARS` | `2000` | prompt 长度上限 |
| `DEMO_MAX_TOKENS_LIMIT` | `512` | max_tokens 上限 |
| `DEMO_MAX_TOKEN_DELAY_MS` | `300` | token 间隔上限 |
| `DEMO_MAX_FIRST_TOKEN_DELAY_MS` | `10000` | 首 token 等待上限 |

例如放慢演示：

```bash
DEMO_TOKEN_DELAY_MS=100 uvicorn app.main:app --port 8000
```

### 10.3 反向代理

SSE 经过 Nginx 时必须关闭缓冲，并放宽读超时，否则会「攒一波再发」甚至 504：

```nginx
location /api/chat/stream {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
}
```

另外不要对 SSE 响应启用 GZip 中间件：压缩会引入缓冲，破坏逐 token 下发的效果。

## 11. 已知限制与生产化建议

这是面试演示项目，刻意保持小而完整，以下几点在生产环境需要补齐：

1. **模型是假的**：`app/llm.py` 只做确定性 token 切分，不调用任何外部服务；
2. **无鉴权/限流**：生产环境需要 API Key、用户级配额、并发上限；
3. **单进程状态**：演示没有跨进程共享状态；多 worker 部署时，会话/取消信号需要 Redis 等外部协调；
4. **断点续传未实现**：SSE 的 `Last-Event-ID` 只发不收，客户端断线重连会重新生成；
5. **超时与最大时长**：生产上应限制单次生成的总时长和 token 预算；
6. **可观测性**：可补充 Prometheus 指标（活跃连接数、TTFT 分布、token 吞吐、错误率）和链路追踪；
7. **多副本部署**：SSE 长连接需要负载均衡支持，网关空闲超时要小于心跳周期。

## 12. 替换成真实 LLM

`app/llm.py` 的接口是 `async def stream_tokens(prompt, limit) -> AsyncIterator[str]`。
接入 OpenAI 兼容接口时，只需把实现换成：

```python
async def stream_tokens(prompt: str, limit: int):
    stream = await client.chat.completions.create(
        model="your-model",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=limit,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
```

`service.py`、SSE/NDJSON 编码、前端、测试都不需要改。
