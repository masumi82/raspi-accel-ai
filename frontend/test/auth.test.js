import { describe, it, expect } from "vitest";
import { buildOidcConfig, cognitoLogoutUrl } from "../src/auth";

const cfg = {
  cognitoAuthority: "https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_abc",
  cognitoClientId: "client123",
  cognitoDomain: "raspi-accel-ai-1.auth.ap-northeast-1.amazoncognito.com",
  redirectUri: "http://localhost:5173/",
};

describe("auth", () => {
  it("buildOidcConfig maps config to oidc settings", () => {
    const o = buildOidcConfig(cfg);
    expect(o.authority).toBe(cfg.cognitoAuthority);
    expect(o.client_id).toBe("client123");
    expect(o.redirect_uri).toBe("http://localhost:5173/");
    expect(o.response_type).toBe("code");
    expect(o.scope).toContain("openid");
  });

  it("cognitoLogoutUrl builds the hosted-ui logout url", () => {
    const u = cognitoLogoutUrl(cfg);
    expect(u).toContain(`https://${cfg.cognitoDomain}/logout`);
    expect(u).toContain("client_id=client123");
    expect(u).toContain("logout_uri=http%3A%2F%2Flocalhost%3A5173%2F");
  });
});
