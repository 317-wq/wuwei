package com.example.p2.config;

import com.example.p2.security.JwtAuthenticationFilter;
import com.example.p2.security.RestAccessDeniedHandler;
import com.example.p2.security.RestAuthenticationEntryPoint;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.authentication.configuration.AuthenticationConfiguration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.InMemoryUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * Spring Security 核心配置。
 *
 * <p>整体方案：无状态（STATELESS）+ JWT</p>
 * <ul>
 *   <li>登录接口 {@code POST /api/login} 放行，用于换取 token；</li>
 *   <li>其余接口一律要求已认证，由 {@link JwtAuthenticationFilter} 解析
 *       {@code Authorization: Bearer <token>} 完成认证；</li>
 *   <li>未认证 / 无权限时返回统一 JSON（而不是 Spring Security 默认的 HTML 登录页）。</li>
 * </ul>
 */
@Configuration
@EnableWebSecurity // 启用 Spring Security 的 Web 安全支持
@EnableMethodSecurity // 启用 @PreAuthorize 方法级鉴权（本题用不到，作为扩展预留）
public class SecurityConfig {

    /** 题目指定的演示账号 */
    private static final String DEMO_USERNAME = "test";

    /** 题目指定的演示密码（仅用于演示，真实项目密码只能以密文存储） */
    private static final String DEMO_PASSWORD = "123456";

    /**
     * 密码编码器：BCrypt 自带随机盐，同一明文每次编码结果都不同；
     * 登录校验时由 DaoAuthenticationProvider 调用 matches() 比对。
     */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    /**
     * 用户信息来源（UserDetailsService）。
     *
     * <p>这里用内存用户演示；真实项目通常替换为“查数据库”的实现，
     * 只要返回的密码是 BCrypt 密文即可，其余代码无需改动。</p>
     */
    @Bean
    public UserDetailsService userDetailsService(PasswordEncoder passwordEncoder) {
        UserDetails demoUser = User.builder()
                .username(DEMO_USERNAME)
                // 启动时把明文编码为 BCrypt 密文，内存中不保存明文
                .password(passwordEncoder.encode(DEMO_PASSWORD))
                .roles("USER") // 等价于授予权限 ROLE_USER
                .build();
        return new InMemoryUserDetailsManager(demoUser);
    }

    /**
     * 暴露 AuthenticationManager 给登录接口使用。
     *
     * <p>Spring Boot 会自动装配一个 DaoAuthenticationProvider，
     * 它使用上面声明的 UserDetailsService + PasswordEncoder 校验账号密码。</p>
     */
    @Bean
    public AuthenticationManager authenticationManager(AuthenticationConfiguration configuration) throws Exception {
        return configuration.getAuthenticationManager();
    }

    /**
     * 安全过滤器链：定义“哪些路径放行、哪些路径需要认证、认证方式是什么”。
     */
    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http,
                                                   JwtAuthenticationFilter jwtAuthenticationFilter,
                                                   RestAuthenticationEntryPoint authenticationEntryPoint,
                                                   RestAccessDeniedHandler accessDeniedHandler) throws Exception {
        http
                // 前后端分离 + Token 认证，不使用 Session，因此关闭 CSRF（CSRF 依赖 Cookie 会话）
                .csrf(AbstractHttpConfigurer::disable)
                // 开启跨域支持（配合下面的 CorsConfigurationSource）
                .cors(Customizer.withDefaults())
                // 不创建、不使用 HttpSession，每个请求都靠 Token 认证
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                // 请求授权规则：注意规则按声明顺序匹配，放行规则要写在前面
                .authorizeHttpRequests(auth -> auth
                        // 登录接口允许匿名访问
                        .requestMatchers(HttpMethod.POST, "/api/login", "/login").permitAll()
                        // 错误转发路径放行，避免异常响应被二次拦截成 401
                        .requestMatchers("/error").permitAll()
                        // 其余所有请求（含 /hello）都必须先通过认证
                        .anyRequest().authenticated())
                // 未认证 -> 401 JSON；已认证但无权限 -> 403 JSON
                .exceptionHandling(handling -> handling
                        .authenticationEntryPoint(authenticationEntryPoint)
                        .accessDeniedHandler(accessDeniedHandler))
                // 兼容 HTTP Basic 认证，方便用 curl -u test:123456 直接调试（可选能力）
                .httpBasic(Customizer.withDefaults())
                // 把 JWT 过滤器插到用户名密码过滤器之前，先尝试用 Token 认证
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    /**
     * 跨域配置：演示环境放开所有来源，生产环境请改为具体的前端域名。
     */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOriginPatterns(List.of("*"));
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("*"));
        configuration.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }
}
