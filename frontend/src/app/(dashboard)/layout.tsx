"use client";

import { useState } from "react";
import { AuthGuard } from "@/components/auth-guard";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { MobileNav } from "@/components/layout/mobile-nav";
import { Toaster } from "@/components/ui/sonner";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50">
        {/* Desktop Sidebar */}
        <Sidebar />

        {/* Mobile Navigation */}
        <MobileNav open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

        {/* Main content area */}
        <div className="md:pl-64 flex flex-col flex-1">
          <Header onMenuClick={() => setMobileNavOpen(true)} />

          <main className="flex-1">
            <div className="py-6 px-4 sm:px-6 lg:px-8">{children}</div>
          </main>
        </div>

        {/* Toast notifications */}
        <Toaster position="top-right" />
      </div>
    </AuthGuard>
  );
}
