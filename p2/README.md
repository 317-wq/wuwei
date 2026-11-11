# P2：Spring Boot 3.2.0 + Spring Security 认证示例

> 笔试题实现：一个**需要 Spring Security 认证**才能访问的 HelloWorld 接口，以及一个**用户名 / 密码登录**接口。
>
> 演示账号：`test` / `123456`

## 1. 题目要求与实现对照

| 题目要求 | 本项目实现 | 位置 |
| --- | --- | --- |
| Spring Boot 3.2.0 | `spring-boot-starter-parent` 版本固定为 `3.2.0` | `pom.xml` |
| GET HelloWorld 接口，返回 `Hello World` | `GET /hello`（别名 `/api/hello`），返回 `text/plain` 的 `Hello World` | `HelloController` |
| 该接口需要 Spring Security 认证 | 未显式放行，命中 `anyRequest().authenticated()`；未认证返回 401 JSON | `SecurityConfig` |
| 用户名密码登录 API | `POST /api/login`，校验通过后签发 JWT | `AuthController` |
| 账号 test / 123456 | 内存用户 `test`，密码以 BCrypt 密文保存 | `SecurityConfig#userDetailsService` |

## 2. 技术栈

- JDK 17（Spring Boot 3.x 最低要求）
- Spring Boot 3.2.0 / Spring Security 6.2 / Spring MVC
- [jjwt 0.12.3](https://github.com/jwtk/jjwt)（JWT 签发与验签）
- Maven 3.6+
- JUnit 5 + MockMvc（集成测试）

## 3. 快速开始

```bash
cd p2

# 方式一：打包后运行
mvn clean package
java -jar target/p2-1.0.0.jar

# 方式二：开发模式直接运行
mvn spring-boot:run
```

启动成功后服务监听 `http://localhost:8080`。也可以直接用 IDEA 运行 `P2Application`。

## 4. 接口说明

### 4.1 登录接口

| 项目 | 内容 |
| --- | --- |
| 方法 / 路径 | `POST /api/login`（别名 `POST /login`） |
| 认证要求 | 无需认证 |
| Content-Type | `application/json` |

请求体：

```json
{
  "username": "test",
  "password": "123456"
}
```

成功响应（200）：

```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0Iiwi...",
  "tokenType": "Bearer",
  "expiresIn": 7200,
  "username": "test"
}
```

失败响应：

| 场景 | 状态码 | 响应示例 |
| --- | --- | --- |
| 账号或密码错误 | 401 | `{"code":401,"message":"用户名或密码错误","path":"/api/login"}` |
| 用户名/密码为空 | 400 | `{"code":400,"message":"密码不能为空","path":"/api/login"}` |

curl 示例：

```bash
curl -s -X POST http://localhost:8080/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"test","password":"123456"}'
```

### 4.2 HelloWorld 接口

| 项目 | 内容 |
| --- | --- |
| 方法 / 路径 | `GET /hello`（别名 `GET /api/hello`） |
| 认证要求 | **必须认证**，否则返回 401 |
| 成功响应 | 200，`Content-Type: text/plain;charset=UTF-8`，响应体 `Hello World` |

支持两种携带凭证的方式。

**方式一：Bearer Token（推荐，登录接口返回的 token）**

```bash
# 1. 未认证访问：返回 401
curl -i http://localhost:8080/hello

# 2. 登录取 token
TOKEN=$(curl -s -X POST http://localhost:8080/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"test","password":"123456"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# 3. 带 token 访问：返回 Hello World
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/hello
```

**方式二：HTTP Basic（兼容能力，方便快速调试）**

```bash
curl -u test:123456 http://localhost:8080/hello
```

未认证时的响应（401）：

```json
{
  "code": 401,
  "message": "未认证：请先调用 POST /api/login 获取 token，再在请求头携带 Authorization: Bearer <token>",
  "path": "/hello"
}
```

> 项目根目录的 `api.http` 可以直接用 IDEA / VS Code 的 HTTP Client 依次执行上述请求。

## 5. 认证流程

```text
客户端                        服务端
  |  POST /api/login            |
  |  {username, password}       |
  |---------------------------->| AuthController
  |                             |  └─ AuthenticationManager
  |                             |       └─ DaoAuthenticationProvider
  |                             |            ├─ UserDetailsService（查用户）
  |                             |            └─ BCryptPasswordEncoder（校验密码）
  |                             |  └─ JwtTokenProvider 签发 HS256 JWT
  |  200 {token, expiresIn}     |
  |<----------------------------|
  |                             |
  |  GET /hello                 |
  |  Authorization: Bearer ...  |
  |---------------------------->| JwtAuthenticationFilter（验签 -> 写入 SecurityContext）
  |                             |  └─ AuthorizationFilter（anyRequest().authenticated()）
  |                             |       └─ HelloController -> "Hello World"
  |  200 Hello World            |
  |<----------------------------|
```

关键点：

1. **登录不自己比对密码**：交给 `AuthenticationManager`，由 `UserDetailsService` + `PasswordEncoder` 完成，账号不存在与密码错误都会抛出 `BadCredentialsException`，统一返回 401。
2. **无状态认证**：`SessionCreationPolicy.STATELESS`，服务端不保存会话，客户端每次请求携带 JWT，方便水平扩容。
3. **JWT 内容**：`sub`（用户名）、`roles`（角色，如 `ROLE_USER`）、`iat` / `exp`（签发与过期时间），使用 HS256 签名防篡改。
4. **过滤器顺序**：`JwtAuthenticationFilter` 插在 `UsernamePasswordAuthenticationFilter` 之前，先尝试用 Token 认证；HTTP Basic 作为兜底方式。

## 6. 项目结构

```text
p2
├── pom.xml
├── api.http                              # 可直接执行的接口调试脚本
├── README.md
└── src
    ├── main
    │   ├── java/com/example/p2
    │   │   ├── P2Application.java        # 启动类
    │   │   ├── config
    │   │   │   ├── SecurityConfig.java   # 安全过滤器链、密码编码器、演示用户
    │   │   │   └── JwtProperties.java    # JWT 配置绑定（app.jwt.*）
    │   │   ├── controller
    │   │   │   ├── AuthController.java   # POST /api/login
    │   │   │   └── HelloController.java  # GET /hello
    │   │   ├── dto
    │   │   │   ├── LoginRequest.java     # 登录请求体（含参数校验）
    │   │   │   ├── LoginResponse.java    # 登录响应体
    │   │   │   └── ApiError.java         # 统一错误响应体
    │   │   ├── exception
    │   │   │   └── GlobalExceptionHandler.java
    │   │   └── security
    │   │       ├── JwtTokenProvider.java            # 签发 / 解析 JWT
    │   │       ├── JwtAuthenticationFilter.java     # 从请求头解析 JWT
    │   │       ├── RestAuthenticationEntryPoint.java # 401 JSON
    │   │       └── RestAccessDeniedHandler.java      # 403 JSON
    │   └── resources
    │       └── application.yml           # 端口、JWT 密钥与有效期
    └── test
        └── java/com/example/p2
            └── AuthFlowIntegrationTest.java
```

## 7. 关键设计说明

- **密码安全**：使用 `BCryptPasswordEncoder`，自带随机盐，数据库中不保存明文；登录响应里也不会回显密码。
- **统一错误格式**：未认证（401）由 `RestAuthenticationEntryPoint` 处理，权限不足（403）由 `RestAccessDeniedHandler` 处理，业务异常由 `GlobalExceptionHandler` 处理，避免 Spring Security 默认返回 HTML 登录页。
- **令牌格式严格校验**：jjwt 底层的 base64url 解码较宽松，签名段长度为 `4n+1` 时末尾多余字符会被丢弃，导致“正确令牌 + 1 个垃圾字符”也能通过验签。`JwtTokenProvider#hasValidStructure` 会显式拒绝这类非规范输入（本项目有对应测试用例）。
- **配置外置**：JWT 密钥与有效期放在 `application.yml`，生产环境通过环境变量覆盖：

  ```bash
  export JWT_SECRET="换成你自己的至少 32 字节随机字符串"
  ```

- **CORS**：演示环境放开了跨域，生产环境应改为具体前端域名。

## 8. 测试

```bash
mvn test
```

`AuthFlowIntegrationTest` 共 8 个用例，覆盖：

1. 未携带令牌访问 `/hello` → 401；
2. 伪造 / 篡改令牌 → 401；
3. 令牌尾部追加垃圾字符 → 401；
4. 登录成功 → 返回 token，且该 token 能访问 `/hello` 得到 `Hello World`；
5. 密码错误 → 401；
6. 用户不存在 → 401（且不暴露用户是否存在）；
7. 缺少密码字段 → 400；
8. HTTP Basic 认证访问 `/hello` → 200。

实际运行结果：

```text
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

## 9. 生产环境可扩展点

- 用户数据改为数据库存储（JPA / MyBatis），实现基于数据库的 `UserDetailsService`；
- 引入刷新令牌（refresh token）、令牌吊销（Redis 黑名单）与登出接口；
- 增加角色 / 权限控制（`@PreAuthorize("hasRole('ADMIN')")`）与接口级限流；
- 全站 HTTPS、密钥托管（KMS / 配置中心）、登录失败次数限制与审计日志；
- 补充 OpenAPI（springdoc）接口文档。
