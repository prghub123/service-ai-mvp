"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  ClipboardList,
  Users,
  UserCircle,
  Settings,
  Wrench,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Jobs", href: "/jobs", icon: ClipboardList },
  { name: "Technicians", href: "/technicians", icon: Wrench },
  { name: "Customers", href: "/customers", icon: Users },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0">
      <div className="flex flex-col flex-grow bg-gray-900 pt-5 overflow-y-auto">
        {/* Logo */}
        <div className="flex items-center flex-shrink-0 px-4">
          <span className="text-white text-xl font-bold">ServiceAI</span>
        </div>

        {/* Navigation */}
        <div className="mt-8 flex-1 flex flex-col">
          <nav className="flex-1 px-2 space-y-1">
            {navigation.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/dashboard" && pathname.startsWith(item.href));

              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    isActive
                      ? "bg-gray-800 text-white"
                      : "text-gray-300 hover:bg-gray-700 hover:text-white",
                    "group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors"
                  )}
                >
                  <item.icon
                    className={cn(
                      isActive
                        ? "text-white"
                        : "text-gray-400 group-hover:text-white",
                      "mr-3 h-5 w-5 flex-shrink-0"
                    )}
                    aria-hidden="true"
                  />
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* User section at bottom */}
        <div className="flex-shrink-0 flex border-t border-gray-800 p-4">
          <Link href="/settings" className="flex-shrink-0 w-full group block">
            <div className="flex items-center">
              <div className="h-9 w-9 rounded-full bg-gray-700 flex items-center justify-center">
                <UserCircle className="h-6 w-6 text-gray-300" />
              </div>
              <div className="ml-3">
                <p className="text-sm font-medium text-white">Account</p>
                <p className="text-xs text-gray-400 group-hover:text-gray-300">
                  View settings
                </p>
              </div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
}
