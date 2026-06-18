"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AppToast } from "@/components/AppToast";
import { NotificationBell } from "@/components/matchday/NotificationBell";
import { ThemeToggle } from "@/components/ThemeToggle";
import { TrophyIcon } from "@/components/TrophyIcon";
import { useAuth } from "@/lib/auth";

type NavLink = { href: string; label: string };
type NavItem = NavLink | { label: string; items: NavLink[] };

const navItems: NavItem[] = [
  { href: "/matchday", label: "Live Matches" },
  { href: "/standings", label: "Standings" },
  {
    label: "Explore",
    items: [
      { href: "/teams", label: "Teams" },
      { href: "/stadiums", label: "Stadiums" },
    ],
  },
  { href: "/bracket", label: "Predictions" },
  { href: "/fanplan", label: "Travel Planner" },
  { href: "/following", label: "Following" },
  { href: "/watch", label: "Fan Rooms" },
  { href: "/resources", label: "Resources" },
];

function isPathActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Desktop "Explore" dropdown. Click-to-toggle (no hover-open, so there is no
 * dead zone between the button and the panel): the menu stays open until the
 * user clicks an item, clicks outside, or presses Escape. Fully keyboard- and
 * touch-accessible.
 */
function NavDropdown({
  label,
  items,
  pathname,
}: {
  label: string;
  items: NavLink[];
  pathname: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const parentActive = items.some((i) => isPathActive(pathname, i.href));

  const close = (returnFocus = false) => {
    setOpen(false);
    if (returnFocus) buttonRef.current?.focus();
  };

  // Move roving focus between menu items (wraps); reads the live DOM so we
  // don't have to thread refs through next/link.
  const focusItemAt = (index: number) => {
    const nodes = ref.current?.querySelectorAll<HTMLAnchorElement>('[role="menuitem"]');
    if (!nodes || nodes.length === 0) return;
    const next = (index + nodes.length) % nodes.length;
    nodes[next]?.focus();
  };

  // Close on outside pointer (mouse + touch + pen) and on Escape.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close(true);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Close when the route changes (e.g. after selecting an item).
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  function onTriggerKeyDown(e: React.KeyboardEvent<HTMLButtonElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      requestAnimationFrame(() => focusItemAt(0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      requestAnimationFrame(() => focusItemAt(-1));
    }
  }

  function onItemKeyDown(e: React.KeyboardEvent<HTMLAnchorElement>, index: number) {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        focusItemAt(index + 1);
        break;
      case "ArrowUp":
        e.preventDefault();
        focusItemAt(index - 1);
        break;
      case "Home":
        e.preventDefault();
        focusItemAt(0);
        break;
      case "End":
        e.preventDefault();
        focusItemAt(-1);
        break;
      case "Escape":
        e.preventDefault();
        close(true);
        break;
      case "Tab":
        // Let focus leave naturally, but don't leave an orphaned open menu.
        setOpen(false);
        break;
    }
  }

  return (
    <div ref={ref} className="nav-dropdown">
      <button
        ref={buttonRef}
        type="button"
        className={`nav-dropdown-trigger ${parentActive ? "nav-link-active" : "nav-link"}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={onTriggerKeyDown}
      >
        {label}
        <svg
          className={`nav-dropdown-caret${open ? " nav-dropdown-caret-open" : ""}`}
          width="11"
          height="11"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div className="nav-dropdown-menu" role="menu" aria-label={label}>
          {items.map((i, idx) => (
            <Link
              key={i.href}
              href={i.href}
              role="menuitem"
              tabIndex={-1}
              className={`nav-dropdown-item${isPathActive(pathname, i.href) ? " nav-dropdown-item-active" : ""}`}
              onClick={() => close()}
              onKeyDown={(e) => onItemKeyDown(e, idx)}
            >
              {i.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

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
          {navItems.map((item) =>
            "items" in item ? (
              <NavDropdown
                key={item.label}
                label={item.label}
                items={item.items}
                pathname={pathname}
              />
            ) : (
              <Link
                key={item.href}
                href={item.href}
                className={isActive(item.href) ? "nav-link-active" : "nav-link"}
              >
                {item.label}
              </Link>
            )
          )}
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
            {navItems.map((item) =>
              "items" in item ? (
                <div key={item.label} className="nav-drawer-group">
                  <span className="nav-drawer-group-label">{item.label}</span>
                  {item.items.map((s) => (
                    <Link
                      key={s.href}
                      href={s.href}
                      className={`nav-drawer-link nav-drawer-sublink${isActive(s.href) ? " nav-drawer-link-active" : ""}`}
                    >
                      {s.label}
                    </Link>
                  ))}
                </div>
              ) : (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`nav-drawer-link${isActive(item.href) ? " nav-drawer-link-active" : ""}`}
                >
                  {item.label}
                </Link>
              )
            )}
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
