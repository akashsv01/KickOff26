"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppToast } from "@/components/AppToast";
import { NotificationBell } from "@/components/matchday/NotificationBell";
import { ThemeToggle } from "@/components/ThemeToggle";
import { TrophyIcon } from "@/components/TrophyIcon";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/matchday", label: "Live Matches" },
  { href: "/standings", label: "Standings" },
  { href: "/teams", label: "Teams" },
  { href: "/bracket", label: "Predictions" },
  { href: "/fanplan", label: "Travel Planner" },
  { href: "/following", label: "Following" },
  { href: "/watch", label: "Fan Rooms" },
  { href: "/resources", label: "Resources" },
];

export default function Nav() {
  const { user, logout, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [logoutToast, setLogoutToast] = useState(false);

  function handleLogout() {
    logout();
    setOpen(false);
    setLogoutToast(true);
    router.push("/");
  }

  const isMatchDay = pathname.startsWith("/matchday");

  // Close the drawer on route change.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Lock body scroll while the mobile drawer is open.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(`${href}/`);

  return (
    <nav className="app-nav">
      {logoutToast ? (
        <AppToast
          message="You've been signed out."
          onDismiss={() => setLogoutToast(false)}
          autoDismissMs={3500}
        />
      ) : null}
      <div className="relative z-[60] mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4">
        <Link href="/" className="flex shrink-0 items-center gap-2 text-xl font-bold text-app-gold">
          <TrophyIcon className="h-7 w-7" />
          <span>KickOff26</span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden items-center justify-end gap-x-2 gap-y-2 text-sm md:flex md:flex-wrap">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={isActive(l.href) ? "nav-link-active" : "nav-link"}
            >
              {l.label}
            </Link>
          ))}
          <div className="ml-1 flex items-center gap-2">
            <ThemeToggle />
            {isMatchDay && <NotificationBell />}
          </div>
          {!loading && user ? (
            <>
              <Link
                href="/profile"
                className={isActive("/profile") ? "nav-link-active ml-1" : "nav-link ml-1"}
              >
                Hi, {user.username}
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="nav-link"
              >
                Log out
              </button>
            </>
          ) : (
            <Link href="/auth" className={isActive("/auth") ? "nav-link-active" : "nav-link"}>
              Account
            </Link>
          )}
        </div>

        {/* Mobile controls */}
        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          {isMatchDay && <NotificationBell />}
          <button
            type="button"
            className="nav-icon-btn"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="mobile-nav-drawer"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {open && (
        <>
          <button
            type="button"
            className="nav-drawer-scrim md:hidden"
            aria-label="Close menu"
            tabIndex={-1}
            onClick={() => setOpen(false)}
          />
          <div id="mobile-nav-drawer" className="nav-drawer md:hidden">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className={`nav-drawer-link${isActive(l.href) ? " nav-drawer-link-active" : ""}`}
              >
                {l.label}
              </Link>
            ))}
            <div className="nav-drawer-divider" />
            {!loading && user ? (
              <>
                <Link
                  href="/profile"
                  className={`nav-drawer-link${isActive("/profile") ? " nav-drawer-link-active" : ""}`}
                >
                  Profile ({user.username})
                </Link>
                <button type="button" onClick={handleLogout} className="nav-drawer-link text-left">
                  Log out
                </button>
              </>
            ) : (
              <Link
                href="/auth"
                className={`nav-drawer-link${isActive("/auth") ? " nav-drawer-link-active" : ""}`}
              >
                Account
              </Link>
            )}
          </div>
        </>
      )}
    </nav>
  );
}
