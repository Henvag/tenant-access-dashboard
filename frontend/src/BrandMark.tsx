/** Product mark for sidebar, splash, and landing hero. */
export default function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      className="brand-mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="brandMarkGrad" x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#14b8a6" />
          <stop offset="1" stopColor="#0f766e" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#brandMarkGrad)" />
      <path
        d="M9 16.5c0-3.6 2.9-6.5 6.5-6.5h1.2c2.4 0 4.3 1.9 4.3 4.3v.4c0 1.7-1.4 3.1-3.1 3.1H16"
        fill="none"
        stroke="#ecfdf8"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <circle cx="16" cy="16.5" r="2.2" fill="#ecfdf8" />
    </svg>
  );
}
