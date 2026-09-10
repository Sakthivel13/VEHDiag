# RideScan — DevOps & Tooling

**Document status:** Build-system facts (marked confirmed) come directly from artifacts embedded in the APK. CI/CD pipeline, testing infrastructure, and release-process details are not observable from a compiled binary and are marked inferred/typical — offered as a reasonable baseline for this tech stack, not as evidence of what's actually in place.

---

## 1. Build System **(confirmed)**

| Item | Evidence |
|---|---|
| Build tool | Android Gradle Plugin (AGP) — standard for this project shape |
| Language | Kotlin (Kotlin builtins/metadata bundled; `*ViewModel.kt` naming throughout) |
| Resource shrinking | Active — resource *file paths* obfuscated to 1–3 character names (e.g. `res/xu.png`) while resource *identifiers* remain intact in `resources.arsc` |
| Code shrinking/obfuscation | Some classes reduced to single-letter names (e.g. `btlibrary/a.kt`–`f.kt`), consistent with R8 in default (non-full) obfuscation mode |
| Baseline Profiles | `assets/dexopt/baseline.prof` + `baseline.profm` present — confirms use of AGP's Baseline Profile feature for startup/runtime performance optimization, which requires a profile-generation step (via Macrobenchmark or Play Console) in the build pipeline |
| Version control | Git — revision `e86ca92a8698c7d8f052099c4278bf69c0012b4a` embedded via AGP's `version-control-info.textproto`, meaning `android.buildFeatures` VCS-info embedding is enabled in the build config |
| Native build | NDK-compiled `libridescan_security.so`, shipped for `armeabi-v7a`, `arm64-v8a`, `x86`, `x86_64` — implies a CMake/ndk-build step in the Gradle config, either in-module or pulled in as a prebuilt `.aar`/binary from a separate native repo |

## 2. Dependency Management **(confirmed versions where observed)**

| Dependency | Version | Notes |
|---|---|---|
| play-services-basement | 18.4.0 | Transitive dependency of Play Services Location |
| play-services-location | 21.3.0 | BLE-scan-related location requirement |
| Retrofit2 / OkHttp3 | not version-pinned in strings | Networking |
| AndroidX Room | not version-pinned in strings | Local persistence |
| iTextPDF | not version-pinned in strings | Report generation — **note:** iText is AGPL/commercial-licensed; worth confirming license compliance for a commercial dealer app if this wasn't already accounted for |
| BouncyCastle | not version-pinned in strings | Crypto/cert handling |

*(inferred)* Given standard Kotlin/Android tooling of this shape, dependency management is almost certainly via Gradle Version Catalogs (`libs.versions.toml`) or classic `build.gradle` version blocks — not directly observable.

## 3. Distribution Model **(confirmed)**

- **Not distributed via Google Play** — the app carries `REQUEST_INSTALL_PACKAGES` permission and dedicated `UpdateActivity`/`UpdateDescriptionActivity` screens for in-app self-update, which is the standard pattern for **internal/enterprise (dealer-network) distribution** rather than public Play Store release.
- This implies an internal artifact host serving APKs (likely the same `amsmssi.com/DMS/` backend, or an adjacent internal endpoint) plus a version-check/update-prompt flow on launch (`BootstrapResponse`, `AppUpdateResponse` models).

*(inferred)* This distribution model typically pairs with:
- An internal MDM (Mobile Device Management) solution for dealer tablets/phones, or a simple "sideload via DMS portal" process
- A signing key managed internally rather than Play App Signing

## 4. CI/CD *(inferred — typical for this stack, not evidenced)*

Not observable from the binary. A reasonable baseline for a Kotlin/Gradle Android project of this scale:
- CI: GitHub Actions, GitLab CI, Bitrise, or Jenkins (common Android CI choices) running `./gradlew assembleRelease`/`bundleRelease`, lint, and unit tests per merge
- Static analysis: ktlint/detekt commonly paired with this stack, though no evidence either way
- Signing: release keystore managed via CI secrets or a dedicated release-management step, given the non-Play distribution model requires the team to manage its own signing pipeline end-to-end
- Baseline Profile generation likely requires a scheduled/manual Macrobenchmark run against a release build, feeding back into `baseline.prof` before each release

## 5. Testing *(largely unverifiable from the binary)*

- `okhttp3.mockwebserver.MockWebServer` string is present in the dex — **(confirmed)** this indicates OkHttp's MockWebServer library is bundled, which is normally a test-only dependency. Its presence in the shipped release binary suggests either:
  - Test dependencies weren't fully stripped from the release build variant, or
  - It's intentionally retained for in-field diagnostic/network-simulation tooling
  Worth flagging to the team if unintentional, since shipping test tooling in production APKs increases attack surface and APK size unnecessarily.
- No other UI/instrumentation testing framework (Espresso, Compose Test) markers were found in string search — doesn't rule out their use in CI (test code often lives in a separate source set not packaged into the release APK).

## 6. Security Tooling **(confirmed presence, not internals)**

- Native module `libridescan_security.so` — compiled/stripped, present across all 4 ABIs, loaded early in flash-related flows. Build-wise, this requires an NDK toolchain and likely a separate, more restricted-access repo/build pipeline for the native security logic, kept apart from the main app codebase.
- BouncyCastle bundled — supports either TLS/certificate pinning or payload signature verification (e.g. for verifying flash-file authenticity before writing to an ECU) — a reasonable requirement for a flashing tool operating on regulated (BSVI-emissions-relevant) vehicle firmware.

## 7. Observability *(not evidenced)*

No crash-reporting SDK (Firebase Crashlytics, Sentry, Bugsnag) or analytics SDK markers were found in the string search. This is either:
- Present but not identifiable via plain string search (some SDKs obfuscate their own markers), or
- Genuinely absent, which would be a notable gap for a field-deployed diagnostic tool — flash failures in particular seem like exactly the kind of event a team would want telemetry on, and `FlashFeedbackRequest`/`FlashReportResponse` models suggest failure reporting is at least handled via the app's own backend sync rather than a third-party crash/analytics SDK.

## 8. Suggested Tooling Checklist *(illustrative, not evidenced — useful as a gap-check against the real setup)*

- [ ] Confirm CI pipeline and whether Baseline Profile regeneration is automated or manual per release
- [ ] Confirm iText license compliance (commercial vs. AGPL usage) for this app's distribution model
- [ ] Verify `MockWebServer` inclusion in the release APK is intentional
- [ ] Confirm crash/telemetry coverage for flash-operation failures specifically, given the operational risk of a failed ECU flash
- [ ] Confirm dongle firmware (`.s19`) versioning/rollback process is tracked outside the app itself (e.g. a firmware release registry)

---
*Reconstructed from build artifacts and dependency traces only — cross-check against the team's actual CI config, `build.gradle`, and release runbooks for ground truth.*
