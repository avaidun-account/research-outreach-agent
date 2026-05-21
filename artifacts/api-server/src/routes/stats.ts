import { Router, type IRouter } from "express";
import { getDb } from "../lib/sqlite";

const router: IRouter = Router();

router.get("/stats", (_req, res) => {
  const db = getDb();

  const total = (db.prepare("SELECT COUNT(*) as n FROM leads").get() as { n: number }).n;

  const byStatus = db
    .prepare("SELECT status, COUNT(*) as n FROM leads GROUP BY status")
    .all() as { status: string; n: number }[];

  const byInstitution = db
    .prepare("SELECT institution, COUNT(*) as n FROM leads GROUP BY institution ORDER BY n DESC")
    .all() as { institution: string; n: number }[];

  const statusMap: Record<string, number> = { drafted: 0, sent: 0, archived: 0 };
  for (const row of byStatus) {
    statusMap[row.status] = row.n;
  }

  res.json({ total, byStatus: statusMap, byInstitution });
});

export default router;
