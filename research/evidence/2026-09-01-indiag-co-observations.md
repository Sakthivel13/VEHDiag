# Evidence Log — 2026-09-01

Source: https://www.indiag.co/ (public fetches, UTC 2026-09-01)

1. robots.txt (OBSERVED): allows *, disallows /dashboard, /account, /checkout, /login, /signup, /delete-account; sitemap at /sitemap.xml.
2. sitemap.xml (OBSERVED): ~110 public URLs — marketing, shop, blog, support, legal.
3. Homepage hero: "Electric Bikes, Fully Decoded" — EV support for Bajaj Chetak, Hero Vida, Ather (OBSERVED).
4. Homepage app links: "Download for iOS" → "#", "Download for Android" → "#" placeholders (OBSERVED); footer "Get the App" → Google Play com.indiag.mobile (OBSERVED).
5. No .apk asset served from www.indiag.co homepage HTML; /indiag.apk → themed 404 "P0404 — ROUTE_NOT_FOUND" (OBSERVED).
6. Shop: hardware kits (Personal/Workshop), 1-year warranty, WhatsApp sales channel (OBSERVED).
7. Support: FAQs, ticket system, chat widget, phone/email/WhatsApp (OBSERVED).
8. User-provided artifact: `Indiag.zip` (SHA-256 dccee9b9702215bd5df4037d1043419250436796446fa5801d619cf17ab58752) contains `base.apk` (38,333,274 bytes), a Compose-based Android app (OBSERVED via zip listing only — no decompilation performed).
9. Technology signals from homepage markup: SPA with hashed asset names (/assets/...webp), Remix/RR-style bundle names — INFERRED, not used for implementation.

VEHDiag decisions: independent implementation; no reference assets copied; purple design system; own APK.
