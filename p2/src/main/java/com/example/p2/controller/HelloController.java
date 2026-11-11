package com.example.p2.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * HelloWorld 接口。
 *
 * <p>该接口没有配置 permitAll，因此会被 SecurityConfig 中的
 * {@code anyRequest().authenticated()} 拦截：必须携带有效凭证才能访问，
 * 未认证时统一返回 401。</p>
 */
@RestController
public class HelloController {

    /**
     * GET /hello（同时暴露 /api/hello 别名，方便按不同路径习惯调用）。
     *
     * <p>返回值是纯文本 "Hello World"（Content-Type: text/plain）。</p>
     */
    @GetMapping({"/hello", "/api/hello"})
    public String hello() {
        return "Hello World";
    }
}
