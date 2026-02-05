"use client";

import { useEffect, useState } from "react";
import { techniciansApi, getErrorMessage } from "@/lib/api";
import { Technician, TechnicianCreate } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import { Loader2, Plus, Phone, Mail } from "lucide-react";
import { toast } from "sonner";

export default function TechniciansPage() {
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  // Add technician modal
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [newTech, setNewTech] = useState<TechnicianCreate>({
    name: "",
    email: "",
    phone: "",
    password: "",
  });

  const fetchTechnicians = async () => {
    setIsLoading(true);
    try {
      const data = await techniciansApi.getAll();
      setTechnicians(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTechnicians();
  }, []);

  const handleAddTechnician = async () => {
    if (!newTech.name || !newTech.email || !newTech.phone || !newTech.password) {
      toast.error("Please fill in all fields");
      return;
    }

    setIsAdding(true);
    try {
      await techniciansApi.create(newTech);
      toast.success("Technician added successfully");
      setAddModalOpen(false);
      setNewTech({ name: "", email: "", phone: "", password: "" });
      fetchTechnicians();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setIsAdding(false);
    }
  };

  const handleToggleActive = async (tech: Technician) => {
    try {
      await techniciansApi.update(tech.id, { is_active: !tech.is_active });
      toast.success(`Technician ${tech.is_active ? "deactivated" : "activated"}`);
      fetchTechnicians();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleToggleOnCall = async (tech: Technician) => {
    try {
      await techniciansApi.update(tech.id, { is_on_call: !tech.is_on_call });
      toast.success(`On-call status updated`);
      fetchTechnicians();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Technicians</h1>
          <p className="text-gray-500">Manage your technician team</p>
        </div>
        <Button onClick={() => setAddModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Technician
        </Button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm text-gray-500">Total Technicians</div>
            <div className="text-2xl font-bold">{technicians.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm text-gray-500">Active</div>
            <div className="text-2xl font-bold text-green-600">
              {technicians.filter((t) => t.is_active).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm text-gray-500">On Call</div>
            <div className="text-2xl font-bold text-blue-600">
              {technicians.filter((t) => t.is_on_call).length}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Technicians table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-gray-500" />
            </div>
          ) : error ? (
            <div className="p-4 text-center text-red-600">{error}</div>
          ) : technicians.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <p>No technicians yet</p>
              <Button
                variant="link"
                onClick={() => setAddModalOpen(true)}
                className="mt-2"
              >
                Add your first technician
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Contact</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Current Jobs</TableHead>
                    <TableHead>On Call</TableHead>
                    <TableHead>Active</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {technicians.map((tech) => (
                    <TableRow key={tech.id}>
                      <TableCell>
                        <div className="font-medium">{tech.name}</div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <a
                            href={`tel:${tech.phone}`}
                            className="text-sm flex items-center hover:text-blue-600"
                          >
                            <Phone className="h-3 w-3 mr-1" />
                            {tech.phone}
                          </a>
                          {tech.email && (
                            <a
                              href={`mailto:${tech.email}`}
                              className="text-sm text-gray-500 flex items-center hover:text-blue-600"
                            >
                              <Mail className="h-3 w-3 mr-1" />
                              {tech.email}
                            </a>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={tech.is_active ? "default" : "secondary"}
                        >
                          {tech.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <span className="font-medium">{tech.current_job_count}</span>
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={tech.is_on_call}
                          onCheckedChange={() => handleToggleOnCall(tech)}
                          disabled={!tech.is_active}
                        />
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={tech.is_active}
                          onCheckedChange={() => handleToggleActive(tech)}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add technician modal */}
      <Dialog open={addModalOpen} onOpenChange={setAddModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Technician</DialogTitle>
            <DialogDescription>
              Add a new technician to your team. They will receive an email to set up their mobile app.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="John Smith"
                value={newTech.name}
                onChange={(e) => setNewTech({ ...newTech, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="john@example.com"
                value={newTech.email}
                onChange={(e) => setNewTech({ ...newTech, email: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                placeholder="(555) 123-4567"
                value={newTech.phone}
                onChange={(e) => setNewTech({ ...newTech, phone: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Initial Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={newTech.password}
                onChange={(e) => setNewTech({ ...newTech, password: e.target.value })}
              />
              <p className="text-xs text-gray-500">
                The technician can change this later in the mobile app
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAddModalOpen(false)}
              disabled={isAdding}
            >
              Cancel
            </Button>
            <Button onClick={handleAddTechnician} disabled={isAdding}>
              {isAdding ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                "Add Technician"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
