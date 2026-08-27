import { useEffect, useState } from "react";

import { cancelJob, getJob, type Job } from "../api/client";

const terminal = new Set(["completed", "failed", "cancelled", "interrupted"]);
const labels: Record<string, string> = { queued: "排隊中", downloading: "下載行情", validating: "驗證資料", running: "執行策略", aggregating: "彙整結果", completed: "已完成", failed: "失敗", cancelled: "已取消", interrupted: "服務中斷" };

export function JobProgress({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  useEffect(() => {
    let timer = 0;
    const poll = async () => {
      const next = await getJob(jobId); setJob(next);
      if (!terminal.has(next.status)) timer = window.setTimeout(poll, 1500);
    };
    void poll();
    return () => window.clearTimeout(timer);
  }, [jobId]);
  return <div className="job-progress" role="status">
    <div><strong>{labels[job?.status ?? "queued"] ?? job?.status}</strong><span>{Math.round((job?.progress ?? 0) * 100)}%</span></div>
    <progress value={job?.progress ?? 0} max={1} />
    {job?.error && <p className="form-error">{job.error}</p>}
    {job && !terminal.has(job.status) && <button className="text-button" onClick={async () => { await cancelJob(jobId); setJob(await getJob(jobId)); }}>取消回測</button>}
  </div>;
}
