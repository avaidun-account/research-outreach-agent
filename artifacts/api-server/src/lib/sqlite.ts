import Database from "better-sqlite3";
import path from "node:path";

const DB_PATH = process.env.DB_FILE ?? path.resolve(process.cwd(), "outreach.db");

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { readonly: false });
    _db.pragma("journal_mode = WAL");
  }
  return _db;
}

export interface Lead {
  id: number;
  name: string;
  title: string;
  institution: string;
  email: string;
  profile_url: string;
  research_focus: string;
  subject: string;
  email_body: string;
  status: string;
  created_at: string;
}
