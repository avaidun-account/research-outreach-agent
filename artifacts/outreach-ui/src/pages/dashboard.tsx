import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Loader2, Play, ExternalLink, Mail } from "lucide-react";
import {
  useLeads,
  useStats,
  useAgentStatus,
  useUpdateLeadStatus,
  useRunAgent,
  type Lead,
} from "@/hooks/useLeads";

const STATUS_COLORS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  drafted: "outline",
  sent: "default",
  archived: "secondary",
};

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

function EmailPanel({ lead, onClose }: { lead: Lead; onClose: () => void }) {
  const update = useUpdateLeadStatus();

  function changeStatus(status: string) {
    update.mutate({ id: lead.id, status });
  }

  return (
    <Sheet open onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
        <SheetHeader className="mb-4">
          <SheetTitle className="text-base">{lead.name}</SheetTitle>
          <p className="text-sm text-muted-foreground">{lead.title} · {lead.institution}</p>
        </SheetHeader>

        <div className="space-y-4">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={STATUS_COLORS[lead.status] ?? "outline"}>{lead.status}</Badge>
            <Select value={lead.status} onValueChange={changeStatus}>
              <SelectTrigger className="h-7 text-xs w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="drafted">drafted</SelectItem>
                <SelectItem value="sent">sent</SelectItem>
                <SelectItem value="archived">archived</SelectItem>
              </SelectContent>
            </Select>
            {lead.profile_url && lead.profile_url !== "Unknown" && (
              <a
                href={lead.profile_url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto text-xs flex items-center gap-1 text-muted-foreground hover:text-foreground"
              >
                Profile <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>

          {lead.email && lead.email !== "Unknown" && (
            <div className="flex items-center gap-2 text-sm">
              <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="font-mono text-xs break-all">{lead.email}</span>
            </div>
          )}

          <div className="rounded-md border p-3 bg-muted/30">
            <p className="text-xs font-semibold text-muted-foreground mb-1">SUBJECT</p>
            <p className="text-sm font-medium">{lead.subject}</p>
          </div>

          <div className="rounded-md border p-3 bg-muted/30">
            <p className="text-xs font-semibold text-muted-foreground mb-2">EMAIL BODY</p>
            <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed">{lead.email_body}</pre>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default function Dashboard() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [institutionFilter, setInstitutionFilter] = useState("all");
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const { data: stats } = useStats();
  const { data: agentData } = useAgentStatus();
  const runAgent = useRunAgent();

  const { data: leadsData, isLoading } = useLeads({
    status: statusFilter !== "all" ? statusFilter : undefined,
    institution: institutionFilter !== "all" ? institutionFilter : undefined,
    search: search.trim() || undefined,
  });

  const leads = leadsData?.leads ?? [];
  const institutions = stats?.byInstitution.map((r) => r.institution) ?? [];
  const isRunning = agentData?.running ?? false;

  function handleRun() {
    runAgent.mutate();
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Research Outreach</h1>
            <p className="text-sm text-muted-foreground">Arjun Vaidun · UC Riverside</p>
          </div>
          <Button
            onClick={handleRun}
            disabled={isRunning || runAgent.isPending}
            className="gap-2"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Agent running…
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Run Agent
              </>
            )}
          </Button>
        </div>

        {isRunning && agentData?.logs && agentData.logs.length > 0 && (
          <div className="rounded-md border bg-muted/40 p-3 text-xs font-mono text-muted-foreground max-h-32 overflow-y-auto">
            {agentData.logs.slice(-10).map((line, i) => (
              <div key={i}>{line}</div>
            ))}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Total" value={stats?.total ?? 0} />
          <StatCard label="Drafted" value={stats?.byStatus.drafted ?? 0} />
          <StatCard label="Sent" value={stats?.byStatus.sent ?? 0} />
          <StatCard label="Archived" value={stats?.byStatus.archived ?? 0} />
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3">
          <Input
            placeholder="Search name, research focus, email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="sm:max-w-xs"
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="sm:w-40">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="drafted">Drafted</SelectItem>
              <SelectItem value="sent">Sent</SelectItem>
              <SelectItem value="archived">Archived</SelectItem>
            </SelectContent>
          </Select>
          <Select value={institutionFilter} onValueChange={setInstitutionFilter}>
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All institutions" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All institutions</SelectItem>
              {institutions.map((inst) => (
                <SelectItem key={inst} value={inst}>{inst}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <Card>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex items-center justify-center h-40">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : leads.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-muted-foreground">
                <p className="text-sm">No leads yet.</p>
                <p className="text-xs mt-1">Run the agent to scrape faculty directories and draft emails.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden md:table-cell">Institution</TableHead>
                    <TableHead className="hidden lg:table-cell">Research Focus</TableHead>
                    <TableHead className="hidden sm:table-cell">Email</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden md:table-cell">Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leads.map((lead) => (
                    <TableRow
                      key={lead.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => setSelectedLead(lead)}
                    >
                      <TableCell>
                        <div className="font-medium text-sm">{lead.name}</div>
                        <div className="text-xs text-muted-foreground md:hidden">{lead.institution}</div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm">{lead.institution}</TableCell>
                      <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                        {lead.research_focus}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-xs font-mono text-muted-foreground">
                        {lead.email !== "Unknown" ? lead.email : "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={STATUS_COLORS[lead.status] ?? "outline"} className="text-xs">
                          {lead.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-xs text-muted-foreground">
                        {lead.created_at ? new Date(lead.created_at).toLocaleDateString() : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <p className="text-xs text-muted-foreground text-center">
          {leadsData?.total ?? 0} total leads · Click a row to preview & manage the email
        </p>
      </div>

      {selectedLead && (
        <EmailPanel lead={selectedLead} onClose={() => setSelectedLead(null)} />
      )}
    </div>
  );
}
