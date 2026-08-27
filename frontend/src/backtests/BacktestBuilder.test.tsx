import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { BacktestBuilder } from "./BacktestBuilder";

it("creates a validated configuration and submits its backtest", async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({
      id: "config-1", name: "BTC baseline", version: 1, payload: {},
    }), { status: 201, headers: { "Content-Type": "application/json" } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ job_id: "job-1" }), {
      status: 202, headers: { "Content-Type": "application/json" },
    }));
  vi.stubGlobal("fetch", fetchMock);
  render(<BacktestBuilder />);

  await userEvent.clear(screen.getByLabelText("設定名稱"));
  await userEvent.type(screen.getByLabelText("設定名稱"), "BTC baseline");
  await userEvent.click(screen.getByRole("button", { name: "儲存並執行回測" }));

  expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/configurations", expect.objectContaining({ method: "POST" }));
  expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/backtests", expect.objectContaining({ method: "POST" }));
  expect(await screen.findByRole("status")).toHaveTextContent("回測工作已送出");
});
