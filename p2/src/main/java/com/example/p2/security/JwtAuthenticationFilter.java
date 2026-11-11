package com.example.p2.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * JWT 认证过滤器：每个请求只执行一次。
 *
 * <p>职责很单一——从请求头 {@code Authorization: Bearer <token>} 中取出令牌，
 * 解析成功就把认证信息放进 SecurityContext，后续的授权判断即可通过；
 * 解析失败则什么也不做，请求会继续走到后面的过滤器链，
 * 最终由 {@link RestAuthenticationEntryPoint} 返回 401。</p>
 *
 * <p>注意：这里不直接返回 401，是为了让“放行接口”（如登录接口）在
 * 携带错误令牌时依然可以正常访问。</p>
 */
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtTokenProvider jwtTokenProvider;

    public JwtAuthenticationFilter(JwtTokenProvider jwtTokenProvider) {
        this.jwtTokenProvider = jwtTokenProvider;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);

        // 只有“带 Bearer 前缀”且“当前还没有认证信息”时才尝试解析
        if (StringUtils.hasText(header)
                && header.startsWith(BEARER_PREFIX)
                && SecurityContextHolder.getContext().getAuthentication() == null) {

            String token = header.substring(BEARER_PREFIX.length()).trim();
            Authentication authentication = jwtTokenProvider.parseToken(token);

            if (authentication != null) {
                // 认证成功：写入 SecurityContext，本次请求后续即可视为已登录
                SecurityContextHolder.getContext().setAuthentication(authentication);
            }
        }

        // 无论是否认证成功都要继续过滤器链（是否放行由授权规则决定）
        filterChain.doFilter(request, response);
    }
}
