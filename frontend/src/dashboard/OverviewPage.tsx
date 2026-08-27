import { BacktestResults } from "../backtests/BacktestResults";

export function OverviewPage({ onCreate }: { onCreate: () => void }) {
  return <div className="page-stack">
    <section className="hero-dashboard"><div><p className="eyebrow">READY TO RESEARCH</p><h2>從公開市場資料，建立可重現的策略實驗。</h2><p>三種策略使用獨立帳本；成交費用、滑價與風險限制皆納入結果。</p></div><button className="primary-action" onClick={onCreate}>建立回測 <span>→</span></button></section>
    <BacktestResults compact />
  </div>;
}
