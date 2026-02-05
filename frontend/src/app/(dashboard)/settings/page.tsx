"use client";

import { useAuthStore } from "@/lib/store/auth";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export default function SettingsPage() {
  const { user, businessName } = useAuthStore();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500">Manage your account and business settings</p>
      </div>

      {/* Profile section */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Your personal account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Name</p>
              <p className="font-medium">{user?.name || "-"}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Email</p>
              <p className="font-medium">{user?.email || "-"}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Role</p>
              <p className="font-medium capitalize">{user?.role || "-"}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Business section */}
      <Card>
        <CardHeader>
          <CardTitle>Business</CardTitle>
          <CardDescription>Your business information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Business Name</p>
              <p className="font-medium">{businessName || "-"}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Business ID</p>
              <p className="font-mono text-sm">{user?.business_id || "-"}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Placeholder for future settings */}
      <Card>
        <CardHeader>
          <CardTitle>Preferences</CardTitle>
          <CardDescription>Additional settings coming soon</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500 text-sm">
            Notification preferences, business hours, and other settings will be available here in a future update.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
