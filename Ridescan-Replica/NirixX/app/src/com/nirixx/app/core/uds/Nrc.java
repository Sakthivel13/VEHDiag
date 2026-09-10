package com.nirixx.app.core.uds;

/** ISO 14229 negative-response code table — technician-readable text.
 *  The UI must never show raw hex without this context. */
public final class Nrc {

    public final int code;
    public final String name;
    public final String userHint;

    private Nrc(int c, String n, String h) { code = c; name = n; userHint = h; }

    private static final Nrc[] TABLE = {
        new Nrc(0x10, "General Reject", "ECU refused the request. Retry; check ignition state."),
        new Nrc(0x11, "Service Not Supported", "This ECU does not implement the requested service."),
        new Nrc(0x12, "Sub-function Not Supported", "This ECU does not support that sub-function."),
        new Nrc(0x13, "Incorrect Message Length / Invalid Format", "Request malformed for this ECU — vehicle definition may differ."),
        new Nrc(0x14, "Response Too Long", "Response exceeds buffer. Report to support."),
        new Nrc(0x21, "Busy — Repeat Request", "ECU busy. Wait a moment and retry."),
        new Nrc(0x22, "Conditions Not Correct", "ECU is not ready for this operation. Verify ignition ON, engine state and vehicle conditions."),
        new Nrc(0x24, "Request Sequence Error", "Wrong sequence (e.g. key sent before seed). Restart the operation."),
        new Nrc(0x25, "No Response From Subnet Component", "A network component did not answer."),
        new Nrc(0x26, "Failure Prevents Execution", "An ECU failure prevents execution. Check DTCs first."),
        new Nrc(0x31, "Request Out Of Range", "The DID/routine/data is not valid for this ECU."),
        new Nrc(0x33, "Security Access Denied", "Security level not granted — run Security Access first."),
        new Nrc(0x35, "Invalid Key", "Security key rejected. Do not retry blindly — ECU counts attempts."),
        new Nrc(0x36, "Exceeded Number Of Attempts", "Security attempts exhausted. ECU is locked for a delay period."),
        new Nrc(0x37, "Required Time Delay Not Expired", "Security delay timer still running. Wait, then retry."),
        new Nrc(0x70, "Upload/Download Not Accepted", "ECU refused the transfer request."),
        new Nrc(0x71, "Transfer Data Suspended", "Data transfer suspended by ECU."),
        new Nrc(0x72, "General Programming Failure", "Programming failed. Do NOT power off; retry from the start."),
        new Nrc(0x73, "Wrong Block Sequence Counter", "Programming block sequence error — restart the transfer."),
        new Nrc(0x78, "Response Pending", "ECU is processing — keep waiting (P2*)."),
        new Nrc(0x7E, "Sub-function Not Supported In Active Session", "Not allowed in the current diagnostic session."),
        new Nrc(0x7F, "Service Not Supported In Active Session", "Open the correct diagnostic session first."),
        new Nrc(0x81, "RPM Too High", "Reduce RPM for this operation."),
        new Nrc(0x82, "RPM Too Low", "Raise RPM for this operation."),
        new Nrc(0x83, "Engine Is Running", "Stop the engine for this operation."),
        new Nrc(0x84, "Engine Is Not Running", "Start the engine for this operation."),
        new Nrc(0x85, "Engine Run Time Too Low", "Let the engine run longer first."),
        new Nrc(0x86, "Temperature Too High", "Wait for cool-down."),
        new Nrc(0x87, "Temperature Too Low", "Warm up first."),
        new Nrc(0x88, "Vehicle Speed Too High", "Stop the vehicle."),
        new Nrc(0x89, "Vehicle Speed Too Low", "Vehicle must be moving."),
        new Nrc(0x8A, "Throttle/Pedal Too High", "Release the throttle."),
        new Nrc(0x8B, "Throttle/Pedal Too Low", "Apply the throttle."),
        new Nrc(0x8C, "Transmission Range Not In Neutral", "Shift to neutral."),
        new Nrc(0x8D, "Transmission Range Not In Gear", "Shift into gear."),
        new Nrc(0x8F, "Brake Switch Not Closed", "Press the brake pedal."),
        new Nrc(0x90, "Shifter Lever Not In Park", "Shift to park."),
        new Nrc(0x91, "Torque Converter Clutch Locked", ""),
        new Nrc(0x92, "Voltage Too High", "Check charging system."),
        new Nrc(0x93, "Voltage Too Low", "Check battery — connect a charger."),
    };

    /** @return info for the NRC byte, or a synthesized "unknown" entry. */
    public static Nrc of(int code) {
        for (int i = 0; i < TABLE.length; i++) if (TABLE[i].code == code) return TABLE[i];
        return new Nrc(code, "Unknown NRC 0x" + Integer.toHexString(code).toUpperCase(),
                "Undocumented ECU refusal — check the vehicle diagnostic definition.");
    }
}
