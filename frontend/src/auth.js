export function buildOidcConfig(cfg) {
  return {
    authority: cfg.cognitoAuthority,
    client_id: cfg.cognitoClientId,
    redirect_uri: cfg.redirectUri,
    post_logout_redirect_uri: cfg.redirectUri,
    response_type: "code",
    scope: "openid email profile",
  };
}

export function cognitoLogoutUrl(cfg) {
  const r = encodeURIComponent(cfg.redirectUri);
  return `https://${cfg.cognitoDomain}/logout?client_id=${cfg.cognitoClientId}&logout_uri=${r}`;
}
