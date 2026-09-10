package com.nirixx.app.core.role;

/** Role-based access control — enforced in the navigation layer (BaseActivity)
 *  and again inside privileged operations; never just hidden buttons.
 *
 *  Role names come from the roles table ("Dealer Engineer" / "Dealer Service"
 *  are the two contract roles from the project; the legacy four map onto them). */
public final class Roles {

    private Roles() {}

    // ---- modules (tiles + screens + operations) ---------------------------
    public static final String M_VIN_DIAG = "vin_diag";
    public static final String M_VEHICLES = "vehicles";
    public static final String M_DIAG_SECTION = "diag_section";      // Select ECU + tiles
    public static final String M_LIVE = "live";
    public static final String M_DTC = "dtc";
    public static final String M_IO = "io";
    public static final String M_ROUTINE = "routine";
    public static final String M_IUPR = "iupr";
    public static final String M_WRITE = "write_did";                // engineer only
    public static final String M_FLASH = "flash";                    // engineer only
    public static final String M_VIN_FLASH = "vin_flash";            // engineer only
    public static final String M_CAMPAIGN = "campaign";              // engineer only
    public static final String M_VHR = "vhr";
    public static final String M_REPORTS = "reports";
    public static final String M_BATTERY = "battery";
    public static final String M_RECORDING = "recording";
    public static final String M_VCI = "vci";
    public static final String M_VCI_FW = "vci_fw";
    public static final String M_MANUAL = "service_manual";
    public static final String M_LOGS = "logs";
    public static final String M_AI = "ai_assistant";
    public static final String M_SYSCHECK = "system_check";
    public static final String M_UPDATE = "app_update";
    public static final String M_SCREEN_REC = "screen_record";
    public static final String M_VIDEOS = "videos";                      // intro/training media

    public static final String ROLE_ENGINEER = "Dealer Engineer";
    public static final String ROLE_SERVICE = "Dealer Service";

    /** Dealer Service module set (contract): connect, identify, diagnose. */
    private static final String[] SERVICE = {
        M_VIN_DIAG, M_VEHICLES, M_DIAG_SECTION, M_LIVE, M_DTC, M_IO, M_ROUTINE,
        M_IUPR, M_VCI, M_VIDEOS,
    };

    /** Technician/Advisor: service set + reports. */
    private static final String[] TECH_EXTRA = { M_VHR, M_REPORTS, M_BATTERY, M_RECORDING, M_LOGS };

    public static boolean isEngineer(String role) {
        return ROLE_ENGINEER.equals(role) || "Service Manager".equals(role)
                || "Administrator".equals(role);
    }

    public static boolean can(String role, String module) {
        if (module == null) return true;                       // ungated screen
        if (isEngineer(role)) return true;
        if (ROLE_SERVICE.equals(role) || role == null) return contains(SERVICE, module);
        if ("Service Technician".equals(role) || "Service Advisor".equals(role))
            return contains(SERVICE, module) || contains(TECH_EXTRA, module);
        return contains(SERVICE, module);                      // unknown role -> least privilege
    }

    private static boolean contains(String[] arr, String m) {
        for (int i = 0; i < arr.length; i++) if (arr[i].equals(m)) return true;
        return false;
    }

    /** Simple-name → module map used by the BaseActivity navigation guard. */
    public static String moduleForScreen(String simpleName) {
        if ("VinDiagnosisActivity".equals(simpleName)) return M_VIN_DIAG;
        if ("VinFlashingActivity".equals(simpleName)) return M_VIN_FLASH;
        if ("VehicleListActivity".equals(simpleName)) return M_VEHICLES;
        if ("SelectECUActivity".equals(simpleName)
                || "ECUDiagnosisActivity".equals(simpleName)) return M_DIAG_SECTION;
        if ("LiveParameterActivity".equals(simpleName)) return M_LIVE;
        if ("ReadDTCsActivity".equals(simpleName)) return M_DTC;
        if ("IOControlActivity".equals(simpleName)) return M_IO;
        if ("RoutineControlActivity".equals(simpleName)) return M_ROUTINE;
        if ("IuprTestActivity".equals(simpleName)) return M_IUPR;
        if ("WriteDataActivity".equals(simpleName)) return M_WRITE;
        if ("FlashActivity".equals(simpleName)
                || "SelectFlashVariantActivity".equals(simpleName)
                || "SupplierFlashListActivity".equals(simpleName)
                || "SupplierFlashActivity".equals(simpleName)
                || "ClusterFlashListActivity".equals(simpleName)) return M_FLASH;
        if ("VhrActivity".equals(simpleName)) return M_VHR;
        if ("ReportsActivity".equals(simpleName)
                || "DiagnosticReportActivity".equals(simpleName)
                || "PhysicalEvaluationActivity".equals(simpleName)
                || "DealerInformationActivity".equals(simpleName)
                || "DataWatcherActivity".equals(simpleName)) return M_REPORTS;
        if ("BatteryHealthActivity".equals(simpleName)
                || "GearLearningActivity".equals(simpleName)) return M_BATTERY;
        if ("LiveDataRecordingActivity".equals(simpleName)) return M_RECORDING;
        if ("AddDeviceActivity".equals(simpleName)) return M_VCI;
        if ("VciFirmwareListActivity".equals(simpleName)
                || "FirmwareUpdateActivity".equals(simpleName)) return M_VCI_FW;
        if ("ServiceManualActivity".equals(simpleName)) return M_MANUAL;
        if ("IntroVideosActivity".equals(simpleName)) return M_VIDEOS;
        if ("LogViewerActivity".equals(simpleName)
                || "FileViewerActivity".equals(simpleName)) return M_LOGS;
        if ("SupportChatActivity".equals(simpleName)) return M_AI;
        if ("SystemCheckActivity".equals(simpleName)
                || "SystemMonitoringActivity".equals(simpleName)) return M_SYSCHECK;
        if ("UpdateActivity".equals(simpleName)
                || "UpdateDescriptionActivity".equals(simpleName)) return M_UPDATE;
        if ("ManualDiagnosticActivity".equals(simpleName)) return M_VIN_FLASH;
        return null;                                            // ungated
    }
}
