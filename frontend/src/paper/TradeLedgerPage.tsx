import { useEffect, useState } from "react";
import { listPaperSessions, type PaperSession } from "../api/client";

export function TradeLedgerPage() {
  const [sessions, setSessions] = useState<PaperSession[]>([]);
  useEffect(() => { void listPaperSessions().then(setSessions); }, []);
  const rows = sessions.flatMap((session) => Object.entries(session.state_snapshot.ledgers).flatMap(([strategy, ledger]) => ledger.fills.map((fill) => ({ session: session.id, strategy, fill: fill as Record<string, string> }))));
  return <section className="panel"><div className="section-heading"><div><p className="eyebrow">PAPER FILLS</p><h2>交易紀錄</h2></div><span>{rows.length} 筆成交</span></div><div className="trade-table">{rows.map((row, index) => <div key={`${row.session}-${index}`}><span>{row.strategy}</span><strong>{row.fill.side?.toUpperCase()} {row.fill.symbol}</strong><span>{row.fill.quantity} @ {row.fill.price}</span><small>{row.fill.filled_at ? new Date(row.fill.filled_at).toLocaleString("zh-TW") : ""}</small></div>)}</div>{rows.length === 0 && <div className="quiet-empty">尚無模擬成交。</div>}</section>;
}
