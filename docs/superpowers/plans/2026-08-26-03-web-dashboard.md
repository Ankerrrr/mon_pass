# Responsive Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the authenticated desktop/mobile dashboard for configuring, running, comparing, and exporting multi-strategy backtests.

**Architecture:** A React single-page application consumes typed FastAPI JSON endpoints through one API client. Server state uses TanStack Query; editable forms use React Hook Form and schema validation; chart adapters isolate the chart library from domain views.

**Tech Stack:** Node.js 20, React 19, TypeScript, Vite, TanStack Query, React Hook Form, Zod, Lightweight Charts, Vitest, Testing Library, Playwright

**Spec:** `docs/superpowers/specs/2026-08-26-binance-multi-strategy-backtest-design.md`

## Global Constraints

- The UI always displays simulation mode and never requests a Binance private credential.
- Desktop uses left navigation; mobile uses a compact menu and single-column cards.
- All authorization decisions remain server-side; client guards improve navigation only.
- Strategy allocations plus reserve and each strategy's symbol weights must total 100% before submission.
- Large symbol selections remain usable through search, virtualization, and queued server work.

---

### Task 1: Frontend Shell, Typed API Client, and Login

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/auth/LoginPage.tsx`
- Create: `frontend/src/layout/AppShell.tsx`
- Test: `frontend/src/auth/LoginPage.test.tsx`
- Test: `frontend/e2e/auth.spec.ts`

**Interfaces:**
- Produces: `api.request<T>(path: string, init?: RequestInit) -> Promise<T>`
- Produces: `useCurrentAdmin()` and authenticated `AppShell`

- [ ] **Step 1: Write failing login and unauthenticated-redirect tests**

```tsx
it("submits credentials and opens the dashboard", async () => {
  render(<LoginPage />);
  await userEvent.type(screen.getByLabelText("管理員帳號"), "admin");
  await userEvent.type(screen.getByLabelText("密碼"), "secret-value");
  await userEvent.click(screen.getByRole("button", { name: "登入" }));
  expect(await screen.findByText("投資組合總覽")).toBeVisible();
});
```

- [ ] **Step 2: Verify frontend tests fail**

Run: `docker compose run --rm web npm test -- LoginPage.test.tsx`

Expected: FAIL because the frontend does not exist.

- [ ] **Step 3: Implement the API client, CSRF header handling, login, logout, route guard, and responsive shell**

```ts
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, credentials: "same-origin" });
  if (response.status === 401) throw new AuthenticationRequired();
  if (!response.ok) throw await ApiError.fromResponse(response);
  return response.json() as Promise<T>;
}
```

- [ ] **Step 4: Run unit and Playwright login tests**

Run: `docker compose run --rm web npm test -- LoginPage.test.tsx`

Run: `docker compose run --rm e2e npx playwright test frontend/e2e/auth.spec.ts`

Expected: PASS at desktop and mobile viewport sizes.

- [ ] **Step 5: Commit frontend shell**

```bash
git add frontend compose.yaml
git commit -m "feat: add authenticated dashboard shell"
```

### Task 2: Backtest Builder and Adjustable Strategy Forms

**Files:**
- Create: `frontend/src/backtests/BacktestBuilderPage.tsx`
- Create: `frontend/src/backtests/schema.ts`
- Create: `frontend/src/backtests/SymbolPicker.tsx`
- Create: `frontend/src/backtests/AllocationEditor.tsx`
- Create: `frontend/src/strategies/TrendForm.tsx`
- Create: `frontend/src/strategies/MeanReversionForm.tsx`
- Create: `frontend/src/strategies/GridForm.tsx`
- Test: `frontend/src/backtests/BacktestBuilderPage.test.tsx`

**Interfaces:**
- Produces: `BacktestFormValues` matching `CreateBacktestRequest`
- Consumes: `/symbols`, `/strategy-configurations`, and `/backtests`

- [ ] **Step 1: Write failing unlimited-selection, rebalance, and validation tests**

```tsx
it("equalizes weights and blocks totals above 100 percent", async () => {
  render(<BacktestBuilderPage />);
  await selectSymbols(["BTCUSDT", "ETHUSDT", "SOLUSDT"]);
  await userEvent.click(screen.getByRole("button", { name: "重新平均" }));
  expect(weightInputs()).toHaveValues(["33.3333", "33.3333", "33.3334"]);
  await setStrategyAllocations([40, 30, 20, 20]);
  expect(screen.getByText("策略比例與現金保留必須合計 100%")) .toBeVisible();
});
```

- [ ] **Step 2: Verify builder tests fail**

Run: `docker compose run --rm web npm test -- BacktestBuilderPage.test.tsx`

Expected: FAIL because forms are absent.

- [ ] **Step 3: Implement virtualized symbol search, runtime estimate, independent timeframes, defaults, reset, import, and all strategy controls**

```ts
export const allocationSchema = z.object({
  trend: z.number().min(0).max(100),
  meanReversion: z.number().min(0).max(100),
  grid: z.number().min(0).max(100),
  cashReserve: z.number().min(0).max(100),
}).refine(value => Object.values(value).reduce((sum, item) => sum + item, 0) === 100,
  "策略比例與現金保留必須合計 100%"
);
```

- [ ] **Step 4: Run builder tests and API contract test**

Run: `docker compose run --rm web npm test -- BacktestBuilderPage.test.tsx`

Expected: PASS and submitted JSON validates against the backend request schema.

- [ ] **Step 5: Commit backtest builder**

```bash
git add frontend/src/backtests frontend/src/strategies
git commit -m "feat: add adjustable backtest builder"
```

### Task 3: Job Progress and Recoverable Error Presentation

**Files:**
- Create: `frontend/src/jobs/JobProgressPage.tsx`
- Create: `frontend/src/jobs/useJobPolling.ts`
- Create: `frontend/src/components/ApiErrorPanel.tsx`
- Test: `frontend/src/jobs/JobProgressPage.test.tsx`

**Interfaces:**
- Consumes: `GET /jobs/{id}` and `POST /jobs/{id}/cancel`
- Produces: stage, completed-symbol count, per-symbol errors, cancel action, and interrupted restart action

- [ ] **Step 1: Write failing progress and cancellation tests**

```tsx
it("shows stage progress and cancels without claiming completion", async () => {
  render(<JobProgressPage jobId="job-1" />);
  expect(await screen.findByText("驗證資料 12 / 40")) .toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "取消回測" }));
  expect(await screen.findByText("已取消；已完成的資料處理仍保留")) .toBeVisible();
});
```

- [ ] **Step 2: Verify progress tests fail**

Run: `docker compose run --rm web npm test -- JobProgressPage.test.tsx`

Expected: FAIL because progress components are absent.

- [ ] **Step 3: Implement bounded polling, stage labels, actionable errors, cancellation confirmation, and interrupted restart**

```ts
const intervalFor = (status: JobStatus) =>
  ["completed", "failed", "cancelled", "interrupted"].includes(status) ? false : 1500;
```

- [ ] **Step 4: Run job UI tests**

Run: `docker compose run --rm web npm test -- JobProgressPage.test.tsx`

Expected: PASS and polling stops for terminal states.

- [ ] **Step 5: Commit progress UI**

```bash
git add frontend/src/jobs frontend/src/components/ApiErrorPanel.tsx
git commit -m "feat: show backtest job progress"
```

### Task 4: Results Dashboard, Comparison, and Export

**Files:**
- Create: `frontend/src/dashboard/OverviewPage.tsx`
- Create: `frontend/src/results/BacktestResultPage.tsx`
- Create: `frontend/src/results/EquityChart.tsx`
- Create: `frontend/src/results/DrawdownChart.tsx`
- Create: `frontend/src/results/StrategyCards.tsx`
- Create: `frontend/src/results/TradeTable.tsx`
- Test: `frontend/src/results/BacktestResultPage.test.tsx`

**Interfaces:**
- Consumes: `/backtests/{id}`, `/backtests/{id}/equity`, `/backtests/{id}/trades`, and CSV export
- Produces: aggregate, strategy, symbol, and buy-and-hold views

- [ ] **Step 1: Write failing metric, attribution, and export tests**

```tsx
it("switches between aggregate and strategy attribution", async () => {
  render(<BacktestResultPage runId="run-1" />);
  expect(await screen.findByText("總報酬 +18.42%")) .toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "均值回歸" }));
  expect(screen.getByText("最大回撤 -7.90%")) .toBeVisible();
});
```

- [ ] **Step 2: Verify result tests fail**

Run: `docker compose run --rm web npm test -- BacktestResultPage.test.tsx`

Expected: FAIL because result views are absent.

- [ ] **Step 3: Implement KPI cards, chart adapters, benchmark overlay, attribution filters, paged trades, and CSV download**

```tsx
<EquityChart series={result.equity} benchmark={result.buyAndHoldEquity} />
<StrategyCards summaries={result.strategySummaries} />
<TradeTable runId={runId} strategy={selectedStrategy} symbol={selectedSymbol} />
```

- [ ] **Step 4: Run component and visual-flow tests**

Run: `docker compose run --rm web npm test -- BacktestResultPage.test.tsx`

Run: `docker compose run --rm e2e npx playwright test frontend/e2e/backtest-results.spec.ts`

Expected: PASS with desktop and mobile screenshots reviewed.

- [ ] **Step 5: Commit result dashboard**

```bash
git add frontend/src/dashboard frontend/src/results frontend/e2e/backtest-results.spec.ts
git commit -m "feat: visualize backtest performance"
```

### Task 5: Configuration, Data Management, and End-to-End Acceptance

**Files:**
- Create: `frontend/src/settings/StrategyConfigurationsPage.tsx`
- Create: `frontend/src/data/DataManagementPage.tsx`
- Create: `frontend/src/system/SystemSettingsPage.tsx`
- Create: `frontend/e2e/backtest-flow.spec.ts`
- Modify: `README.md`

**Interfaces:**
- Produces: named configuration clone/import/export/reset flows
- Produces: dataset status, refresh, and validation issue views
- Produces: full login-to-export acceptance flow

- [ ] **Step 1: Write the failing end-to-end acceptance flow**

```ts
test("administrator creates and inspects a three-strategy backtest", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "建立回測" }).click();
  await selectSymbols(page, ["BTCUSDT", "ETHUSDT"]);
  await page.getByRole("button", { name: "執行回測" }).click();
  await expect(page.getByText("已完成")).toBeVisible();
  await expect(page.getByText("趨勢跟隨")).toBeVisible();
  await expect(page.getByText("均值回歸")).toBeVisible();
  await expect(page.getByText("網格交易")).toBeVisible();
});
```

- [ ] **Step 2: Verify the acceptance test fails**

Run: `docker compose run --rm e2e npx playwright test frontend/e2e/backtest-flow.spec.ts`

Expected: FAIL because settings and complete navigation are unfinished.

- [ ] **Step 3: Implement configuration and data pages, destructive-action confirmation, and responsive navigation**

Use explicit buttons for clone, restore defaults, import, export, refresh dataset, and delete result. Require the administrator to type the result name before permanent deletion.

- [ ] **Step 4: Run frontend and end-to-end suites**

Run: `docker compose run --rm web npm test`

Run: `docker compose run --rm e2e npx playwright test`

Expected: PASS at desktop and mobile viewports with no accessibility violations in critical pages.

- [ ] **Step 5: Commit completed web dashboard**

```bash
git add frontend README.md compose.yaml
git commit -m "feat: complete backtest web dashboard"
```
