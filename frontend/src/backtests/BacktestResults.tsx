import { useEffect, useState } from "react";

import { listBacktests, type BacktestRun } from "../api/client";

const money = (value: string) => new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 2 }).format(Number(value));

export function BacktestResults({ compact = false }: { compact?: boolean }) {
  const [runs, setRuns] = useState<BacktestRun[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { listBacktests().then(setRuns).catch(() => setError("目前無法讀取回測結果")); }, []);

  return <section className="panel results-panel">
    <div className="section-heading"><div><p className="eyebrow">REPRODUCIBLE RESULTS</p><h2>{compact ? "最近回測" : "回測結果"}</h2></div><span>{runs.length} 次完成</span></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {!error && runs.length === 0 && <div className="quiet-empty">尚無完成的回測。建立工作後可在這裡比較三個策略。</div>}
    <div className="run-list">{runs.slice(0, compact ? 3 : undefined).map((run) => {
      const ledgers = Object.entries(run.result_snapshot.ledgers);
      return <article className="run-card" key={run.id}>
        <div><small>{new Date(run.created_at).toLocaleString("zh-TW")}</small><strong>{run.configuration_snapshot.name ?? "策略回測"}</strong><code>{run.fingerprint.slice(0, 12)}</code></div>
        <div className="ledger-row">{ledgers.map(([strategy, ledger]) => <span key={strategy}><small>{strategy.replace("mean_reversion", "mean rev.")}</small><b>{money(ledger.cash)} USDT</b><em>{ledger.fills.length} fills</em></span>)}</div>
        <a className="text-link" href={`/api/backtests/${run.id}/trades.csv`}>匯出交易 CSV ↓</a>
      </article>;
    })}</div>
  </section>;
}
