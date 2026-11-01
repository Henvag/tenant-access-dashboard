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

| Token | Value | Use |
| --- | --- | --- |
| `--bg` | `#f7f8f8` | Page ground, also the sidebar |
| `--surface` | `#ffffff` | Cards and panels |
| `--surface-2` | `#f0f2f2` | Inputs, segmented controls, avatars |
| `--ink` | `#111418` | Text and the primary button |
| `--muted` | `#5f6670` | Secondary text (passes 4.5:1 on `--bg`) |
| `--line` | `#e3e6e7` | Borders and row rules |
| `--accent` | `#0f766e` | Links, focus rings, data that matters |
| `--danger` | `#b42318` | Refusals and destructive actions only |

- The accent goes on data and links, not on chrome. Primary buttons are near-black (`--ink`).
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

- The sidebar sits on the page ground with a single rule on its right edge. The active item is a neutral
  grey fill.
- Tables use 12px grey sentence-case headers and 1px row rules. No zebra stripes, no header band.
- Every view must work at 390px wide with no horizontal page scroll. Wide tables scroll inside
  `.table-wrap`.

## Motion

- One easing curve for transitions and entrances: `--ease` (`cubic-bezier(0.22, 1, 0.36, 1)`). Never
  the browser default `ease`. Loading loops (spinner, typing dots) may stay linear.
- Animate only `transform` and `opacity`. No hover lift on cards; a hover changes the border colour.
- Everything respects `prefers-reduced-motion`.

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
- After a visual change, retake the tour images (`frontend/src/assets/tour/`) and check the hotspot
  positions in `ProductTour.tsx` still land on their targets.
