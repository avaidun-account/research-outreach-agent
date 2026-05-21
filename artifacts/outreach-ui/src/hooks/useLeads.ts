import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const API = "/api";

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

export interface Stats {
  total: number;
  byStatus: { drafted: number; sent: number; archived: number };
  byInstitution: { institution: string; n: number }[];
}

export interface AgentStatus {
  running: boolean;
  startedAt: string | null;
  finishedAt: string | null;
  logs: string[];
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function useLeads(params: { status?: string; institution?: string; search?: string }) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.institution) qs.set("institution", params.institution);
  if (params.search) qs.set("search", params.search);
  const query = qs.toString() ? `?${qs.toString()}` : "";

  return useQuery({
    queryKey: ["leads", params],
    queryFn: () => apiFetch<{ leads: Lead[]; total: number }>(`/leads${query}`),
    refetchInterval: 10_000,
  });
}

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => apiFetch<Stats>("/stats"),
    refetchInterval: 10_000,
  });
}

export function useAgentStatus() {
  return useQuery({
    queryKey: ["agent-status"],
    queryFn: () => apiFetch<AgentStatus>("/agent/status"),
    refetchInterval: 5_000,
  });
}

export function useUpdateLeadStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      apiFetch<Lead>(`/leads/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["leads"] });
      void qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useRunAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ message: string; startedAt: string }>("/agent/run", { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["agent-status"] });
    },
  });
}
