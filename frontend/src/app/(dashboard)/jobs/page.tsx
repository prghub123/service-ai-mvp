"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { jobsApi, techniciansApi, getErrorMessage } from "@/lib/api";
import { Job, JobStatus, JobPriority, Technician } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2, Search, Filter, X, Phone } from "lucide-react";
import { format } from "date-fns";

const STATUS_OPTIONS: { value: JobStatus | "all"; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "scheduled", label: "Scheduled" },
  { value: "dispatched", label: "Dispatched" },
  { value: "en_route", label: "En Route" },
  { value: "in_progress", label: "In Progress" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
];

const PRIORITY_OPTIONS: { value: JobPriority | "all"; label: string }[] = [
  { value: "all", label: "All Priorities" },
  { value: "emergency", label: "Emergency" },
  { value: "urgent", label: "Urgent" },
  { value: "normal", label: "Normal" },
  { value: "low", label: "Low" },
];

export default function JobsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [jobs, setJobs] = useState<Job[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters from URL params
  const [statusFilter, setStatusFilter] = useState<JobStatus | "all">(
    (searchParams.get("status") as JobStatus) || "all"
  );
  const [priorityFilter, setPriorityFilter] = useState<JobPriority | "all">(
    (searchParams.get("priority") as JobPriority) || "all"
  );
  const [techFilter, setTechFilter] = useState(
    searchParams.get("technician_id") || "all"
  );

  const fetchJobs = useCallback(async () => {
    setIsLoading(true);
    try {
      const filters: Record<string, string> = {};
      if (statusFilter !== "all") filters.status = statusFilter;
      if (priorityFilter !== "all") filters.priority = priorityFilter;
      if (techFilter !== "all") filters.technician_id = techFilter;

      const data = await jobsApi.getAll(filters as any);
      setJobs(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, priorityFilter, techFilter]);

  useEffect(() => {
    const fetchTechnicians = async () => {
      try {
        const data = await techniciansApi.getAll();
        setTechnicians(data);
      } catch {
        // Ignore error, technician filter just won't work
      }
    };
    fetchTechnicians();
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Update URL when filters change
  useEffect(() => {
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (priorityFilter !== "all") params.set("priority", priorityFilter);
    if (techFilter !== "all") params.set("technician_id", techFilter);

    const newUrl = params.toString() ? `?${params.toString()}` : "/jobs";
    router.replace(newUrl, { scroll: false });
  }, [statusFilter, priorityFilter, techFilter, router]);

  const clearFilters = () => {
    setStatusFilter("all");
    setPriorityFilter("all");
    setTechFilter("all");
  };

  const hasActiveFilters =
    statusFilter !== "all" || priorityFilter !== "all" || techFilter !== "all";

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
          <p className="text-gray-500">Manage and track all service jobs</p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-medium flex items-center">
              <Filter className="h-4 w-4 mr-2" />
              Filters
            </CardTitle>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="h-4 w-4 mr-1" />
                Clear
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Select
              value={statusFilter}
              onValueChange={(v) => setStatusFilter(v as JobStatus | "all")}
            >
              <SelectTrigger>
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={priorityFilter}
              onValueChange={(v) => setPriorityFilter(v as JobPriority | "all")}
            >
              <SelectTrigger>
                <SelectValue placeholder="Filter by priority" />
              </SelectTrigger>
              <SelectContent>
                {PRIORITY_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={techFilter} onValueChange={setTechFilter}>
              <SelectTrigger>
                <SelectValue placeholder="Filter by technician" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Technicians</SelectItem>
                {technicians.map((tech) => (
                  <SelectItem key={tech.id} value={tech.id}>
                    {tech.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Jobs table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-600">{error}</div>
          ) : jobs.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <p>No jobs found</p>
              {hasActiveFilters && (
                <Button variant="link" onClick={clearFilters}>
                  Clear filters
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job</TableHead>
                    <TableHead>Customer</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Technician</TableHead>
                    <TableHead>Scheduled</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell>
                        <div>
                          <Link
                            href={`/jobs/${job.id}`}
                            className="font-medium text-blue-600 hover:underline"
                          >
                            {job.confirmation_code}
                          </Link>
                          <p className="text-sm text-gray-500">{job.service_type}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{job.customer_name || "Unknown"}</p>
                          {job.customer_phone && (
                            <a
                              href={`tel:${job.customer_phone}`}
                              className="text-sm text-gray-500 flex items-center hover:text-blue-600"
                            >
                              <Phone className="h-3 w-3 mr-1" />
                              {job.customer_phone}
                            </a>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <StatusBadge status={job.status} />
                          {job.priority === "emergency" && (
                            <Badge variant="destructive" className="w-fit">
                              Emergency
                            </Badge>
                          )}
                          {job.priority === "urgent" && (
                            <Badge variant="secondary" className="w-fit">
                              Urgent
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {job.technician_name || (
                          <span className="text-yellow-600 text-sm">Unassigned</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {job.scheduled_date ? (
                          <div>
                            <p>{format(new Date(job.scheduled_date), "MMM d, yyyy")}</p>
                            {job.scheduled_time_start && (
                              <p className="text-sm text-gray-500">
                                {job.scheduled_time_start}
                              </p>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400">Not scheduled</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Link href={`/jobs/${job.id}`}>
                          <Button variant="outline" size="sm">
                            View
                          </Button>
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const variants: Record<
    string,
    { variant: "default" | "secondary" | "destructive" | "outline"; label: string }
  > = {
    pending: { variant: "secondary", label: "Pending" },
    scheduled: { variant: "default", label: "Scheduled" },
    dispatched: { variant: "default", label: "Dispatched" },
    en_route: { variant: "default", label: "En Route" },
    in_progress: { variant: "default", label: "In Progress" },
    completed: { variant: "outline", label: "Completed" },
    cancelled: { variant: "destructive", label: "Cancelled" },
    awaiting_parts: { variant: "secondary", label: "Awaiting Parts" },
  };

  const { variant, label } = variants[status] || {
    variant: "secondary" as const,
    label: status,
  };

  return <Badge variant={variant}>{label}</Badge>;
}
