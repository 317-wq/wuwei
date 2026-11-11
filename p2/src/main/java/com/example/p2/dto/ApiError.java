package com.example.p2.dto;

/**
 * 统一的错误响应体。
 *
 * <p>示例：{"code":401,"message":"未认证：...","path":"/hello"}</p>
 *
 * @param code    HTTP 状态码，与响应状态保持一致，方便前端统一处理
 * @param message 可读的错误说明
 * @param path    触发错误的请求路径
 */
public record ApiError(int code, String message, String path) {
}
