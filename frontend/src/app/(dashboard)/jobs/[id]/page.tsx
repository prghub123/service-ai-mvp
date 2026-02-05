"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { jobsApi, techniciansApi, getErrorMessage } from "@/lib/api";
import { Job, Technician } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  Loader2,
  Phone,
  MapPin,
  Calendar,
  Clock,
  User,
  Wrench,
  AlertTriangle,
} from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [job, setJob] = useState<Job | null>(null);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  // Assign technician modal
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [selectedTechId, setSelectedTechId] = useState("");
  const [isAssigning, setIsAssigning] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [jobData, techData] = await Promise.all([
          jobsApi.getById(jobId),
          techniciansApi.getAll(true), // Active only
        ]);
        setJob(jobData);
        setTechnicians(techData);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [jobId]);

  const handleAssignTechnician = async () => {
    if (!selectedTechId) return;

    setIsAssigning(true);
    try {
      await jobsApi.assignTechnician(jobId, selectedTechId);
      toast.success("Technician assigned successfully");
      
      // Refresh job data
      const updatedJob = await jobsApi.getById(jobId);
      setJob(updatedJob);
      setAssignModalOpen(false);
      setSelectedTechId("");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setIsAssigning(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <div className="bg-red-50 text-red-600 p-4 rounded-lg">
          {error || "Job not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back button and header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-gray-900">
                {job.confirmation_code}
              </h1>
              <StatusBadge status={job.status} />
              {job.priority === "emergency" && (
                <Badge variant="destructive">
                  <AlertTriangle className="h-3 w-3 mr-1" />
                  Emergency
                </Badge>
              )}
            </div>
            <p className="text-gray-500">{job.service_type}</p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2">
          {!job.technician_id && (
            <Button onClick={() => setAssignModalOpen(true)}>
              <Wrench className="h-4 w-4 mr-2" />
              Assign Technician
            </Button>
          )}
        </div>
      </div>

      {/* Job details grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Customer info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center">
              <User className="h-4 w-4 mr-2" />
              Customer
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-sm text-gray-500">Name</p>
              <p className="font-medium">{job.customer_name || "Unknown"}</p>
            </div>
            {job.customer_phone && (
              <div>
                <p className="text-sm text-gray-500">Phone</p>
                <a
                  href={`tel:${job.customer_phone}`}
                  className="font-medium text-blue-600 hover:underline flex items-center"
                >
                  <Phone className="h-4 w-4 mr-1" />
                  {job.customer_phone}
                </a>
              </div>
            )}
            {job.address && (
              <div>
                <p className="text-sm text-gray-500">Address</p>
                <p className="font-medium flex items-start">
                  <MapPin className="h-4 w-4 mr-1 mt-0.5 flex-shrink-0" />
                  {job.address}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Schedule info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center">
              <Calendar className="h-4 w-4 mr-2" />
              Schedule
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <p className="text-sm text-gray-500">Date</p>
              <p className="font-medium">
                {job.scheduled_date
                  ? format(new Date(job.scheduled_date), "EEEE, MMMM d, yyyy")
                  : "Not scheduled"}
              </p>
            </div>
            {job.scheduled_time_start && (
              <div>
                <p className="text-sm text-gray-500">Time</p>
                <p className="font-medium flex items-center">
                  <Clock className="h-4 w-4 mr-1" />
                  {job.scheduled_time_start}
                  {job.scheduled_time_end && ` - ${job.scheduled_time_end}`}
                </p>
              </div>
            )}
            <div>
              <p className="text-sm text-gray-500">Assigned Technician</p>
              {job.technician_name ? (
                <p className="font-medium flex items-center">
                  <Wrench className="h-4 w-4 mr-1" />
                  {job.technician_name}
                </p>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="text-yellow-600">Unassigned</span>
                  <Button
                    variant="link"
                    size="sm"
                    className="p-0 h-auto"
                    onClick={() => setAssignModalOpen(true)}
                  >
                    Assign now
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Job description */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-gray-700 whitespace-pre-wrap">
              {job.description || "No description provided"}
            </p>
          </CardContent>
        </Card>

        {/* Job timeline / metadata */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Details</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <dt className="text-sm text-gray-500">Priority</dt>
                <dd className="font-medium capitalize">{job.priority}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Status</dt>
                <dd className="font-medium capitalize">{job.status.replace("_", " ")}</dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Created</dt>
                <dd className="font-medium">
                  {format(new Date(job.created_at), "MMM d, yyyy h:mm a")}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Service Type</dt>
                <dd className="font-medium capitalize">{job.service_type}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Assign technician modal */}
      <Dialog open={assignModalOpen} onOpenChange={setAssignModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign Technician</DialogTitle>
            <DialogDescription>
              Select a technician to assign to this job.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <Select value={selectedTechId} onValueChange={setSelectedTechId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a technician" />
              </SelectTrigger>
              <SelectContent>
                {technicians.map((tech) => (
                  <SelectItem key={tech.id} value={tech.id}>
                    <div className="flex items-center justify-between w-full">
                      <span>{tech.name}</span>
                      <span className="text-sm text-gray-500 ml-2">
                        ({tech.current_job_count} jobs)
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {technicians.length === 0 && (
              <p className="text-sm text-gray-500 mt-2">
                No active technicians available.{" "}
                <Link href="/technicians" className="text-blue-600 hover:underline">
                  Add a technician
                </Link>
              </p>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAssignModalOpen(false)}
              disabled={isAssigning}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAssignTechnician}
              disabled={!selectedTechId || isAssigning}
            >
              {isAssigning ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Assigning...
                </>
              ) : (
                "Assign"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
