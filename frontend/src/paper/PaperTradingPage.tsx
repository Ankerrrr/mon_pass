import { useCallback, useEffect, useState } from "react";

import { listConfigurations, listPaperSessions, startPaperSession, stopPaperSession, systemHealth, type Configuration, type PaperSession } from "../api/client";
import { EmergencyStopButton } from "./EmergencyStopButton";

export function PaperTradingPage() {
  const [sessions, setSessions] = useState<PaperSession[]>([]);
  const [configurations, setConfigurations] = useState<Configuration[]>([]);
  const [selected, setSelected] = useState("");
  const [health, setHealth] = useState<Record<string, string | null>>({});
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const [nextSessions, configs, nextHealth] = await Promise.all([listPaperSessions(), listConfigurations(), systemHealth()]);
      setSessions(nextSessions); setConfigurations(configs); setHealth(nextHealth);
      if (!selected && configs[0]) setSelected(configs[0].id);
      setError("");
    } catch { setError("無法讀取模擬交易狀態"); }
  }, [selected]);
  useEffect(() => { void load(); }, [load]);

  async function start() {
    if (!selected) return;
    await startPaperSession(selected); await load();
  }
  async function stop(id: string) { await stopPaperSession(id); await load(); }

  return <div className="page-stack">
    <section className="safety-banner"><strong>模擬模式｜不會送出真實訂單</strong><span>僅使用 Binance 公開行情，不需要 API Key</span></section>
    <section className="health-grid">
      {["application", "database", "paper_worker", "market_stream"].map((key) => <span key={key}><small>{key.replace("_", " ")}</small><b className={health[key] === "ok" || health[key] === "connected" ? "healthy" : "warning"}>{health[key] ?? "讀取中"}</b></span>)}
    </section>
    <section className="panel">
      <div className="section-heading"><div><p className="eyebrow">LIVE PAPER OPERATIONS</p><h2>即時模擬交易</h2></div><EmergencyStopButton onStopped={load} /></div>
      <div className="start-session"><select aria-label="策略設定" value={selected} onChange={(e) => setSelected(e.target.value)}><option value="">選擇策略設定</option>{configurations.map((item) => <option value={item.id} key={item.id}>{item.name} · v{item.version}</option>)}</select><button className="primary-action" onClick={start} disabled={!selected}>啟動模擬</button></div>
      {error && <p className="form-error">{error}</p>}
      <div className="session-list">{sessions.map((session) => <article className="session-card" key={session.id}>
        <div><span className={`status-dot ${session.status}`} /> <strong>{session.status === "active" ? "執行中" : "已停止"}</strong><small>{session.id.slice(0, 8)} · config v{session.configuration_version}</small></div>
        <div className="ledger-row">{Object.entries(session.state_snapshot.ledgers).map(([name, ledger]) => <span key={name}><small>{name}</small><b>{Number(ledger.cash).toLocaleString()} USDT</b><em>{ledger.fills.length} fills</em></span>)}</div>
        <div><small>最後 K 線：{session.last_candle_at ? new Date(session.last_candle_at).toLocaleString("zh-TW") : "等待行情"}</small>{session.status === "active" && <button className="text-button" onClick={() => stop(session.id)}>停止</button>}</div>
      </article>)}</div>
      {sessions.length === 0 && <div className="quiet-empty">尚無模擬工作。請先建立回測設定，再從上方啟動。</div>}
    </section>
  </div>;
}
