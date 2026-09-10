# RideScan — Reconstructed Project Folder Structure

**Package:** `com.ridescantp.mahle.ridescantp` · **Version analyzed:** 2.3.6
**Document status:** Reconstructed from the compiled APK — package names, class names, and resource *identifiers* (e.g. `activity_login`) survive R8/resource shrinking and are directly evidenced. Actual resource *file paths* (e.g. `res/xu.png`) were shortened by the build's resource-shrinker, so exact original filenames for drawables/layout XML are not recoverable — I've mapped them back to their most likely conventional names. Gradle file contents, exact module split, and build-variant config are inferred from standard Android/Kotlin project conventions, not observed directly.

---

## 1. Top-Level Layout (inferred — standard single-module Android/Gradle project)

```
RideScan/
├── app/                              # main (likely only) Gradle module
│   ├── build.gradle.kts (or .gradle)
│   ├── proguard-rules.pro
│   └── src/
│       └── main/
│           ├── AndroidManifest.xml
│           ├── java/ (or kotlin/)
│           │   └── com/ridescantp/mahle/ridescantp/
│           │       └── ... (see Section 2)
│           ├── res/
│           │   └── ... (see Section 3)
│           └── assets/
│               └── ... (see Section 4)
├── build.gradle.kts                  # project-level
├── settings.gradle.kts
├── gradle.properties
├── gradle/wrapper/
│   ├── gradle-wrapper.properties
│   └── gradle-wrapper.jar
└── local.properties
```

*(inferred)* Given the app's size and the fact that all 97 activities live under one package with no separate `:core`, `:network`, or `:data` module naming visible in class paths, this is most consistent with a **single-module `app/`** Gradle project rather than a multi-module setup — common for dealer-tool apps of this scope where team size doesn't justify modularization.

## 2. Source Tree — `app/src/main/java/com/ridescantp/mahle/ridescantp/` **(confirmed package paths)**

```
com/ridescantp/mahle/ridescantp/
│
├── RideScanApplication.kt            # Application class (inferred — standard entry point)
│
├── data/
│   └── model/                        # flat DTO/POJO package — request & response models
│       ├── AppUpdate.kt / AppUpdateResponse.kt
│       ├── BluetoothEvent.kt
│       ├── BootstrapResponse.kt
│       ├── Branch.kt
│       ├── CheckMail.kt / CheckVCI.kt
│       ├── ConfirmGTS/
│       │   ├── ConfirmGTSResponse.kt
│       │   └── ConfrimGTSRequest.kt   # (typo preserved from original — "Confrim")
│       ├── DTCsDatum.kt
│       ├── DealerEmployee.kt / DealerEmployeeInfo.kt
│       ├── DealerInfo.kt / DealerInfoResponse.kt
│       ├── Designation.kt
│       ├── Device.kt / DeviceList.kt
│       ├── DtcErrorCodeData.kt / DtcErrorCodeResponse.kt
│       ├── ECUModel.kt
│       ├── EcuFlash.kt / EcuFlashResponse.kt
│       ├── FMWData.kt
│       ├── FirmwareVersion.kt
│       ├── FlashFeedbackRequest.kt
│       ├── FlashModel.kt / FlashReportResponse.kt / FlashSequence.kt
│       ├── FlashVariant.kt / FlashVariantItem.kt
│       ├── FobkeyResponse/
│       │   ├── FobKeyModel.kt
│       │   └── FobKeyResponse.kt
│       ├── ForgotPasswordResponse.kt
│       ├── Functionality.kt
│       ├── FwDetail.kt
│       ├── GetVCIUpdateResponse.kt
│       ├── IOControl.kt / IoControlResponse.kt
│       ├── IUPRData.kt / IUPRHistory.kt / IUPRPrimary.kt / IUPRPrimaryModel.kt
│       │   / IUPRReport.kt / IUPRResponse.kt / IUPRSecondary.kt
│       ├── IuprInfoData.kt / IuprParameterData.kt / IuprUpdaeRequest.kt / IuprUpdateResponse.kt
│       ├── LiveDataRecording.kt
│       ├── LiveParameter.kt / LiveParameterResponse.kt
│       ├── LocalVCIFMW.kt
│       ├── LogInfo.kt
│       ├── LogViewer/
│       │   └── FileItem.kt
│       ├── NewPinResponse.kt
│       └── OTPRequestResponse.kt
│       # (list is representative — model package is large; ~50+ DTOs observed)
│
├── btlibrary/                         # Bluetooth Classic/BLE serial transport
│   ├── BluetoothUtil.kt
│   ├── Constants.kt
│   ├── SerialListener.kt
│   ├── SerialService.kt               # foreground service, holds live connection
│   ├── SerialSocket.kt
│   ├── TextUtil.kt
│   └── (6 additional obfuscated internal classes: a–f)
│
├── service/
│   ├── AppCloseService.kt
│   ├── ClientService.kt
│   ├── OverlayService.kt
│   └── ScreenRecordOverlayService.kt
│
└── ui/
    ├── login/LoginActivity.kt
    ├── register/RegisterActivity.kt
    ├── forgotpin/
    │   ├── ForgotPinActivity.kt
    │   ├── NewPinActivity.kt
    │   └── OTPActivity.kt
    ├── sso_dealership_login/SSOActivity.kt
    ├── usertype/UserTypeActivity.kt
    ├── welcome/WelcomeActivity.kt
    ├── tutorial/TutorialActivity.kt
    ├── splash/SplashActivity.kt
    ├── home/HomeActivity.kt
    ├── main/MainActivity.kt
    ├── notification/NotificationActivity.kt
    ├── account_details/AccountDetailsActivity.kt
    ├── dealerinformation/DealerInformationActivity.kt
    ├── add_device/AddDeviceActivity.kt
    ├── vehicle_list/VehicleListActivity.kt
    ├── vin_based_diagnosis/VINBasedDiagnosisActivity.kt
    ├── vin_based_flashing/VINBasedFlashingActivity.kt
    ├── select_ECU/SelectECUActivity.kt
    ├── selectoption/SelectOptionActivity.kt
    ├── raider_selection/RaiderSelectionActivity.kt
    │
    ├── ecu_diagnosis/ECUDiagnosisActivity.kt
    ├── read_DTCs/ReadDTCsActivity.kt
    ├── live_parameter/LiveParameterActivity.kt
    ├── live_data_recording/LiveDataRecordingActivity.kt
    ├── io_control/IOControlActivity.kt
    ├── routine_control/RoutineControlActivity.kt
    ├── iupr_test/
    │   ├── IUPRHistoryActivity.kt
    │   ├── IUPRTestPrimaryActivity.kt
    │   └── IUPRTestSecondaryActivity.kt
    ├── manual_diagnostic/ManualDiagnosticActivity.kt
    ├── gear_learning_procedure/GearLearningActivity.kt
    ├── data_watcher/DataWatcherActivity.kt
    ├── system_monitoring/SystemMonitoringActivity.kt
    ├── physical_evaluation/PhysicalEvaluationActivity.kt
    ├── write_data/WriteDataActivity.kt
    ├── gtsviews/GTSViewActivity.kt
    │
    ├── ecu_flashing/
    │   ├── ecu_flashing/
    │   │   ├── ECUFlashingActivity.kt
    │   │   └── SelectFlashVarientActivity.kt
    │   ├── new_ecu_flashing/NewECUFlashingActivity.kt
    │   ├── abs_flashing/
    │   │   ├── abs_flashing_conti/ABSFlashingContiActivity.kt
    │   │   ├── babs_flashing/BABSFlashActivity.kt
    │   │   ├── babs2_flashing/BABS2FlashActivity.kt
    │   │   └── kabs_flashing/KABSFlashActivity.kt
    │   ├── conti_flashing/
    │   │   ├── conti_flash/ContiFlashActivity.kt
    │   │   └── conti2_flash/Conti2FlashActivity.kt
    │   ├── inel_flashing/INELFlashActivity.kt
    │   ├── isg_flashing/
    │   │   ├── isg_flash/ISGFlashActivity.kt
    │   │   ├── isg_flash_jupiter/ISGFlashJupiterActivity.kt
    │   │   └── isg_flash_raider/ISGFlashRaiderActivity.kt
    │   ├── keihin_flashing/keihin_flash_sport/KeihinFlashSportActivity.kt
    │   ├── kems_flash/kems_flash_recovery/KEMSFlashRecoveryActivity.kt
    │   ├── keyless_ecu_flashing/KeylessECUFlashingActivity.kt
    │   ├── mikuni_flashing/
    │   │   ├── kems_flash/KEMSFlashActivity.kt
    │   │   └── mikuni_can_flash/MikuniCanFlashActivity.kt
    │   ├── pricol_flashing/
    │   │   ├── pricol_flash/PricolFlashActivity.kt
    │   │   ├── pricol_2_flash/Pricol2FlashActivity.kt
    │   │   ├── pricol_4_flash/Pricol4FlashActivity.kt
    │   │   ├── pricol_5_flash/Pricol5FlashActivity.kt
    │   │   ├── pricol_apache_flash/PricolApacheFlashActivity.kt
    │   │   ├── pricol_bto_flash/PricolBTOFlashActivity.kt
    │   │   ├── pricol_tpms_flash/PricolTPMSFlashActivity.kt
    │   │   ├── pricol_u400_flash/PricolU400FlashActivity.kt
    │   │   └── mid_variant_pricol2_flash/MidVariantPricol2FlashActivity.kt
    │   ├── sedemac_ems_flashing/
    │   │   ├── sedemac_ems_flashing/SEDEMAC_EMSFlashActivity.kt
    │   │   ├── sedemac_xl_100_obd2b_flash/SedemacXL100OBD2BFlashActivity.kt
    │   │   └── u558_sedemac_ems_flashing/U558SEDEMAC_EMSFlashActivity.kt
    │   ├── j125_cluster_flashing/J125ClusterFlashingActivity.kt
    │   ├── n597_cluster_flashing/N597_Cluster_FlashActivity.kt
    │   ├── u577_cluster_flashing/
    │   │   ├── u577_basic_cluster_flash/U577BasicClusterFlashActivity.kt
    │   │   └── u577_premium_cluster_flash/U577PremiumClusterFlashActivity.kt
    │   ├── u732_cluster_flashing/
    │   │   ├── u732_rlcd_cluster_flash/U732RLCDClusterFlashActivity.kt
    │   │   └── u732_tft_cluster_flash/U732TFTClusterFlashActivity.kt
    │   ├── u796_cluster_flashing/U796ClusterFlashActivity.kt
    │   └── ronin_flash_variant/RoninFlashvariantActivity.kt
    │
    ├── firmware_update/
    │   ├── techpro_firmware_update/FirmwareUpdateActivity.kt
    │   ├── tz_24v_firmware_update/TZ24vVCIFirmwareUpdateActivity.kt
    │   ├── tz_mini_vci_firmware_update/TZMiniVCIFirmwareUpdateActivity.kt
    │   ├── tz_new_vci_firmware_update/TZNewVCIFirmwareUpdateActivity.kt
    │   └── tz_vci_firmware_update/TZVCIFirmwareUpdateActivity.kt
    │
    ├── diagnostic_report/DiagnosticReportActivity.kt
    ├── report_summary_new/NewReportSummaryActivity.kt
    ├── vehicle_health_report/
    │   ├── VhrActivity.kt
    │   ├── VhrDealerInformationActivity.kt
    │   ├── VhrDiagnosticReportActivity.kt
    │   └── VhrIOControlActivity.kt
    │   # + fragments: fragment_vhr_dealer, fragment_vhr_diagnostic,
    │   #   fragment_vhr_io_control, fragment_vhr_summary (per resource names)
    ├── battery_health_report/BatteryHealthReportActivity.kt
    ├── log_viewer/LogViewerActivity.kt
    ├── file_viewer/FileViewerActivity.kt
    ├── servicemanual/ServiceManualActivity.kt
    ├── video_player/VideoPlayerActivity.kt
    │
    └── update/
        ├── UpdateActivity.kt
        └── update_description/UpdateDescriptionActivity.kt
```

## 3. Resource Tree — `app/src/main/res/` **(names confirmed via resources.arsc string table; file paths obfuscated in the shipped APK, shown here restored to conventional names)**

```
res/
├── layout/
│   ├── activity_login.xml, activity_home.xml, activity_main.xml, activity_splash.xml
│   ├── activity_add_device.xml, activity_ecu_diagnosis.xml, activity_ecu_flashing.xml
│   ├── activity_abs_flashing.xml, activity_babs_flash.xml, activity_basb2_flash.xml
│   │   (note: "basb2" typo preserved from original resource name)
│   ├── activity_conti_flash.xml, activity_conti2_flash.xml, activity_inel_flash.xml
│   ├── activity_isg_flashing.xml, activity_isg_jupiter_flash.xml, activity_isg_raider_flash.xml
│   ├── activity_kabs_flash.xml, activity_keihin_flash_sport.xml
│   ├── activity_kems2_flash.xml, activity_kems_recovery_flash.xml
│   ├── activity_keyless_ecu_flashing.xml, activity_mikuni_can_flash.xml
│   ├── activity_pricol_flash.xml, activity_pricol_2_flash.xml, activity_pricol_4_flash.xml,
│   │   activity_pricol5_flash.xml, activity_pricol_apache_flash.xml,
│   │   activity_pricol_bto_flash.xml, activity_pricol_tpms_flash.xml, activity_pricol_u400_flash.xml
│   ├── activity_j125_cluster_flashing.xml, activity_n597_cluster_flash.xml
│   ├── activity_new_ecu_flashing.xml, activity_firmwareupdate.xml
│   ├── activity_read_dtcs.xml, activity_live_parameter.xml, activity_live_data_recording.xml
│   ├── activity_io_control.xml, activity_manual_diagnostic.xml, activity_gear_learning.xml
│   ├── activity_iupr_history.xml, activity_iupr_test_primary.xml, activity_iupr_test_secondary.xml
│   ├── activity_diagnostic_report.xml, activity_new_report_summary.xml
│   ├── activity_battery_health_report.xml, activity_log_viewer.xml, activity_file_viewer.xml
│   ├── activity_dealer_information.xml, activity_account_details.xml
│   ├── activity_forgotpin.xml, activity_newpin.xml, activity_otp.xml
│   ├── activity_notification.xml, activity_data_watcher.xml, activity_gtsview.xml
│   ├── activity_physical_evaluation.xml, activity_raider_selection.xml
│   ├── activity_chat_bot.xml                    # in-app chatbot/support UI (not surfaced in manifest as a standalone Activity — likely embedded as a fragment/dialog)
│   ├── fragment_vhr_dealer.xml, fragment_vhr_diagnostic.xml,
│   │   fragment_vhr_io_control.xml, fragment_vhr_summary.xml
│   ├── fragment_one.xml, fragment_two.xml, fragment_three.xml   # generic tab/step fragments
│   ├── item_recycler_view.xml, item_row.xml, item_view_role_description.xml
│   ├── row_index_key.xml
│   ├── dialog_button.xml, dialog_erase_loader.xml, dialog_loader_overlay.xml,
│   │   dialog_message3.xml, dialog_message4.xml, dialog_message6.xml,
│   │   dialog_odometer.xml, dialog_retry_confirmation.xml
│   └── ... (remaining ~90+ layouts, one per Activity/screen, following the same naming convention)
│
├── menu/
│   ├── menu_img.xml
│   └── menu_lay.xml
│
├── drawable/ (+ drawable-hdpi/xhdpi/xxhdpi/xxxhdpi variants)
│   ├── ic_*.xml / ic_*.png            # ~66 icon assets (nav icons, status icons, ECU/flash iconography)
│   └── bg_*, selector/state-list drawables for buttons & cards
│
├── mipmap-*/                          # launcher icon densities
│
├── values/
│   ├── strings.xml
│   ├── colors.xml
│   ├── styles.xml / themes.xml
│   ├── dimens.xml                     # includes activity_horizontal_margin, etc.
│   └── attrs.xml
├── values-night/                      # dark theme overrides (Material3 dependency present)
├── color-v23/, color-v31/              # observed in extracted APK — dynamic/tonal color support
│
├── font/                               # custom font family (fontFamily/fontProvider entries present)
│
├── xml/
│   ├── file_paths.xml                 # FileProvider path config (matches manifest's fileprovider authority)
│   └── network_security_config.xml (typical, not directly confirmed)
│
└── raw/
    └── *.json (e.g. H2.json, KK.json, Oo.json, lw.json, sj.json — obfuscated names,
        likely Lottie animation files given json+drawable pairing common in onboarding/loading screens)
```

## 4. Assets Tree — `app/src/main/assets/` **(confirmed)**

```
assets/
├── flash_variant.json          # vehicle variant → ECU/flash-file mapping table
├── vcf-renesas_78k0r.s19        # Renesas 78K0R VCI dongle firmware (Motorola S-record)
├── PublicSuffixDatabase.list     # OkHttp dependency (public suffix list for cookie/domain handling)
└── dexopt/
    ├── baseline.prof              # AGP baseline profile (build artifact, not authored source)
    └── baseline.profm
```

## 5. Native Libraries — `app/src/main/jniLibs/` **(confirmed, standard AGP convention)**

```
jniLibs/
├── armeabi-v7a/libridescan_security.so
├── arm64-v8a/libridescan_security.so
├── x86/libridescan_security.so
└── x86_64/libridescan_security.so
```
*(inferred path — the shipped APK stores these under `lib/`, which is `jniLibs/` pre-build; the source likely also includes a `cpp/` or prebuilt-library submission from a separate native build, not part of this app module.)*

## 6. Bundled Third-Party Resource Sets (not app source — pulled in via dependencies) **(confirmed presence, standard packaging)**

```
com/itextpdf/...      # iTextPDF resource bundles (hyphenation dictionaries, CSS defaults, jsoup entities)
org/bouncycastle/...   # BouncyCastle certificate-path error message bundles
kotlin/....kotlin_builtins   # Kotlin stdlib reflection metadata
META-INF/
├── androidx/, com/, native-image/, services/     # dependency service-loader manifests
└── version-control-info.textproto                 # AGP-embedded git revision (e86ca92a8698c7d8f052099c4278bf69c0012b4a)
```

## 7. Build Metadata Observed

```
play-services-basement.properties     # version=18.4.0
play-services-location.properties     # version=21.3.0
```

---

**Summary of confidence levels:**
- **High confidence** (directly observed): package/class names, resource identifier names, asset files, native lib architectures, third-party library resource bundles, git revision hash.
- **Medium confidence** (standard convention, not directly observed): single-module Gradle layout, Gradle file names, `jniLibs/` vs. separate native module, exact `values/` file split.
- **Low confidence / labeled inferred**: file grouping within `ui/`, whether some "activity_*" layouts pair with Activities vs. embedded Fragments, raw `.json` files being Lottie animations.
