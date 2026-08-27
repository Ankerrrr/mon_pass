import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { PaperTradingPage } from "./PaperTradingPage";

it("keeps simulation warning visible and guards emergency stop", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } })));
  render(<PaperTradingPage />);
  expect(screen.getByText("模擬模式｜不會送出真實訂單")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "緊急停止全部模擬" }));
  expect(screen.getByRole("dialog", { name: "確認緊急停止" })).toBeVisible();
  expect(screen.getByRole("button", { name: "確認全部停止" })).toBeDisabled();
});
