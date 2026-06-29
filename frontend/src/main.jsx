import React from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import { buildOidcConfig } from "./auth";
import { config } from "./config";
import App from "./App";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider {...buildOidcConfig(config)}>
      <App />
    </AuthProvider>
  </React.StrictMode>
);
