package com.example.p2.dto;

/**
 * 登录成功响应体。
 *
 * @param token     JWT 令牌，后续请求放在 Authorization 请求头中
 * @param tokenType 令牌类型，固定为 Bearer，拼接方式：Bearer &lt;token&gt;
 * @param expiresIn 有效期（秒）
 * @param username  登录成功的用户名
 */
public record LoginResponse(String token, String tokenType, long expiresIn, String username) {
}
