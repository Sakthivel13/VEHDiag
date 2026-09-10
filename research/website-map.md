# VEHDiag Research — Reference Website Map

Reference product: **InDiag** — https://www.indiag.co/
Research date: 2026-09-01 (UTC). Method: public HTTP fetches only (no auth bypass, no private resources). robots.txt respected.

## Public page inventory (from sitemap.xml + linked pages)

| URL | Purpose | Status |
|---|---|---|
| / | Homepage — product marketing | OBSERVED |
| /features | Feature showcase | OBSERVED (in sitemap) |
| /about | Company/about | OBSERVED (in sitemap) |
| /partnership | Partner program | OBSERVED (in sitemap) |
| /shop | Hardware store ("Diagnostic Kits", Personal/Workshop) | OBSERVED |
| /blog | Blog index (100+ posts, categories: diagnostics, workshop, obd-guide, tips-and-tricks, industry, product) | OBSERVED (in sitemap) |
| /contact | Contact page | OBSERVED (in sitemap) |
| /support | Help center, FAQs, chat widget, tickets | OBSERVED |
| /privacy-policy, /terms, /shipping-policy, /refund-policy | Legal pages | OBSERVED (in sitemap) |
| /login, /signup, /dashboard, /account, /checkout, /delete-account | Disallowed by robots.txt → NOT PUBLICLY OBSERVABLE via crawl | NOT PUBLICLY OBSERVABLE |
| web.indiag.co | Web dashboard (referenced on homepage as "Cross-Platform Sync") | INFERRED from marketing copy |
| /indiag.apk (probe) | 404 — no APK at root path | OBSERVED |

## Mobile app distribution

| Channel | Evidence |
|---|---|
| Google Play | https://play.google.com/store/apps/details?id=com.indiag.mobile (homepage "Get the App", footer/support "App" links, pcampaignid=web_share) — OBSERVED |
| iOS | Homepage has "Download for iOS" link → href="#" placeholder — OBSERVED (not a real store link on the public page) |
| Direct APK on www.indiag.co | Not found; no *.apk href/src in homepage HTML; /indiag.apk → 404 — OBSERVED (absent) |
| GitHub zip | User-supplied artifact: `Indiag.zip` in the VEHDiag repo contains `base.apk` (38,333,274 bytes). Distribution pattern: APK zipped and committed to a GitHub repository for direct download — OBSERVED (user-provided evidence) |
| web.indiag.co app | Referenced in marketing copy ("web dashboard") — INFERRED |

## Pattern adopted by VEHDiag (implementation decision)

1. Build our own `VEHDiag.apk` (independent code, independent signing).
2. Commit it (and a distributable `VEHDiag.zip`) to the VEHDiag GitHub repository.
3. Serve the APK from the VEHDiag website at `/downloads/VEHDiag.apk` with version, size, SHA-256, and QR code — mirroring how InDiag makes its Android app downloadable (Play Store primary + direct-download pattern).
4. Secondary links: Google Play listing placeholder (package `com.vehdiag.app`) and GitHub Releases.
