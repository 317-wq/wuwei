package com.example.p2.exception;

import com.example.p2.dto.ApiError;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.context.support.DefaultMessageSourceResolvable;
import org.springframework.http.HttpStatus;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

/**
 * 全局异常处理：把异常统一转换成 JSON 错误响应。
 *
 * <p>注意：过滤器链中抛出的异常（如未认证）不会经过这里，
 * 而是由 SecurityConfig 里配置的 AuthenticationEntryPoint 处理。</p>
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 登录时账号或密码错误。
     *
     * <p>Spring Security 默认会把“用户不存在”也包装成 BadCredentialsException，
     * 避免攻击者据此枚举用户名，所以这里统一提示“用户名或密码错误”。</p>
     */
    @ExceptionHandler(AuthenticationException.class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    public ApiError handleAuthenticationException(AuthenticationException ex, HttpServletRequest request) {
        return new ApiError(HttpStatus.UNAUTHORIZED.value(), "用户名或密码错误", request.getRequestURI());
    }

    /** 请求体字段校验失败，例如 username 为空 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiError handleValidationException(MethodArgumentNotValidException ex, HttpServletRequest request) {
        String message = ex.getBindingResult().getFieldErrors().stream()
                .map(DefaultMessageSourceResolvable::getDefaultMessage)
                .collect(Collectors.joining("; "));
        return new ApiError(HttpStatus.BAD_REQUEST.value(),
                message.isBlank() ? "请求参数不合法" : message,
                request.getRequestURI());
    }

    /** 请求体不是合法 JSON，或缺少请求体 */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiError handleUnreadableBody(HttpMessageNotReadableException ex, HttpServletRequest request) {
        return new ApiError(HttpStatus.BAD_REQUEST.value(),
                "请求体格式错误，请提交 JSON，例如 {\"username\":\"test\",\"password\":\"123456\"}",
                request.getRequestURI());
    }

    /** 已认证但权限不足（本题仅一个角色，通常不会触发） */
    @ExceptionHandler(AccessDeniedException.class)
    @ResponseStatus(HttpStatus.FORBIDDEN)
    public ApiError handleAccessDeniedException(AccessDeniedException ex, HttpServletRequest request) {
        return new ApiError(HttpStatus.FORBIDDEN.value(), "没有访问该资源的权限", request.getRequestURI());
    }
}
