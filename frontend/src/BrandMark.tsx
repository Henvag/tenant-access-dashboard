/**
 * Product mark for sidebar, splash, and landing nav: the T-key. The T of Tenant drawn as a key, with a
 * ring in the bow (where it hangs from in motion) and one tooth at the tip. Flat Fjord square, no gradient.
 * The same drawing lives in public/favicon.svg and the film's demo.html and endcard.html.
 */
export default function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      className="brand-mark"
      width={size}
      height={size}
      viewBox="0 0 256 256"
      aria-hidden="true"
    >
      <rect width="256" height="256" rx="72" fill="#0a6455" />
      <path
        fillRule="evenodd"
        fill="#e8f5f0"
        d="M71.84 60.92H184.16A12.48 12.48 0 0 1 196.64 73.40V92.12A12.48 12.48 0 0 1 184.16 104.60H143.60V160.76H171.68V176.36H159.20V195.08H112.40V104.60H71.84A12.48 12.48 0 0 1 59.36 92.12V73.40A12.48 12.48 0 0 1 71.84 60.92ZM128 74.18A8.58 8.58 0 1 0 128 91.34A8.58 8.58 0 1 0 128 74.18Z"
      />
    </svg>
  );
}
