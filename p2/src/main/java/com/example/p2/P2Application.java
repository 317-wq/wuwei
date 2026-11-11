package com.example.p2;

import com.example.p2.config.JwtProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

/**
 * 项目启动类。
 *
 * <p>题目要求：基于 Spring Boot 3.2.0 + Spring Security，实现</p>
 * <ol>
 *   <li>一个需要认证才能访问的 HelloWorld 接口（GET）；</li>
 *   <li>一个用户名/密码登录接口（test / 123456），登录成功后签发 JWT 令牌。</li>
 * </ol>
 */
@SpringBootApplication
// 把 application.yml 里的 app.jwt.* 配置绑定到 JwtProperties（record）
@EnableConfigurationProperties(JwtProperties.class)
public class P2Application {

    public static void main(String[] args) {
        SpringApplication.run(P2Application.class, args);
    }
}
