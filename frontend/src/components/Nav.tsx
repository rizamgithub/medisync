"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { currentUser } from "@/lib/auth";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/request", label: "New Request" },
  { href: "/inventory", label: "Inventory" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <header className="nav">
      <div className="nav-inner container">
        <Link href="/" className="brand">
          <span className="brand-mark">+</span> MediSync
        </Link>
        <nav className="nav-links">
          {LINKS.map((link) => {
            const active =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={active ? "nav-link active" : "nav-link"}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="nav-user">
          <span className="nav-user-name">{currentUser.name}</span>
          <span className="badge badge-info">{currentUser.role}</span>
        </div>
      </div>
    </header>
  );
}
