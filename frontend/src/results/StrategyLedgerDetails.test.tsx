import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";

import { StrategyLedgerDetails } from "./StrategyLedgerDetails";

it("shows strategy profit and each operation's asset change", async () => {
  render(<StrategyLedgerDetails strategy="trend" ledger={{
    initial_cash: "1000", cash: "917", fills: [],
    summary: {
      initial_cash: "1000", ending_cash: "917", position_value: "130",
      ending_equity: "1047", total_pnl: "47", total_return: "0.047",
      realized_pnl: "18", unrealized_pnl: "29", fees: "3", fill_count: 2,
      valuation_is_estimated: false,
    },
    operations: [{
      filled_at: "2026-01-02T00:00:00Z", symbol: "BTCUSDT", side: "sell",
      quantity: "1", price: "120", notional: "120", fee: "1", cash_delta: "119",
      realized_pnl: "18", cash_after: "917", position_quantity_after: "1",
      equity_after: "1037", equity_change: "39", reason: "exit", mode: "backtest",
    }],
  }} />);

  expect(screen.getByText("+47.00 USDT")).toBeVisible();
  await userEvent.click(screen.getByText("趨勢策略"));
  expect(screen.getByText("+39.00 USDT")).toBeVisible();
  expect(screen.getByText("+119.00 USDT")).toBeVisible();
  expect(screen.getByText("已實現 +18.00")).toBeVisible();
});
