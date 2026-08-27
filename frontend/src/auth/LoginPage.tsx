import { FormEvent, useState } from "react";

import { ApiError, type Admin, login } from "../api/client";

export function LoginPage({ onAuthenticated }: { onAuthenticated: (admin: Admin) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onAuthenticated(await login(username, password));
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 401 ? "帳號或密碼錯誤" : "登入失敗，請確認服務狀態後重試");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-story" aria-label="產品介紹">
        <div className="brand"><span className="brand-mark">QH</span> QUANT HOME</div>
        <p className="eyebrow">BINANCE SPOT · RESEARCH TERMINAL</p>
        <h1>讓每一筆策略決策，<br /><em>都有跡可循。</em></h1>
        <p className="lede">在自己的電腦上完成資料驗證、多策略回測與即時模擬。資金彼此隔離，結果可以重現。</p>
        <div className="feature-line"><span>01</span><p><strong>三策略並行</strong><small>趨勢 · 均值回歸 · 網格</small></p></div>
        <div className="feature-line"><span>02</span><p><strong>保守成交模型</strong><small>手續費、滑價與風險上限</small></p></div>
      </section>
      <section className="login-panel">
        <div className="simulation-pill"><i /> 模擬模式｜不會送出真實訂單</div>
        <form className="login-card" onSubmit={submit}>
          <p className="eyebrow">ADMIN ACCESS</p>
          <h2>登入研究工作台</h2>
          <p className="muted">使用這台主機設定的管理員帳號。</p>
          <label>管理員帳號<input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} /></label>
          <label>密碼<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" aria-label="登入工作台" disabled={busy}>{busy ? "驗證中…" : "登入工作台"}<span aria-hidden="true">→</span></button>
          <p className="local-note">● 本機加密工作階段 · 僅供可信任網路使用</p>
        </form>
      </section>
    </main>
  );
}
