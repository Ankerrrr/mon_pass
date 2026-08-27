import { useEffect, useState } from "react";

import { cloneConfiguration, deleteConfiguration, exportConfiguration, listConfigurations, type Configuration } from "../api/client";

export function ConfigurationsPage() {
  const [items, setItems] = useState<Configuration[]>([]);
  const load = () => listConfigurations().then(setItems);
  useEffect(() => { void load(); }, []);
  async function exportItem(item: Configuration) {
    const data = await exportConfiguration(item.id);
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${item.name}-v${item.version}.json`; anchor.click(); URL.revokeObjectURL(url);
  }
  return <section className="panel"><div className="section-heading"><div><p className="eyebrow">VERSIONED CONFIGURATIONS</p><h2>策略設定</h2></div><span>{items.length} 組設定</span></div>
    <div className="management-list">{items.map((item) => <article key={item.id}><div><strong>{item.name}</strong><small>版本 {item.version}</small></div><div><button onClick={() => exportItem(item)}>匯出</button><button onClick={async () => { await cloneConfiguration(item.id, `${item.name} 副本`); await load(); }}>複製</button><button className="danger-link" onClick={async () => { if (confirm(`刪除「${item.name}」？`)) { await deleteConfiguration(item.id); await load(); } }}>刪除</button></div></article>)}</div>
    {items.length === 0 && <div className="quiet-empty">尚無設定。請由「建立回測」新增。</div>}
  </section>;
}
