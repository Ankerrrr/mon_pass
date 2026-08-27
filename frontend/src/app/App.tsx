import { useEffect, useState } from "react";
import { currentAdmin, type Admin } from "../api/client";
import { LoginPage } from "../auth/LoginPage";
import { AppShell } from "../layout/AppShell";

export function App() {
  const [admin, setAdmin] = useState<Admin | null | undefined>(undefined);
  useEffect(() => { currentAdmin().then(setAdmin).catch(() => setAdmin(null)); }, []);
  if (admin === undefined) return <main className="boot">QUANT HOME <span>INITIALIZING</span></main>;
  return admin ? <AppShell admin={admin} /> : <LoginPage onAuthenticated={setAdmin} />;
}
