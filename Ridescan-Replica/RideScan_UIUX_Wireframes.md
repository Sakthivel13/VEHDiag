# RideScan — UI/UX Wireframes & Screen Flow

**Document status:** Reconstructed from layout resource identifiers (`activity_*`, `fragment_*`, `dialog_*`, `item_*`) and Activity manifest structure — not from rendered screenshots or design files. Layouts below are **low-fidelity structural wireframes inferred from screen naming and standard UX patterns for this app category** (dealer diagnostic tools), not pixel-accurate reproductions of the real UI. I viewed a couple of the app's larger bundled images only to get a general sense of visual tone (dark, illustration-led onboarding/branding screens with a technical/automotive feel) — I'm not reproducing those images here.

---

## 1. Screen Inventory by Type

| Type | Count (approx.) | Naming pattern | Examples |
|---|---|---|---|
| Full-screen Activities | 97 | `activity_*` | `activity_login`, `activity_ecu_flashing`, `activity_pricol_flash` |
| Fragments (embedded views) | ~10+ | `fragment_*` | `fragment_vhr_dealer`, `fragment_one/two/three` |
| Dialogs / modals | 8+ | `dialog_*` | `dialog_odometer`, `dialog_retry_confirmation`, `dialog_erase_loader` |
| List item layouts | 4+ | `item_*`, `row_*` | `item_recycler_view`, `row_index_key` |
| Menus | 2 | `menu_*` | `menu_img`, `menu_lay` |

## 2. Primary User Flow (top-level navigation)

```
Splash ──▶ Welcome ──▶ Tutorial (first run) ──▶ Login / SSO ──▶ (Forgot PIN → OTP → New PIN)
                                                       │
                                                       ▼
                                                  UserType select
                                                       │
                                                       ▼
                                                     Home
                                        ┌──────────────┼───────────────┐
                                        ▼              ▼               ▼
                                  Vehicle List    Add Device      Notifications
                                        │
                                        ▼
                            VIN-Based Diagnosis/Flashing
                                        │
                        ┌───────────────┼────────────────┐
                        ▼               ▼                ▼
                  Select ECU     Select Flash Variant   (auto-detected path)
                        │               │
                        ▼               ▼
              ┌── Diagnostics ──┐  ┌── ECU Flashing ──┐
              │                  │  │  (per supplier)   │
              ▼                  │  ▼                    │
        Read DTCs                │  Continental/Bosch/    │
        Live Parameter            │  Pricol/Sedemac/       │
        Live Data Recording       │  Mikuni/Keihin/INEL/   │
        IO Control                │  ISG/Cluster flashing   │
        Routine Control           │                          │
        IUPR Test                 └──────────┬───────────────┘
        Manual Diagnostic                     ▼
        Gear Learning                  Flash progress/result
              │                               │
              └───────────────┬───────────────┘
                               ▼
                     Diagnostic / VHR Report
                               │
                               ▼
                  Report Summary ──▶ PDF export / File Viewer
```

## 3. Key Screen Wireframes (structural, low-fidelity)

### 3.1 Login (`activity_login`)
```
┌─────────────────────────────┐
│         [RideScan logo]      │
│                               │
│   ┌───────────────────────┐   │
│   │ Dealer ID / Username    │   │
│   └───────────────────────┘   │
│   ┌───────────────────────┐   │
│   │ Password                │   │
│   └───────────────────────┘   │
│                               │
│        [   Login   ]          │
│                               │
│      Forgot PIN?  ·  SSO       │
└─────────────────────────────┘
```

### 3.2 Home (`activity_home`)
```
┌─────────────────────────────┐
│  ☰   RideScan        🔔  ⚙   │
├─────────────────────────────┤
│  ┌───────┐ ┌───────┐          │
│  │ Vehicle│ │  Add   │          │
│  │  List  │ │ Device │          │
│  └───────┘ └───────┘          │
│  ┌───────┐ ┌───────┐          │
│  │ VIN    │ │ Manual │          │
│  │ Scan   │ │ Diag   │          │
│  └───────┘ └───────┘          │
│  ┌───────┐ ┌───────┐          │
│  │Reports │ │Service │          │
│  │        │ │ Manual │          │
│  └───────┘ └───────┘          │
├─────────────────────────────┤
│  Dealer: [Name]  Branch: [X]  │
└─────────────────────────────┘
```
*Grid of feature tiles is the inferred pattern, consistent with `menu_img`/`menu_lay` resource names and the flat top-level feature set observed in the manifest.*

### 3.3 VIN-Based Diagnosis / Select ECU (`activity_...`, `SelectECUActivity`)
```
┌─────────────────────────────┐
│  ← Select Vehicle             │
├─────────────────────────────┤
│  VIN: [ scan / manual entry ]  │
│  Model: RTR160 4V              │
│  Variant: RTR160_4V_1CH_EFI_BSVI│
│  Norm: BSVI                    │
├─────────────────────────────┤
│  Select ECU:                   │
│   ○ EMS                         │
│   ○ ABS                         │
│   ○ Cluster                     │
├─────────────────────────────┤
│        [ Connect VCI ]          │
└─────────────────────────────┘
```

### 3.4 ECU Flashing Flow (generic across supplier variants, e.g. `activity_pricol_flash`)
```
┌─────────────────────────────┐
│  ← Pricol Flash — RTR160        │
├─────────────────────────────┤
│  VCI: Connected ●                │
│  Current FW: v2.1.0               │
│  Target FW:  v2.3.4                │
├─────────────────────────────┤
│  [ dialog_erase_loader ]          │
│  ▓▓▓▓▓▓▓▓▓░░░░░░░  56%             │
│  "Erasing... Do not disconnect"    │
├─────────────────────────────┤
│  Status log:                       │
│  > Session established              │
│  > Security access granted           │
│  > Erase sequence complete            │
├─────────────────────────────┤
│  [ Retry ]   (dialog_retry_confirmation on failure) │
└─────────────────────────────┘
```
*The presence of `dialog_erase_loader` and `dialog_retry_confirmation` strongly implies a progress-modal + failure-recovery pattern shared across all ~25 supplier-specific flashing activities, rather than each screen having bespoke UX.*

### 3.5 Odometer / Data Entry Dialog (`dialog_odometer`)
```
┌───────────────────────┐
│   Enter Odometer Reading │
│   ┌─────────────────┐    │
│   │      [ km ]        │    │
│   └─────────────────┘    │
│      [Cancel]  [OK]         │
└───────────────────────┘
```
*Suggests VHR/diagnostic reports capture odometer reading as a manual input step — a compliance/record-keeping field common to service reports.*

### 3.6 Vehicle Health Report (VHR) Tabs (`fragment_vhr_dealer`, `_diagnostic`, `_io_control`, `_summary`)
```
┌─────────────────────────────┐
│  Vehicle Health Report          │
├─────────────────────────────┤
│ [Dealer Info] [Diagnostic] [IO] [Summary] │  ← tabbed fragment navigation
├─────────────────────────────┤
│   (active tab content)           │
│                                   │
├─────────────────────────────┤
│         [ Generate PDF ]           │
└─────────────────────────────┘
```
*Four fragment names sharing the `fragment_vhr_*` prefix strongly indicate a single Activity hosting a ViewPager/TabLayout with four swipeable sections — a standard pattern for multi-part reports.*

### 3.7 Live Data Recording (`activity_live_data_recording`)
```
┌─────────────────────────────┐
│  ← Live Data Recording           │
├─────────────────────────────┤
│  RPM:      3200    Speed: 42km/h  │
│  Coolant:  78°C    Battery: 12.6V │
│  [ live sparkline/graph area ]    │
├─────────────────────────────┤
│   ● REC  00:34        [Stop]      │
└─────────────────────────────┘
```

## 4. Interaction Patterns Observed / Inferred

| Pattern | Evidence |
|---|---|
| Progress-blocking modals during flash operations | `dialog_erase_loader`, `dialog_loader_overlay` |
| Confirm-before-retry on failure | `dialog_retry_confirmation` |
| Multi-message alert dialogs (varying content length) | `dialog_message3/4/6` — suggests a shared dialog component parameterized by message variant, not one-off screens |
| Tabbed sub-report navigation | `fragment_vhr_*` set |
| Recycler-based lists throughout (vehicle list, DTC list, log viewer) | `item_recycler_view`, `item_row`, `row_index_key` |
| In-app chatbot/support surface | `activity_chat_bot` layout present, though not listed as a manifest Activity — likely presented as a fragment/bottom-sheet rather than a full screen |
| Screen recording overlay during sessions | `OverlayService`/`ScreenRecordOverlayService`, likely a floating record button visible during diagnostic/flash flows |

## 5. Design System Notes *(inferred, low confidence)*

- Material Components + Material3 dependencies present (`color-v31`, `values-night`, dynamic color support) — app likely supports Android 12+ dynamic theming and a dark mode variant.
- Custom font family declared (`fontFamily`/`fontProvider*` resources) — branded typography rather than default system font.
- Icon set (~66 `ic_*` drawables) sized for a bottom-nav/toolbar-driven IA rather than a hamburger-drawer-only pattern, though both are plausible given `menu_lay`/`menu_img` naming.

---
*This document should be validated against actual Figma/design files or screenshots if available — it reconstructs structure and likely intent, not exact visuals, spacing, or copy.*
