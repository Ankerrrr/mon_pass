import { useState } from "react";

import type { StrategyLedger } from "../api/client";

const strategyNames: Record<string, string> = {
  trend: "趨勢策略",
  mean_reversion: "均值回歸",
  grid: "網格策略",
};

const money = (value: string | number, signed = false) => {
  const number = Number(value);
  const formatted = new Intl.NumberFormat("zh-TW", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(number);
  return `${signed && number > 0 ? "+" : ""}${formatted}`;
};

const tone = (value: string) => Number(value) > 0 ? "profit" : Number(value) < 0 ? "loss" : "";

export function StrategyLedgerDetails({ strategy, ledger }: { strategy: string; ledger: StrategyLedger }) {
  const [visible, setVisible] = useState(20);
  const summary = ledger.summary;
  const operations = ledger.operations ?? [];

  return <details className="strategy-ledger">
    <summary>
      <span><small>STRATEGY</small><strong>{strategyNames[strategy] ?? strategy}</strong></span>
      <span><small>期末總資產</small><strong>{money(summary.ending_equity)} USDT</strong></span>
      <span><small>總收益</small><strong className={tone(summary.total_pnl)}>{money(summary.total_pnl, true)} USDT</strong></span>
      <span><small>報酬率</small><strong className={tone(summary.total_return)}>{money(Number(summary.total_return) * 100, true)}%</strong></span>
      <span><small>操作</small><strong>{summary.fill_count} 筆</strong></span>
    </summary>
    <div className="strategy-detail-body">
      {summary.valuation_is_estimated && <p className="estimate-note">未平倉部位以最後成交價估算；重新執行回測後可使用期末收盤價。</p>}
      <div className="result-metrics">
        <span><small>初始資金</small><b>{money(summary.initial_cash)}</b></span>
        <span><small>期末現金</small><b>{money(summary.ending_cash)}</b></span>
        <span><small>持倉價值</small><b>{money(summary.position_value)}</b></span>
        <span><small>已實現收益</small><b className={tone(summary.realized_pnl)}>{money(summary.realized_pnl, true)}</b></span>
        <span><small>未實現收益</small><b className={tone(summary.unrealized_pnl)}>{money(summary.unrealized_pnl, true)}</b></span>
        <span><small>累計手續費</small><b>{money(summary.fees)}</b></span>
      </div>
      <h4>操作紀錄</h4>
      {operations.length === 0 ? <div className="operation-empty">尚無買賣操作</div> : <div className="operation-table">
        <div className="operation-head"><span>時間 / 交易</span><span>數量 × 價格</span><span>現金增減</span><span>操作後資產</span><span>資產增減</span></div>
        {operations.slice(0, visible).map((operation, index) => <div className="operation-row" key={`${operation.filled_at}-${index}`}>
          <span><time>{operation.filled_at ? new Date(operation.filled_at).toLocaleString("zh-TW") : "—"}</time><b className={operation.side}>{operation.side === "buy" ? "買入" : "賣出"} {operation.symbol}</b></span>
          <span><b>{operation.quantity} × {money(operation.price)}</b><small>名目 {money(operation.notional)} · 費用 {money(operation.fee)}</small></span>
          <span className={tone(operation.cash_delta)}>{money(operation.cash_delta, true)} USDT</span>
          <span><b>{money(operation.equity_after)} USDT</b><small>現金 {money(operation.cash_after)}</small></span>
          <span className={tone(operation.equity_change)}><b>{money(operation.equity_change, true)} USDT</b><small>已實現 {money(operation.realized_pnl, true)}</small></span>
        </div>)}
        {visible < operations.length && <button className="show-more" onClick={() => setVisible((count) => count + 20)}>顯示更多（尚有 {operations.length - visible} 筆）</button>}
      </div>}
    </div>
  </details>;
}
