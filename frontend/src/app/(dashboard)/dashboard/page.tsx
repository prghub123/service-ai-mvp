"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { dashboardApi, jobsApi, getErrorMessage } from "@/lib/api";
import { DashboardStats, Job } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ClipboardList,
  Clock,
  CheckCircle,
  AlertTriangle,
  Users,
  Wrench,
  ArrowRight,
  Loader2,
} from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, jobsData] = await Promise.all([
          dashboardApi.getStats(),
          jobsApi.getAll({ page_size: 5 }),
        ]);
        setStats(statsData);
        setRecentJobs(jobsData);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-600 p-4 rounded-lg">
        <p>Error loading dashboard: {error}</p>
        <Button
          variant="outline"
          className="mt-2"
          onClick={() => window.location.reload()}
        >
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500">Welcome back! Here&apos;s what&apos;s happening today.</p>
      </div>

      {/* Emergency alert */}
      {stats && stats.emergency_jobs > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center">
            <AlertTriangle className="h-5 w-5 text-red-600 mr-3" />
            <div>
              <p className="font-medium text-red-800">
                {stats.emergency_jobs} Emergency Job{stats.emergency_jobs > 1 ? "s" : ""} Pending
              </p>
              <p className="text-sm text-red-600">Requires immediate attention</p>
            </div>
          </div>
          <Link href="/jobs?priority=emergency">
            <Button variant="destructive" size="sm">
              View Jobs
            </Button>
          </Link>
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Jobs Today"
          value={stats?.total_jobs_today || 0}
          icon={ClipboardList}
          iconColor="text-blue-600"
          iconBg="bg-blue-100"
        />
        <StatsCard
          title="Pending Jobs"
          value={stats?.pending_jobs || 0}
          icon={Clock}
          iconColor="text-yellow-600"
          iconBg="bg-yellow-100"
          href="/jobs?status=pending"
        />
        <StatsCard
          title="Completed Today"
          value={stats?.completed_today || 0}
          icon={CheckCircle}
          iconColor="text-green-600"
          iconBg="bg-green-100"
        />
        <StatsCard
          title="Active Technicians"
          value={`${stats?.active_technicians || 0}/${stats?.total_technicians || 0}`}
          icon={Wrench}
          iconColor="text-purple-600"
          iconBg="bg-purple-100"
          href="/technicians"
        />
      </div>

      {/* Recent jobs and quick actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent jobs */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Recent Jobs</CardTitle>
            <Link href="/jobs">
              <Button variant="ghost" size="sm">
                View all
                <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {recentJobs.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No jobs yet</p>
            ) : (
              <div className="space-y-4">
                {recentJobs.map((job) => (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className="block p-3 rounded-lg border hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            {job.confirmation_code}
                          </span>
                          <StatusBadge status={job.status} />
                          {job.priority === "emergency" && (
                            <Badge variant="destructive">Emergency</Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 mt-1">
                          {job.service_type} • {job.customer_name || "Unknown"}
                        </p>
                      </div>
                      <div className="text-right text-sm text-gray-500">
                        {job.scheduled_date || "Unscheduled"}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link href="/jobs?status=pending" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Clock className="mr-2 h-4 w-4" />
                View Pending Jobs ({stats?.pending_jobs || 0})
              </Button>
            </Link>
            <Link href="/technicians" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Wrench className="mr-2 h-4 w-4" />
                Manage Technicians
              </Button>
            </Link>
            <Link href="/customers" className="block">
              <Button variant="outline" className="w-full justify-start">
                <Users className="mr-2 h-4 w-4" />
                View Customers ({stats?.total_customers || 0})
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Stats card component
interface StatsCardProps {
  title: string;
  value: number | string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  href?: string;
}

function StatsCard({ title, value, icon: Icon, iconColor, iconBg, href }: StatsCardProps) {
  const content = (
    <Card className={href ? "hover:bg-gray-50 transition-colors cursor-pointer" : ""}>
      <CardContent className="p-6">
        <div className="flex items-center">
          <div className={`p-3 rounded-lg ${iconBg}`}>
            <Icon className={`h-6 w-6 ${iconColor}`} />
          </div>
          <div className="ml-4">
            <p className="text-sm font-medium text-gray-500">{title}</p>
            <p className="text-2xl font-semibold text-gray-900">{value}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }

  return content;
}

// Status badge component
function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string }> = {
    pending: { variant: "secondary", label: "Pending" },
    scheduled: { variant: "default", label: "Scheduled" },
    dispatched: { variant: "default", label: "Dispatched" },
    en_route: { variant: "default", label: "En Route" },
    in_progress: { variant: "default", label: "In Progress" },
    completed: { variant: "outline", label: "Completed" },
    cancelled: { variant: "destructive", label: "Cancelled" },
    awaiting_parts: { variant: "secondary", label: "Awaiting Parts" },
  };

  const { variant, label } = variants[status] || { variant: "secondary" as const, label: status };

  return <Badge variant={variant}>{label}</Badge>;
}
