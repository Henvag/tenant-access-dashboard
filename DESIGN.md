# Tenant Access design rules

Read this before changing anything a person sees. It exists so the product keeps one look instead of
drifting back to whatever a generator or a UI kit produces by default. The values below live in
`frontend/src/styles.css` under `:root`; change them there and here together.

The rules draw on three public guides: [taste-skill](https://github.com/Leonxlnx/taste-skill) (its list
of generated-design tells and its study of real app screens), [HyperFrames](https://github.com/heygen-com/hyperframes)
(write the look down once, real UI only) and [ai-design-skills](https://github.com/elayadesign/ai-design-skills)
(type scale, radius and motion discipline).

## Type

- One typeface: **Schibsted Grotesk** (400, 500, 600; 700 only where a number is the point). It was drawn
  for Schibsted, the Oslo media group, which suits a product with a Norwegian side. No second face except
  the system monospace for client IDs, URLs and keys.
- Sizes, and nothing between them: 12, 14, 16, 18, 20, 24, 30px. App body text is 14px, labels and meta
  12px, page titles 24px. Landing headlines may use a `clamp()` up to 48px.
- Sentence case everywhere. No uppercase letter-spaced labels, table headers or eyebrows.
- Numbers that line up use `font-variant-numeric: tabular-nums` and sit right-aligned.
- No italics, no gradient or outlined text, no text shadows.

## Colour

The palette is called Fjord: pale green-grey grounds, near-black type and one deep green accent.

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#f5f7f6` | Page ground, also the sidebar |
| `--surface` | `#ffffff` | Cards and panels |
| `--surface-2` | `#ecf0ef` | Inputs, segmented controls, avatars |
| `--ink` | `#0f1715` | Text and the primary button |
| `--ink-2` | `#29332f` | Leads and body copy under a heading |
| `--muted` | `#56625e` | Secondary text (5.9:1 on `--bg`) |
| `--line` | `#dbe2e0` | Borders and row rules |
| `--line-strong` | `#c2cbc8` | Secondary button borders, hovered cards |
| `--accent` | `#0a6455` | Links, focus rings, the brand mark, data that matters |
| `--accent-soft` | `#e1efea` | Accent pills and step numbers |
| `--danger` | `#b42318` | Refusals and destructive actions only |

The landing page has two dark surfaces, the Security section and the featured (Team) plan card in Pricing, and inside them only the night tokens:

| Token | Value | Use |
| --- | --- | --- |
| `--night` | `#0f1a17` | Ground of the Security section |
| `--night-ink` | `#e8efec` | Headings and titles on night |
| `--night-muted` | `#9aaba5` | Body text on night (7.4:1) |
| `--night-accent` | `#6cd2b8` | Links on night |
| `--night-line` | `#26332f` | Rules on night |
| `--night-raised` | `#142420` | The separation figure's panel on night |
| `--night-warm` | `#e7b66b` | Company B in the separation figure, nothing else |

- The accent goes on data and links, not on chrome, and stays under about 5% of a screen. Primary
  buttons are near-black (`--ink`), one per view; the others are `.btn-secondary` (white, `--line-strong`
  border).
- The brand mark is a flat `--accent` square with a pale glyph (`BrandMark.tsx`, `public/favicon.svg`).
  No gradient.
- Status pills are a pale tint with dark text of the same hue. Never a saturated fill with white text.
- One status colour per row. A refusal reason is red text, an ordinary reason is plain text.
- Avatars are neutral initials. No colour per person.
- No gradients on grounds, buttons, cards or placeholders. No glows, glass or backdrop blur.

## Shape

- Radius is tight and chosen once: cards 8px, controls 6px, chips and code 4px. Pills and avatars are
  fully round.
- A border or a shadow, never both. Resting cards have a 1px `--line` border and no shadow. Shadows
  (`--shadow`) are only for what floats: menus, dialogs and tooltips.
- No one-sided accent bars on cards, nav items or notices.
- Group figures in one container split by 1px dividers, label over number, no icon. Never a row of
  separate cards with an icon in a tinted square.

## Layout

- The landing page is one page. Sign-in and registration stay on it, beside the hero; nothing moves to a
  page of its own.
- Landing sections share one column, `min(1100px, 100% - 2.5rem)`, the same as the nav bar.
- The sidebar sits on the page ground with a single rule on its right edge. The active item is a neutral
  grey fill.
- Tables use 12px grey sentence-case headers and 1px row rules. No zebra stripes, no header band.
- Every view must work at 390px wide with no horizontal page scroll. Wide tables scroll inside
  `.table-wrap`.

## Landing navigation

- A sticky bar on the page ground with one bottom rule and no blur: the mark and name, links to the
  sections in the same order as they appear on the page (How it works, Apps, Security, Pricing, FAQ), the
  EN/NO switch, a quiet "Sign in" link and the one dark button, "Explore the live demo".
- The link of the section on screen carries `aria-current` and is drawn in `--ink` with a 2px `--accent`
  rule on the bar's bottom edge. The others are `--muted`.
- Links are plain `#id` anchors, so the address can be shared (`tenantaccess.me/#pricing`). Scrolling is
  smooth unless reduced motion is on, and `scroll-padding-top` keeps the bar off each heading.
- Below 900px the links fold into a menu under the bar, in the same order. Escape closes it.

## Landing pricing

- Pricing is the one centered section: heading, lede and a Monthly/Yearly switch whose saving is worked
  out from the plan catalog, never typed in.
- Three plan cards: a tier mark, the name, who it is for, the price, one button, a rule, then the limits
  with check marks and the numbers in bold. Team is the featured card on `--night`, tagged
  "Recommended" (our advice, not a popularity claim). No "Most popular" labels.
- When a section is added, removed or moved, change `SECTIONS` in `Landing.tsx` so the nav keeps the
  page's order.

## Motion

- One easing curve for transitions and entrances: `--ease` (`cubic-bezier(0.22, 1, 0.36, 1)`). Never
  the browser default `ease`. Loading loops (spinner, typing dots) may stay linear.
- Animate only `transform` and `opacity`. No hover lift on cards; a hover changes the border colour.
- Everything respects `prefers-reduced-motion`.
- The one looping animation is the separation figure in the Security section (`SeparationFigure.tsx`):
  10 s, plays only while on screen, holds its first scene with reduced motion. Its request lines draw
  with `stroke-dashoffset`, the single exception to transform/opacity. It shows the real mechanism
  (one `users` table, row-level security), never a metaphor such as companies being torn apart.

## Copy

- No em dashes. Use a full stop, a comma or a colon.
- Plain, specific sentences: "Revoke someone's access and they are signed out of Grafana", not
  "Streamline access management".
- Banned words: seamless, effortless, unlock, supercharge, elevate, empower, streamline, robust,
  cutting-edge, all-in-one, "Get started", "Learn more".
- No "Step 2 of 6" labels, no eyebrow above a heading, no invented customer logos or vanity numbers.
- Errors say what failed and what to do next. No exclamation marks.

## Pictures

- Screenshots are the real product, captured from the demo company with `scripts/capture-demo.mjs`.
  Never a mock dashboard built from grey bars.
- Real brand marks (Google, Microsoft, Grafana, Outline) are welcome where they name something, small and
  inline. Decorative icons in tinted boxes, repeated on every item, are not.
- The landing film follows these rules too; its numbers (sizes, eases, shot timings) are in
  `film/SPEC.md`. After a visual change, re-capture and re-render it (`film/README.md`) and retake the
  README screenshots.
