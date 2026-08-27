import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

afterEach(() => vi.restoreAllMocks());

it("submits credentials and enters the dashboard", async () => {
  const onAuthenticated = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ user: { username: "admin" }, csrf_token: "csrf-value" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );
  render(<LoginPage onAuthenticated={onAuthenticated} />);

  await userEvent.type(screen.getByLabelText("管理員帳號"), "admin");
  await userEvent.type(screen.getByLabelText("密碼"), "secret-value");
  await userEvent.click(screen.getByRole("button", { name: "登入工作台" }));

  expect(fetch).toHaveBeenCalledWith(
    "/api/auth/login",
    expect.objectContaining({ method: "POST", credentials: "same-origin" }),
  );
  expect(onAuthenticated).toHaveBeenCalledWith({ username: "admin" });
});

it("shows the server error without leaving the login page", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid username or password" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  render(<LoginPage onAuthenticated={() => undefined} />);

  await userEvent.type(screen.getByLabelText("管理員帳號"), "admin");
  await userEvent.type(screen.getByLabelText("密碼"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "登入工作台" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("帳號或密碼錯誤");
});
