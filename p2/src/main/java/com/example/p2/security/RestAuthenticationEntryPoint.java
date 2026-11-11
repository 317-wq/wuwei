package com.example.p2.security;

import com.example.p2.dto.ApiError;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * 未认证处理器：替换 Spring Security 默认的 302 跳转登录页 / 401 空响应，
 * 改为返回统一格式的 401 JSON，方便前端和接口调试。
 */
@Component
public class RestAuthenticationEntryPoint implements AuthenticationEntryPoint {

    private final ObjectMapper objectMapper;

    public RestAuthenticationEntryPoint(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    @Override
    public void commence(HttpServletRequest request,
                         HttpServletResponse response,
                         AuthenticationException authException) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());

        ApiError body = new ApiError(
                HttpServletResponse.SC_UNAUTHORIZED,
                "未认证：请先调用 POST /api/login 获取 token，再在请求头携带 Authorization: Bearer <token>",
                request.getRequestURI());
        objectMapper.writeValue(response.getWriter(), body);
    }
}
