package com.example.p2.controller;

import com.example.p2.dto.LoginRequest;
import com.example.p2.dto.LoginResponse;
import com.example.p2.security.JwtTokenProvider;
import jakarta.validation.Valid;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * 认证接口：用户名 + 密码换取 JWT 令牌。
 */
@RestController
public class AuthController {

    private final AuthenticationManager authenticationManager;

    private final JwtTokenProvider jwtTokenProvider;

    public AuthController(AuthenticationManager authenticationManager, JwtTokenProvider jwtTokenProvider) {
        this.authenticationManager = authenticationManager;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    /**
     * 登录接口。
     *
     * <p>请求：POST /api/login，JSON 体 {"username":"test","password":"123456"}</p>
     * <p>成功：200 + 令牌；账号密码错误：401 + 错误信息。</p>
     *
     * <p>这里不自己比对密码，而是把用户名密码交给 AuthenticationManager，
     * 由它调用 UserDetailsService 查用户、用 PasswordEncoder 校验密码，
     * 校验通过后返回已认证的 Authentication。</p>
     */
    @PostMapping({"/api/login", "/login"})
    public LoginResponse login(@Valid @RequestBody LoginRequest request) {
        // 认证失败会抛出 BadCredentialsException（AuthenticationException 的子类），
        // 由 GlobalExceptionHandler 转成 401 JSON
        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.username(), request.password()));

        // 认证通过，签发 JWT
        String token = jwtTokenProvider.createToken(authentication);

        return new LoginResponse(
                token,
                "Bearer",
                jwtTokenProvider.getExpiration().toSeconds(),
                authentication.getName());
    }
}
