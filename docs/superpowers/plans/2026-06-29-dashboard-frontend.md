# Dashboard Frontend Implementation Plan (raspi-accel-ai プラン3b/3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** プラン3aのAPIを消費する React/Vite ダッシュボードSPA（Cognito Hosted UI ログイン、加速度の時系列グラフ＋イベント一覧）を実装し、S3+CloudFront でホスティングするインフラを SAM に追加する。

**Architecture:** 純ロジック（API クライアント `api.js`、系列変換 `series.js`、OIDC 設定 `auth.js`）を vitest で TDD。React UI（OIDC 認証・recharts グラフ・一覧表）は `npm run build` で検証。ホスティングは S3（非公開）+ CloudFront（OAC）。Cognito の CallbackURLs と API の CORS を CloudFront ドメインに合わせて更新。

**Tech Stack:** React 18 + Vite 5（JavaScript/JSX）、react-oidc-context + oidc-client-ts（Cognito Hosted UI）、recharts、vitest。ホスティングは S3 + CloudFront + OAC（SAM）。テンプレ検証は cfn-lint。

## Global Constraints

- フロントは `frontend/`。Node はインストール済み（npm registry 到達可）。`npm ci`/`npm install` 可
- 秘密情報を持たせない：Cognito クライアントは public（client secret なし）。設定は `import.meta.env`（`VITE_*`）。`frontend/.env` は Git 除外済み、`.env.example` を用意
- API 呼び出しは必ず `Authorization: Bearer <IdToken>`。HTTPS 前提
- 純ロジック（api/series/auth）は vitest で TDD。UI コンポーネントは `npm run build` 成功で検証（recharts/OIDC は jsdom テストしない）
- vitest は node 環境（jsdom 不要）。テストは `frontend/test/`
- S3 バケットは非公開（CloudFront OAC 経由のみ）。CloudFront は redirect-to-https、SPA フォールバック（403/404→index.html）
- 既存 `cloud/template.yaml` は「ホスティング追加」と「UserPoolClient/CORS の CloudFront 対応更新」のみ変更（他リソースは不変）

## File Structure

```
frontend/
  package.json          vite.config.js     index.html     .env.example
  src/
    main.jsx            config.js          auth.js        api.js        series.js
    App.jsx
    components/ EventsView.jsx  EventsChart.jsx  EventsTable.jsx
  test/
    api.test.js         series.test.js     auth.test.js
cloud/template.yaml     # 追加: S3/CloudFront/OAC/BucketPolicy、UserPoolClient/CORS 更新、Outputs
```

---

### Task 1: フロント雛形とツールチェーン

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`, `frontend/.env.example`
- Create: `frontend/src/main.jsx`, `frontend/src/App.jsx`（最小、後続で差し替え）

**Interfaces:**
- Consumes: なし
- Produces: ビルド可能な最小 Vite+React アプリ、vitest 実行環境

- [ ] **Step 1: ファイルを作成**

`frontend/package.json`:

```json
{
  "name": "raspi-accel-ai-dashboard",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-oidc-context": "^3.2.0",
    "oidc-client-ts": "^3.1.0",
    "recharts": "^2.13.3"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^5.4.11",
    "vitest": "^2.1.8"
  }
}
```

`frontend/vite.config.js`:

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "node" },
});
```

`frontend/index.html`:

```html
<!doctype html>
<html lang="ja">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>raspi-accel-ai dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`frontend/.env.example`:

```
VITE_API_URL=https://xxxx.execute-api.ap-northeast-1.amazonaws.com
VITE_COGNITO_AUTHORITY=https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_xxxxx
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxx
VITE_COGNITO_DOMAIN=raspi-accel-ai-123456789012.auth.ap-northeast-1.amazoncognito.com
VITE_REDIRECT_URI=http://localhost:5173/
VITE_DEVICE_ID=raspi-01
```

`frontend/src/main.jsx`:

```jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

`frontend/src/App.jsx`（最小・後続タスクで差し替え）:

```jsx
export default function App() {
  return <h1>raspi-accel-ai dashboard</h1>;
}
```

- [ ] **Step 2: 依存をインストール**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm install`
Expected: 成功（`node_modules/` 作成、`package-lock.json` 生成）。ネットワーク不可で失敗した場合は BLOCKED 報告。

- [ ] **Step 3: ビルド検証**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm run build`
Expected: `dist/` が生成され `built in` で終了（エラーなし）

- [ ] **Step 4: Commit**

`package-lock.json` も含める（`node_modules/`・`dist/` は .gitignore 済み）。

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/index.html frontend/.env.example frontend/src/main.jsx frontend/src/App.jsx
git commit -m "feat(frontend): scaffold vite react dashboard app"
```

---

### Task 2: OIDC 設定 (auth.js) と config.js

**Files:**
- Create: `frontend/src/config.js`
- Create: `frontend/src/auth.js`
- Test: `frontend/test/auth.test.js`

**Interfaces:**
- Consumes: なし
- Produces:
  - `config`（`import.meta.env` 由来。テスト対象外）
  - `buildOidcConfig(cfg) -> object`（authority/client_id/redirect_uri/post_logout_redirect_uri/response_type="code"/scope="openid email profile"）
  - `cognitoLogoutUrl(cfg) -> string`（Cognito Hosted UI の `/logout` URL）

- [ ] **Step 1: 失敗するテストを書く**

`frontend/test/auth.test.js`:

```js
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm test -- test/auth.test.js`
Expected: FAIL（`Failed to resolve import "../src/auth"`）

- [ ] **Step 3: 実装を書く**

`frontend/src/config.js`:

```js
export const config = {
  apiUrl: import.meta.env.VITE_API_URL,
  cognitoAuthority: import.meta.env.VITE_COGNITO_AUTHORITY,
  cognitoClientId: import.meta.env.VITE_COGNITO_CLIENT_ID,
  cognitoDomain: import.meta.env.VITE_COGNITO_DOMAIN,
  redirectUri: import.meta.env.VITE_REDIRECT_URI || `${window.location.origin}/`,
  deviceId: import.meta.env.VITE_DEVICE_ID || "raspi-01",
};
```

`frontend/src/auth.js`:

```js
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm test -- test/auth.test.js`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/config.js frontend/src/auth.js frontend/test/auth.test.js
git commit -m "feat(frontend): add oidc config and cognito logout url"
```

---

### Task 3: API クライアント (api.js)

**Files:**
- Create: `frontend/src/api.js`
- Test: `frontend/test/api.test.js`

**Interfaces:**
- Consumes: なし
- Produces: `async fetchEvents(apiUrl, token, deviceId="raspi-01", limit=50) -> object`（`GET {apiUrl}/events?deviceId=&limit=` に Bearer 付与。非 ok は throw）

- [ ] **Step 1: 失敗するテストを書く**

`frontend/test/api.test.js`:

```js
import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchEvents } from "../src/api";

afterEach(() => vi.restoreAllMocks());

describe("fetchEvents", () => {
  it("calls the events endpoint with bearer token and returns json", async () => {
    const json = { deviceId: "raspi-01", count: 1, events: [{ ts: "t1" }] };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => json });
    const out = await fetchEvents("https://api.example", "TOKEN", "raspi-01", 10);
    expect(out).toEqual(json);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain("/events?deviceId=raspi-01&limit=10");
    expect(opts.headers.Authorization).toBe("Bearer TOKEN");
  });

  it("throws on non-ok response", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    await expect(fetchEvents("https://api.example", "T")).rejects.toThrow("401");
  });
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm test -- test/api.test.js`
Expected: FAIL（`Failed to resolve import "../src/api"`）

- [ ] **Step 3: 実装を書く**

`frontend/src/api.js`:

```js
export async function fetchEvents(apiUrl, token, deviceId = "raspi-01", limit = 50) {
  const url = `${apiUrl}/events?deviceId=${encodeURIComponent(deviceId)}&limit=${limit}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}`);
  }
  return res.json();
}
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm test -- test/api.test.js`
Expected: PASS（2 passed）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.js frontend/test/api.test.js
git commit -m "feat(frontend): add authenticated events api client"
```

---

### Task 4: 系列変換 (series.js)

**Files:**
- Create: `frontend/src/series.js`
- Test: `frontend/test/series.test.js`

**Interfaces:**
- Consumes: なし
- Produces: `toSeries(events) -> array`（ts 昇順、`{ts, mag_peak, mag_rms, tilt_deg, label, severity}`。features 欠損は null）

- [ ] **Step 1: 失敗するテストを書く**

`frontend/test/series.test.js`:

```js
import { describe, it, expect } from "vitest";
import { toSeries } from "../src/series";

describe("toSeries", () => {
  it("sorts oldest-first and maps features", () => {
    const events = [
      { ts: "2026-06-29T12:05:00Z", features: { mag_peak: 3.2, mag_rms: 1.0, tilt_deg: 45 }, label: "impact", severity: "high" },
      { ts: "2026-06-29T12:00:00Z", features: { mag_peak: 1.0, mag_rms: 0.0, tilt_deg: 0 }, label: "normal", severity: "low" },
    ];
    const s = toSeries(events);
    expect(s.map((x) => x.ts)).toEqual(["2026-06-29T12:00:00Z", "2026-06-29T12:05:00Z"]);
    expect(s[1].mag_peak).toBe(3.2);
    expect(s[0].label).toBe("normal");
  });

  it("handles missing features", () => {
    const s = toSeries([{ ts: "t1", label: "x", severity: "low" }]);
    expect(s[0].mag_peak).toBeNull();
  });

  it("does not mutate the input array", () => {
    const events = [{ ts: "b" }, { ts: "a" }];
    toSeries(events);
    expect(events.map((e) => e.ts)).toEqual(["b", "a"]);
  });
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm test -- test/series.test.js`
Expected: FAIL（`Failed to resolve import "../src/series"`）

- [ ] **Step 3: 実装を書く**

`frontend/src/series.js`:

```js
export function toSeries(events) {
  return [...events]
    .sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
    .map((e) => ({
      ts: e.ts,
      mag_peak: e.features?.mag_peak ?? null,
      mag_rms: e.features?.mag_rms ?? null,
      tilt_deg: e.features?.tilt_deg ?? null,
      label: e.label,
      severity: e.severity,
    }));
}
```

- [ ] **Step 4: テストが通ることを確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm test -- test/series.test.js`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/series.js frontend/test/series.test.js
git commit -m "feat(frontend): add event-to-series transform"
```

---

### Task 5: UI コンポーネントと認証ゲート

**Files:**
- Create: `frontend/src/components/EventsTable.jsx`, `frontend/src/components/EventsChart.jsx`, `frontend/src/components/EventsView.jsx`
- Modify: `frontend/src/App.jsx`（認証ゲート）, `frontend/src/main.jsx`（AuthProvider）

**Interfaces:**
- Consumes: `useAuth`(react-oidc-context), `buildOidcConfig`, `cognitoLogoutUrl`, `config`, `fetchEvents`, `toSeries`
- Produces: ログイン/ログアウト付きダッシュボード。検証はビルド（vitest 対象外）

- [ ] **Step 1: コンポーネントを作成**

`frontend/src/components/EventsTable.jsx`:

```jsx
const SEV_COLOR = { low: "#2e7d32", medium: "#ed6c02", high: "#d32f2f" };

export default function EventsTable({ events }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 16 }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left" }}>時刻</th>
          <th style={{ textAlign: "left" }}>種別</th>
          <th style={{ textAlign: "left" }}>深刻度</th>
          <th style={{ textAlign: "left" }}>説明</th>
        </tr>
      </thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.ts} style={{ borderTop: "1px solid #ddd" }}>
            <td>{e.ts}</td>
            <td>{e.label}</td>
            <td style={{ color: SEV_COLOR[e.severity] || "#333" }}>{e.severity}</td>
            <td>{e.explanation}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

`frontend/src/components/EventsChart.jsx`:

```jsx
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from "recharts";

export default function EventsChart({ series }) {
  return (
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <LineChart data={series}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="ts" hide />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="mag_peak" stroke="#8884d8" dot={false} />
          <Line type="monotone" dataKey="mag_rms" stroke="#82ca9d" dot={false} />
          <Line type="monotone" dataKey="tilt_deg" stroke="#ffc658" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

`frontend/src/components/EventsView.jsx`:

```jsx
import { useEffect, useState } from "react";
import { config } from "../config";
import { fetchEvents } from "../api";
import { toSeries } from "../series";
import EventsChart from "./EventsChart";
import EventsTable from "./EventsTable";

export default function EventsView({ token }) {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchEvents(config.apiUrl, token, config.deviceId, 100)
      .then((d) => active && setEvents(d.events || []))
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token]);

  if (loading) return <p>読み込み中…</p>;
  if (error) return <p>取得エラー: {error}</p>;
  if (events.length === 0) return <p>イベントがありません。</p>;

  return (
    <section>
      <EventsChart series={toSeries(events)} />
      <EventsTable events={events} />
    </section>
  );
}
```

- [ ] **Step 2: App と main を更新**

`frontend/src/App.jsx`（全置換）:

```jsx
import { useAuth } from "react-oidc-context";
import { cognitoLogoutUrl } from "./auth";
import { config } from "./config";
import EventsView from "./components/EventsView";

export default function App() {
  const auth = useAuth();

  if (auth.isLoading) return <p style={{ padding: 24 }}>読み込み中…</p>;
  if (auth.error) return <p style={{ padding: 24 }}>認証エラー: {auth.error.message}</p>;

  if (!auth.isAuthenticated) {
    return (
      <main style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
        <h1>raspi-accel-ai dashboard</h1>
        <button onClick={() => auth.signinRedirect()}>ログイン</button>
      </main>
    );
  }

  return (
    <main style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>raspi-accel-ai dashboard</h1>
        <button onClick={() => { window.location.href = cognitoLogoutUrl(config); }}>
          ログアウト
        </button>
      </header>
      <EventsView token={auth.user?.id_token} />
    </main>
  );
}
```

`frontend/src/main.jsx`（全置換）:

```jsx
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
```

- [ ] **Step 3: ビルドと既存テストを検証**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/frontend && npm run build && npm test`
Expected: ビルド成功（`dist/` 生成）＋ vitest 全 passed（auth/api/series）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx frontend/src/main.jsx frontend/src/components/
git commit -m "feat(frontend): add auth gate, events chart and table"
```

---

### Task 6: ホスティングインフラ（S3 + CloudFront）と Cognito/CORS 更新

**Files:**
- Modify: `cloud/template.yaml`

**Interfaces:**
- Consumes: 既存 `UserPool`/`UserPoolClient`/`DashboardApi`
- Produces: 非公開 S3 + CloudFront(OAC)。UserPoolClient の Callback/Logout と API CORS に CloudFront ドメインを反映。Outputs: `FrontendBucketName`, `FrontendUrl`

- [ ] **Step 1: Resources に追記（`UserPoolDomain` の後など Resources 内）**

`cloud/template.yaml` の `Resources:` に追加:

```yaml
  FrontendBucket:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true

  FrontendOAC:
    Type: AWS::CloudFront::OriginAccessControl
    Properties:
      OriginAccessControlConfig:
        Name: !Sub "raspi-accel-ai-oac-${AWS::AccountId}"
        OriginAccessControlOriginType: s3
        SigningBehavior: always
        SigningProtocol: sigv4

  FrontendDistribution:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Enabled: true
        DefaultRootObject: index.html
        Origins:
          - Id: s3origin
            DomainName: !GetAtt FrontendBucket.RegionalDomainName
            OriginAccessControlId: !Ref FrontendOAC
            S3OriginConfig:
              OriginAccessIdentity: ""
        DefaultCacheBehavior:
          TargetOriginId: s3origin
          ViewerProtocolPolicy: redirect-to-https
          CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6
        CustomErrorResponses:
          - ErrorCode: 403
            ResponseCode: 200
            ResponsePagePath: /index.html
          - ErrorCode: 404
            ResponseCode: 200
            ResponsePagePath: /index.html

  FrontendBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref FrontendBucket
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: cloudfront.amazonaws.com
            Action: s3:GetObject
            Resource: !Sub "${FrontendBucket.Arn}/*"
            Condition:
              StringEquals:
                AWS:SourceArn: !Sub "arn:aws:cloudfront::${AWS::AccountId}:distribution/${FrontendDistribution}"
```

- [ ] **Step 2: UserPoolClient と DashboardApi CORS を CloudFront 対応に更新**

`cloud/template.yaml` の `UserPoolClient.Properties` の `CallbackURLs` / `LogoutURLs` を次に置換:

```yaml
      CallbackURLs:
        - http://localhost:5173/
        - !Sub "https://${FrontendDistribution.DomainName}/"
      LogoutURLs:
        - http://localhost:5173/
        - !Sub "https://${FrontendDistribution.DomainName}/"
```

`cloud/template.yaml` の `DashboardApi.Properties.CorsConfiguration.AllowOrigins` を次に置換（ワイルドカード撤廃）:

```yaml
        AllowOrigins:
          - http://localhost:5173
          - !Sub "https://${FrontendDistribution.DomainName}"
```

- [ ] **Step 3: Outputs に追記**

```yaml
  FrontendBucketName:
    Value: !Ref FrontendBucket
  FrontendUrl:
    Value: !Sub "https://${FrontendDistribution.DomainName}"
```

- [ ] **Step 4: テンプレートを検証**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/cloud && /home/m-horiuchi/persol_ws/raspi-accel-ai/.venv/bin/cfn-lint template.yaml`
Expected: E(エラー)0件で exit 0。W 警告は全文報告（ブロッカーではない）。既存リソースが UserPoolClient/CORS 以外変更されていないことを確認。

- [ ] **Step 5: クラウドテスト回帰確認**

Run: `cd /home/m-horiuchi/persol_ws/raspi-accel-ai/cloud && /home/m-horiuchi/persol_ws/raspi-accel-ai/.venv/bin/python -m pytest tests/ -q`
Expected: 全テスト緑（28）

- [ ] **Step 6: Commit**

```bash
git add cloud/template.yaml
git commit -m "feat(cloud): add s3+cloudfront spa hosting and scope cognito/cors to cloudfront"
```

---

### Task 7: フロント README とトップ README 更新

**Files:**
- Create: `frontend/README.md`
- Modify: `README.md`（ロードマップでプラン3完了を反映、ダッシュボード状態を ✅ に）

**Interfaces:**
- Consumes: 全タスク
- Produces: ビルド/デプロイ手順、トップ README のステータス更新

- [ ] **Step 1: フロント README を作成**

`frontend/README.md`:

````markdown
# raspi-accel-ai dashboard (frontend)

React + Vite の SPA。Cognito Hosted UI でログインし、ダッシュボードAPI(プラン3a)から
加速度イベントを取得して時系列グラフと一覧で表示する。

## セットアップ
```bash
cd frontend
npm install
cp .env.example .env   # 値を sam デプロイの Outputs で埋める
```
`.env` に設定する値（`cloud` スタックの Outputs より）:
- `VITE_API_URL` = DashboardApiUrl
- `VITE_COGNITO_AUTHORITY` = `https://cognito-idp.<region>.amazonaws.com/<UserPoolId>`
- `VITE_COGNITO_CLIENT_ID` = UserPoolClientId
- `VITE_COGNITO_DOMAIN` = HostedUiDomain
- `VITE_REDIRECT_URI` = ローカルは `http://localhost:5173/`、本番は `FrontendUrl` ＋ `/`
- `VITE_DEVICE_ID` = 例 `raspi-01`

## 開発
```bash
npm run dev      # http://localhost:5173
npm test         # vitest (api/series/auth)
npm run build    # dist/ を生成
```

## デプロイ（S3 + CloudFront）
```bash
npm run build
aws s3 sync dist/ "s3://<FrontendBucketName>/" --delete
aws cloudfront create-invalidation --distribution-id <DistId> --paths '/*'
```
`FrontendUrl`（CloudFront ドメイン）にアクセス → Cognito Hosted UI ログイン → ダッシュボード表示。
（CloudFront ドメインは Cognito CallbackURLs と API CORS に登録済み。`.env` の REDIRECT_URI を本番URLにして再ビルドすること。）

## テスト方針
純ロジック（`api.js`/`series.js`/`auth.js`）は vitest で検証。React UI（OIDC・recharts）は
`npm run build` の成功で検証する。
````

- [ ] **Step 2: トップ README のロードマップ更新**

`README.md` のロードマップで `- [ ] プラン3: ダッシュボード...` を `- [x]` に変更し、コンポーネント表の frontend 行の状態を `🔜 予定` → `✅ 完了`、ドキュメント列を `[frontend/README.md](frontend/README.md)` に更新する。

- [ ] **Step 3: Commit**

```bash
git add frontend/README.md README.md
git commit -m "docs: add frontend README and mark dashboard complete"
```

---

## Self-Review

**1. Spec coverage（design spec §6 / フロント要件 → タスク）**
- 自作軽量Webアプリ(React+Vite) → Task 1/5
- Cognito ログイン → Task 2（OIDC設定）+ Task 5（AuthProvider/認証ゲート）
- API から取得 → Task 3（fetchEvents, Bearer）
- 時系列グラフ → Task 4（series）+ Task 5（EventsChart/recharts）
- LLM 判定（label/severity/explanation）一覧 → Task 5（EventsTable）
- S3 + CloudFront ホスティング → Task 6
- 認証/CORS を本番オリジンにスコープ（3a の据え置き解消）→ Task 6
- ドキュメント → Task 7

**2. Placeholder scan:** TBD/「適切に処理」等なし。各コードステップに実コードあり。`.env.example` のダミー値はプレースホルダではなくサンプル。

**3. Type/contract consistency:** `fetchEvents(apiUrl, token, deviceId, limit)` は Task 3 定義・Task 5 消費で一致。`toSeries` の入力はAPIの `events`（3a の `{ts, features, label, severity, explanation}`）と一致。`buildOidcConfig`/`cognitoLogoutUrl` は Task 2 定義・Task 5(main/App) 消費で一致。CloudFront ドメイン参照（`FrontendDistribution.DomainName`）は Task 6 内で UserPoolClient/CORS/Output に一貫使用。

**意図的にビルド検証（ユニット非対象）:** React コンポーネント（App/EventsView/EventsChart/EventsTable）、OIDC 実フロー、CloudFront 実配信。これらは `npm run build` 成功＋実デプロイで検証。
