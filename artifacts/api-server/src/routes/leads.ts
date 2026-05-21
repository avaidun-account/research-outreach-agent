import { Router, type IRouter } from "express";
import { getDb, type Lead } from "../lib/sqlite";

const router: IRouter = Router();

router.get("/leads", (req, res) => {
  const db = getDb();
  const { status, institution, search } = req.query as Record<string, string>;

  let query = "SELECT * FROM leads WHERE 1=1";
  const params: unknown[] = [];

  if (status) {
    query += " AND status = ?";
    params.push(status);
  }
  if (institution) {
    query += " AND institution = ?";
    params.push(institution);
  }
  if (search) {
    query += " AND (name LIKE ? OR research_focus LIKE ? OR email LIKE ?)";
    const like = `%${search}%`;
    params.push(like, like, like);
  }

  query += " ORDER BY created_at DESC";

  const leads = db.prepare(query).all(...params) as Lead[];
  const total = (db.prepare("SELECT COUNT(*) as n FROM leads").get() as { n: number }).n;

  res.json({ leads, total });
});

router.get("/leads/:id", (req, res) => {
  const db = getDb();
  const lead = db.prepare("SELECT * FROM leads WHERE id = ?").get(req.params.id) as Lead | undefined;
  if (!lead) {
    res.status(404).json({ error: "Not found" });
    return;
  }
  res.json(lead);
});

router.patch("/leads/:id", (req, res) => {
  const db = getDb();
  const { status } = req.body as { status?: string };

  const allowed = ["drafted", "sent", "archived"];
  if (!status || !allowed.includes(status)) {
    res.status(400).json({ error: "Invalid status" });
    return;
  }

  db.prepare("UPDATE leads SET status = ? WHERE id = ?").run(status, req.params.id);
  const lead = db.prepare("SELECT * FROM leads WHERE id = ?").get(req.params.id) as Lead | undefined;
  if (!lead) {
    res.status(404).json({ error: "Not found" });
    return;
  }
  res.json(lead);
});

export default router;
