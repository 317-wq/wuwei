package com.example.p2.security;

import com.example.p2.config.JwtProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Date;
import java.util.List;

/**
 * JWT 令牌工具类：负责“签发令牌”和“解析令牌”。
 *
 * <p>令牌采用 HS256 对称签名（HMAC-SHA256），密钥来自配置 {@code app.jwt.secret}。
 * 服务端不需要保存会话，令牌本身就携带了用户名、角色和过期时间。</p>
 */
@Component
public class JwtTokenProvider {

    /** 角色信息在令牌中的自定义 claim 名称 */
    private static final String CLAIM_ROLES = "roles";

    /** JWT 的固定结构：header.payload.signature，共 3 段 base64url */
    private static final int JWT_SEGMENT_COUNT = 3;

    private final SecretKey secretKey;

    private final Duration expiration;

    public JwtTokenProvider(JwtProperties properties) {
        // HS256 要求密钥长度不少于 32 字节，配置中的密钥已满足该要求
        this.secretKey = Keys.hmacShaKeyFor(properties.secret().getBytes(StandardCharsets.UTF_8));
        this.expiration = properties.expiration();
    }

    /**
     * 根据登录成功后的 Authentication 签发 JWT。
     *
     * @param authentication 已认证的用户信息（用户名 + 权限）
     * @return 紧凑格式的 JWT 字符串
     */
    public String createToken(Authentication authentication) {
        Instant now = Instant.now();
        Instant expiresAt = now.plus(expiration);

        List<String> roles = authentication.getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .toList();

        return Jwts.builder()
                .subject(authentication.getName())   // 主题：用户名
                .claim(CLAIM_ROLES, roles)           // 自定义 claim：角色列表
                .issuedAt(Date.from(now))            // 签发时间
                .expiration(Date.from(expiresAt))    // 过期时间
                // 显式指定 HS256，避免算法随密钥长度变化（jjwt 默认会按密钥长度自动挑选）
                .signWith(secretKey, Jwts.SIG.HS256) // 签名，防篡改
                .compact();
    }

    /**
     * 校验并解析 JWT。
     *
     * <p>签名错误、令牌过期、格式非法等情况统一返回 {@code null}，
     * 由调用方决定“当作未认证处理”，避免把底层异常暴露给客户端。</p>
     *
     * @param token JWT 字符串（不含 "Bearer " 前缀）
     * @return 认证对象；令牌无效时返回 null
     */
    public Authentication parseToken(String token) {
        // 先做严格的格式校验：必须是 3 段，且每段长度不能是 4n+1。
        // 原因：jjwt 底层 base64url 解码较宽松，签名段长度为 4n+1 时会把末尾多余的 1 个字符丢弃，
        // 导致“正确令牌尾部再加 1 个垃圾字符”也能通过验签（内容其实没变），这里显式拒绝非规范输入。
        if (!hasValidStructure(token)) {
            return null;
        }

        try {
            Claims claims = Jwts.parser()
                    .verifyWith(secretKey) // 用同一密钥验签
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            String username = claims.getSubject();
            if (username == null || username.isBlank()) {
                return null;
            }

            // 从 claim 中还原权限，交给后续的授权判断使用
            List<GrantedAuthority> authorities = new ArrayList<>();
            Object rolesClaim = claims.get(CLAIM_ROLES);
            if (rolesClaim instanceof Collection<?> roles) {
                for (Object role : roles) {
                    authorities.add(new SimpleGrantedAuthority(String.valueOf(role)));
                }
            }

            // 第三个参数为权限集合；credentials 置空，因为已通过签名验证身份
            return new UsernamePasswordAuthenticationToken(username, null, authorities);
        } catch (JwtException | IllegalArgumentException ex) {
            // 签名不匹配、已过期、格式错误等都属于“令牌不可用”
            return null;
        }
    }

    /**
     * 校验 JWT 的字面结构：3 段非空 base64url，且长度合法（长度 % 4 不能等于 1）。
     *
     * <p>只检查结构，不校验内容；内容是否可信由后面的验签保证。</p>
     */
    private boolean hasValidStructure(String token) {
        String[] segments = token.split("\\.", -1);
        if (segments.length != JWT_SEGMENT_COUNT) {
            return false;
        }
        for (String segment : segments) {
            if (segment.isEmpty() || segment.length() % 4 == 1) {
                return false;
            }
        }
        return true;
    }

    /** 令牌有效期，用于登录响应中的 expiresIn 字段 */
    public Duration getExpiration() {
        return expiration;
    }
}
