/**
 * Understated, reusable sign-off footer (glass-card theme). Rendered on the
 * Resources page for now. Inline lucide-style SVGs - no extra dependency.
 */

const iconProps = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

function GithubIcon() {
  return (
    <svg {...iconProps}>
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.4 5.4 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </svg>
  );
}

function LinkedinIcon() {
  return (
    <svg {...iconProps}>
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
      <rect width="4" height="12" x="2" y="9" />
      <circle cx="4" cy="4" r="2" />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg {...iconProps}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
      <path d="M2 12h20" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg {...iconProps}>
      <rect width="20" height="16" x="2" y="4" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  );
}

function HeartIcon() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 24 24"
      fill="currentColor"
      className="footer-heart"
      role="img"
      aria-label="love"
    >
      <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
    </svg>
  );
}

const LINKS = [
  { label: "GitHub", href: "https://github.com/akashsv01", Icon: GithubIcon },
  { label: "LinkedIn", href: "https://linkedin.com/in/akash-s-vora", Icon: LinkedinIcon },
  { label: "Portfolio", href: "https://akashsvora.dev", Icon: GlobeIcon },
];

const CONTACT_EMAIL = "akashvora301@gmail.com";

export function SiteFooter() {
  return (
    <footer className="resources-footer">
      <div className="resources-footer-inner">
        <p className="resources-footer-built">
          Built with <HeartIcon /> by <span className="resources-footer-name">Akash S Vora</span>
        </p>

        <p className="resources-footer-contact">
          Have feedback or suggestions?{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>Reach out</a> - I would love to hear from you.
        </p>

        <nav className="resources-footer-links" aria-label="Social and contact links">
          {LINKS.map(({ label, href, Icon }) => (
            <a
              key={label}
              href={href}
              className="footer-link"
              target="_blank"
              rel="noopener noreferrer"
              aria-label={label}
            >
              <Icon />
              <span>{label}</span>
            </a>
          ))}
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="footer-link"
            aria-label="Email Akash S Vora"
          >
            <MailIcon />
            <span>Contact</span>
          </a>
        </nav>
      </div>
    </footer>
  );
}
