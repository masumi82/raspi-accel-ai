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
        <button onClick={() => { auth.removeUser(); window.location.href = cognitoLogoutUrl(config); }}>
          ログアウト
        </button>
      </header>
      <EventsView token={auth.user?.id_token} />
    </main>
  );
}
