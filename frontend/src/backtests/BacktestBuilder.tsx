import { FormEvent, useMemo, useState } from "react";

import { ApiError, createBacktest, createConfiguration } from "../api/client";

function isoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

export function BacktestBuilder() {
  const defaults = useMemo(() => {
    const end = new Date();
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - 180);
    return { start: isoDate(start), end: isoDate(end) };
  }, []);
  const [name, setName] = useState("BTC 三策略基準");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [start, setStart] = useState(defaults.start);
  const [end, setEnd] = useState(defaults.end);
  const [capital, setCapital] = useState("10000");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const normalized = symbol.trim().toUpperCase();
    const universe = (interval: string) => ({ interval, symbols: [{ symbol: normalized, weight: "1" }] });
    const payload = {
      initial_capital: capital,
      start_time: `${start}T00:00:00Z`, end_time: `${end}T00:00:00Z`,
      allocations: { trend: "0.40", mean_reversion: "0.30", grid: "0.20", cash_reserve: "0.10" },
      universes: { trend: universe("4h"), mean_reversion: universe("1h"), grid: universe("15m") },
      trend: {}, mean_reversion: {}, grid: {}, fee_rate: "0.001", slippage_bps: "5",
    };
    try {
      const configuration = await createConfiguration(name.trim(), payload);
      const job = await createBacktest(configuration.id);
      setMessage(`回測工作已送出 · ${job.job_id.slice(0, 8)}`);
    } catch (error) {
      setMessage(error instanceof ApiError ? `無法執行：${error.message}` : "無法執行回測，請稍後重試");
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel builder-panel">
    <div className="section-heading"><div><p className="eyebrow">NEW RESEARCH RUN</p><h2>建立回測</h2></div><span>三策略獨立資金帳本</span></div>
    <form className="builder-form" onSubmit={submit}>
      <label>設定名稱<input aria-label="設定名稱" value={name} onChange={(e) => setName(e.target.value)} required /></label>
      <label>交易對<input aria-label="交易對" value={symbol} onChange={(e) => setSymbol(e.target.value)} pattern="[A-Za-z0-9]+" required /></label>
      <label>開始日期<input type="date" value={start} max={end} onChange={(e) => setStart(e.target.value)} required /></label>
      <label>結束日期<input type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} required /></label>
      <label>初始資金（USDT）<input type="number" min="1" step="0.01" value={capital} onChange={(e) => setCapital(e.target.value)} required /></label>
      <div className="allocation-summary"><small>資金配置</small><strong>趨勢 40% · 均值回歸 30% · 網格 20% · 現金 10%</strong></div>
      <button className="primary-action" type="submit" disabled={busy} aria-label="儲存並執行回測">{busy ? "準備資料中…" : "儲存並執行回測"}<span>→</span></button>
      {message && <p className={message.startsWith("回測") ? "success-message" : "form-error"} role="status">{message}</p>}
    </form>
  </section>;
}
