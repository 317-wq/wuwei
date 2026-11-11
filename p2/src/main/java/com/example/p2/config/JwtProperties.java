package com.example.p2.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * JWT 相关配置，对应 application.yml 中的 app.jwt.* 节点。
 *
 * <p>使用 record + @ConfigurationProperties 实现类型安全的外部化配置，
 * 启动时由 @EnableConfigurationProperties 注册为 Bean。</p>
 *
 * @param secret     签名密钥；HS256 要求至少 32 字节（256 bit）
 * @param expiration 令牌有效期，支持 2h、30m 这类写法
 */
@ConfigurationProperties(prefix = "app.jwt")
public record JwtProperties(String secret, Duration expiration) {
}
