# Spec: Tenant Access, "Someone leaves"

GOAL:    a visitor understands in 25 s that one admin controls who opens which company app, can switch a person off, and sees every refusal, then clicks Explore the live demo.
OUTPUT:  HyperFrames, 1920 x 1080, 30 fps.
TIME:    25 s x 30 = 750 frames. No music.

LOOK:
- Ground #f0f2f2 (the product's --surface-2), flat, no texture.
- Ink #111418, muted #5f6670, one word in --danger #b42318 ("refusal"). No teal outside the product's own UI.
- Type: Schibsted Grotesk only. Lines 50 px / 600 / -0.02em / line-height 1.12; quiet line 28 px / 400 / muted. End card wordmark 72 px / 600; CTA 28 px / 500.
- Medium: the real product UI, captured at 2x from the demo company (scripts in the PR). Window 1176 x 735 at x 648, y 173, radius 12, shadow 0 1px 2px rgba(17,20,24,.06) + 0 18px 48px rgba(17,20,24,.10). No border.
- Left column x 192 to 600 holds one line at a time, vertically centred.

OBJECTS:
- The app window: the real dashboard, sidebar included, so it reads as software without a label.
- The cursor: black arrow with a 2 px white edge, 46 px tall (4.3% of frame), soft 2 px drop shadow.
- The brand mark: the product's own SVG from BrandMark.tsx.

MOTION:
- Camera: power2.inOut, 0.5 to 0.6 s per move. Push scale 1.84 so 14 px UI text renders at 26 px or more.
- Cursor travel: power3.inOut, 0.45 to 0.7 s. Click: scale 1 → 0.86 in 0.07 s (power2.in), back in 0.12 s (power2.out).
- Screen change after a click: the next real screen replaces it in 2 frames (0.06 s); the sidebar pixels match so only the page changes.
- Lines: L1 and L4 per word blur 6 px → 0, 0.13 s, 0.067 s apart; L2 per word grey #c5cacd → ink, 0.08 s apart; L3 whole line blur 8 px → 0 in 0.18 s. Exits blur 6 px + fade, 0.16 s.
- Spotlight: rows that are not the subject take a white veil at 60% in 0.25 s power2.out.

SHOTS:
1. 0.0 to 3.7: overview. Window settles 0.97 → 1 (expo.out 1.0 s). L1 "One sign-in for your company's apps." Push to the app tiles (1.0), cursor rests on Grafana, pull back, cursor clicks Apps (3.65).
2. 3.7 to 9.0: apps. L2 "Choose who can open each app." Push to the app list; the cursor visits Everyone, Assigned people, Admins only, each row spotlit. Pull back; click People (9.0).
3. 9.0 to 16.0: people. L3 "Someone leaves? Switch off their access." Push to Jonas Lie, not yet disabled. Pan to his menu; click; Disable; the row turns Disabled. Quiet line "Their next app sign-in is refused." Pan back to "Jonas Lie, Disabled". Pull back; click Audit (16.0).
4. 16.0 to 21.3: audit. L4 "Every sign-in and refusal is logged." Push to the table, scroll to Jonas: "Failed sign-in, Account disabled" and "Access disabled, By admin"; other rows veiled; cursor points at the Failed sign-in row. Pull back; the sidebar's brand mark lifts out and carries to centre while the window blurs away.
5. 21.2 to 25.0: end card. Mark centred at 912, 330 (96 px). "Tenant Access" wipes in below, then the "Explore the live demo" button and tenantaccess.me. Held 3 s.

BANNED: dark void, glow, gradients outside the brand mark, glass, three cards in a row, a title over a dimmed screenshot, the logo in a corner, click rings, UI tilted in 3D, invented UI, em dashes, every line entering the same way, floating or breathing loops.

NORWEGIAN: same shots and timings. L1 "Én innlogging for selskapets apper." L2 "Velg hvem som kan åpne hver app." L3 "Slutter noen? Slå av tilgangen deres." / "Neste innlogging i en app blir avvist." L4 "Hver innlogging og avvisning logges." ("avvisning" in red). CTA "Utforsk live-demoen".

QA: 2.0 (tiles readable), 5.2 (Everyone spotlit), 10.3 (Jonas Active readable), 12.7 (Disabled status), 18.6 (Account disabled readable, cursor on it), 20.9 (mark mid-carry), 24.5 (end card complete).
