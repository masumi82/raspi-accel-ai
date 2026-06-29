export const config = {
  apiUrl: import.meta.env.VITE_API_URL,
  cognitoAuthority: import.meta.env.VITE_COGNITO_AUTHORITY,
  cognitoClientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
  cognitoDomain: import.meta.env.VITE_COGNITO_DOMAIN,
  redirectUri: import.meta.env.VITE_REDIRECT_URI || `${window.location.origin}/`,
  deviceId: import.meta.env.VITE_DEVICE_ID || "raspi-01",
};
