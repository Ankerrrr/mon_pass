import { useEffect, useState } from "react";

import { listAuditEvents, systemHealth, type AuditEvent } from "../api/client";

export function SystemPage() {
  const [health, setHealth] = useState<Record<string, string | null>>({});
  const [events, setEvents] = useState<AuditEvent[]>([]);
  useEffect(() => { void Promise.all([systemHealth().then(setHealth), listAuditEvents().then(setEvents)]); }, []);
  return <div className="page-stack"><section className="health-grid">{["application", "database", "paper_worker", "market_stream"].map((key) => <span key={key}><small>{key}</small><b>{health[key] ?? "讀取中"}</b></span>)}</section><section className="panel"><div className="section-heading"><div><p className="eyebrow">AUDIT TRAIL</p><h2>操作稽核</h2></div><span>最近 {events.length} 筆</span></div><div className="management-list">{events.map((item) => <article key={item.id}><div><strong>{item.action}</strong><small>{item.subject_type} · {item.subject_id ?? "全部"}</small></div><time>{new Date(item.created_at).toLocaleString("zh-TW")}</time></article>)}</div></section></div>;
}
