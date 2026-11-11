package com.example.p2;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.Map;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.httpBasic;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 端到端集成测试：验证“登录 -> 拿令牌 -> 访问受保护接口”的完整链路。
 *
 * <p>启动完整 Spring 容器 + MockMvc，不占用真实端口。</p>
 */
@SpringBootTest
@AutoConfigureMockMvc
class AuthFlowIntegrationTest {

    private static final String LOGIN_URL = "/api/login";

    private static final String HELLO_URL = "/hello";

    private static final String DEMO_USERNAME = "test";

    private static final String DEMO_PASSWORD = "123456";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @DisplayName("未携带令牌访问 /hello 返回 401")
    void helloWithoutTokenShouldReturn401() throws Exception {
        mockMvc.perform(get(HELLO_URL))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401))
                .andExpect(jsonPath("$.path").value(HELLO_URL));
    }

    @Test
    @DisplayName("伪造/篡改令牌访问 /hello 返回 401")
    void helloWithInvalidTokenShouldReturn401() throws Exception {
        String token = loginAndGetToken();
        mockMvc.perform(get(HELLO_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + token + "tampered"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    @DisplayName("令牌尾部追加垃圾字符访问 /hello 返回 401（拒绝非规范 base64url）")
    void helloWithTokenPlusGarbageShouldReturn401() throws Exception {
        String token = loginAndGetToken();
        mockMvc.perform(get(HELLO_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + token + "x"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    @DisplayName("登录成功返回 token，携带该 token 访问 /hello 返回 Hello World")
    void loginThenAccessHelloShouldSucceed() throws Exception {
        String token = loginAndGetToken();

        mockMvc.perform(get(HELLO_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_PLAIN))
                .andExpect(content().string("Hello World"));

        // 别名路径 /api/hello 同样可用
        mockMvc.perform(get("/api/hello").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(content().string("Hello World"));
    }

    @Test
    @DisplayName("密码错误登录返回 401")
    void loginWithWrongPasswordShouldReturn401() throws Exception {
        mockMvc.perform(post(LOGIN_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(loginBody(DEMO_USERNAME, "wrong-password")))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401))
                .andExpect(jsonPath("$.message").value("用户名或密码错误"));
    }

    @Test
    @DisplayName("用户不存在登录返回 401，且不暴露用户是否存在")
    void loginWithUnknownUserShouldReturn401() throws Exception {
        mockMvc.perform(post(LOGIN_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(loginBody("not-exist", DEMO_PASSWORD)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    @DisplayName("缺少密码字段登录返回 400")
    void loginWithoutPasswordShouldReturn400() throws Exception {
        mockMvc.perform(post(LOGIN_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"test\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.message").value("密码不能为空"));
    }

    @Test
    @DisplayName("HTTP Basic 也可通过认证（方便 curl 调试的兼容能力）")
    void helloWithBasicAuthShouldSucceed() throws Exception {
        mockMvc.perform(get(HELLO_URL).with(httpBasic(DEMO_USERNAME, DEMO_PASSWORD)))
                .andExpect(status().isOk())
                .andExpect(content().string("Hello World"));
    }

    /** 登录并返回 token；同时断言登录响应的核心字段 */
    private String loginAndGetToken() throws Exception {
        MvcResult result = mockMvc.perform(post(LOGIN_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(loginBody(DEMO_USERNAME, DEMO_PASSWORD)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.token").isNotEmpty())
                .andExpect(jsonPath("$.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.expiresIn").value(7200))
                .andExpect(jsonPath("$.username").value(DEMO_USERNAME))
                .andReturn();

        JsonNode body = objectMapper.readTree(result.getResponse().getContentAsString());
        return body.get("token").asText();
    }

    private String loginBody(String username, String password) throws Exception {
        return objectMapper.writeValueAsString(Map.of("username", username, "password", password));
    }
}
