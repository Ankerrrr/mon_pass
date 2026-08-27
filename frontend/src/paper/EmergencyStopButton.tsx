import { useState } from "react";

import { emergencyStopPaper } from "../api/client";

export function EmergencyStopButton({ onStopped }: { onStopped: () => void }) {
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  async function stop() {
    setBusy(true);
    await emergencyStopPaper();
    setBusy(false);
    setOpen(false);
    onStopped();
  }
  return <>
    <button className="danger-action" onClick={() => setOpen(true)}>緊急停止全部模擬</button>
    {open && <div className="modal-backdrop"><section className="confirm-dialog" role="dialog" aria-label="確認緊急停止">
      <p className="eyebrow">EMERGENCY CONTROL</p><h2>停止所有模擬工作？</h2>
      <p>此操作不會送出交易，但會立即停止所有 active session。輸入 <code>STOP</code> 確認。</p>
      <label>確認文字<input autoFocus value={confirmation} onChange={(e) => setConfirmation(e.target.value)} /></label>
      <div><button onClick={() => setOpen(false)}>取消</button><button className="danger-action" disabled={confirmation !== "STOP" || busy} onClick={stop}>{busy ? "停止中…" : "確認全部停止"}</button></div>
    </section></div>}
  </>;
}
