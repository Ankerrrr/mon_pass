import { useState } from "react";

import type { Admin } from "../api/client";
import { BacktestBuilder } from "../backtests/BacktestBuilder";
import { BacktestResults } from "../backtests/BacktestResults";
import { OverviewPage } from "../dashboard/OverviewPage";
import { PaperTradingPage } from "../paper/PaperTradingPage";
import { TradeLedgerPage } from "../paper/TradeLedgerPage";
import { ConfigurationsPage } from "../settings/ConfigurationsPage";
import { DataManagementPage } from "../market_data/DataManagementPage";
import { SystemPage } from "../system/SystemPage";

const items = ["總覽", "建立回測", "回測結果", "策略設定", "模擬交易", "交易紀錄", "資料管理", "系統設定"];

export function AppShell({ admin }: { admin: Admin }) {
  const [page, setPage] = useState(0);
  const titles = ["投資組合總覽", "建立回測", "回測結果", "策略設定", "模擬交易", "交易紀錄", "資料管理", "系統設定"];
  const content = page === 1 ? <BacktestBuilder /> : page === 2 ? <BacktestResults /> : page === 3 ? <ConfigurationsPage /> : page === 4 ? <PaperTradingPage /> : page === 5 ? <TradeLedgerPage /> : page === 6 ? <DataManagementPage /> : page === 7 ? <SystemPage /> : <OverviewPage onCreate={() => setPage(1)} />;
  return <div className="app-shell">
    <aside><div className="brand"><span className="brand-mark">QH</span> QUANT HOME</div><nav>{items.map((item, index) => <button className={index === page ? "active" : ""} onClick={() => setPage(index)} key={item}><span>0{index + 1}</span>{item}</button>)}</nav><div className="account"><i>{admin.username.slice(0, 1).toUpperCase()}</i><p>{admin.username}<small>Administrator</small></p></div></aside>
    <main className="workspace"><header><div><p className="eyebrow">QUANT HOME WORKSPACE</p><h1>{titles[page]}</h1></div><div className="simulation-pill"><i /> 模擬模式｜無真實下單</div></header>{content}</main>
  </div>;
}
