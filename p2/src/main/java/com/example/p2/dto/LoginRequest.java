package com.example.p2.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * 登录请求体。
 *
 * <p>使用 record 承载不可变数据；@NotBlank 由 spring-boot-starter-validation 校验，
 * 校验失败时由全局异常处理器统一返回 400。</p>
 *
 * @param username 用户名，例如 test
 * @param password 明文密码，例如 123456
 */
public record LoginRequest(
        @NotBlank(message = "用户名不能为空") String username,
        @NotBlank(message = "密码不能为空") String password) {
}
