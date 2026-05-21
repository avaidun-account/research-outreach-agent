import { Router, type IRouter } from "express";
import { spawn } from "node:child_process";
import path from "node:path";

const router: IRouter = Router();

const WORKSPACE_ROOT = process.env.WORKSPACE_ROOT ?? path.resolve(process.cwd());

let agentRunning = false;
let agentLogs: string[] = [];
let agentStartedAt: string | null = null;
let agentFinishedAt: string | null = null;

router.get("/agent/status", (_req, res) => {
  res.json({
    running: agentRunning,
    startedAt: agentStartedAt,
    finishedAt: agentFinishedAt,
    logs: agentLogs.slice(-50),
  });
});

router.post("/agent/run", (_req, res) => {
  if (agentRunning) {
    res.status(409).json({ error: "Agent is already running" });
    return;
  }

  agentRunning = true;
  agentLogs = [];
  agentStartedAt = new Date().toISOString();
  agentFinishedAt = null;

  const proc = spawn("python3", ["research_outreach_agent.py"], {
    cwd: WORKSPACE_ROOT,
    env: { ...process.env },
  });

  proc.stdout.on("data", (chunk: Buffer) => {
    const lines = chunk.toString().split("\n").filter(Boolean);
    agentLogs.push(...lines);
  });

  proc.stderr.on("data", (chunk: Buffer) => {
    const lines = chunk.toString().split("\n").filter(Boolean);
    agentLogs.push(...lines.map((l) => `[err] ${l}`));
  });

  proc.on("close", () => {
    agentRunning = false;
    agentFinishedAt = new Date().toISOString();
  });

  res.json({ message: "Agent started", startedAt: agentStartedAt });
});

export default router;
