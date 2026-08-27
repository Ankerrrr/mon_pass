import { useEffect, useState } from "react";

import { deleteDataset, listDatasets, refreshSymbols, type Dataset } from "../api/client";

export function DataManagementPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [notice, setNotice] = useState("");
  const load = () => listDatasets().then(setDatasets);
  useEffect(() => { void load(); }, []);
  return <section className="panel"><div className="section-heading"><div><p className="eyebrow">MARKET DATA CACHE</p><h2>資料管理</h2></div><button className="primary-action" onClick={async () => { const result = await refreshSymbols(); setNotice(`已更新 ${result.total_symbols} 個 USDT 現貨交易對`); }}>更新交易對</button></div>
    {notice && <p className="success-message">{notice}</p>}
    <div className="management-list">{datasets.map((item) => <article key={item.id}><div><strong>{item.symbol} · {item.interval}</strong><small>{item.candle_count.toLocaleString()} 根 K 線 · {item.is_valid ? "驗證通過" : "資料異常"} · 引用 {item.reference_count}</small></div><code>{item.fingerprint.slice(0, 14)}</code><button disabled={item.reference_count > 0} onClick={async () => { await deleteDataset(item.id); await load(); }}>刪除未使用資料</button></article>)}</div>
    {datasets.length === 0 && <div className="quiet-empty">尚無快取資料；執行回測時會自動下載並驗證。</div>}
  </section>;
}
