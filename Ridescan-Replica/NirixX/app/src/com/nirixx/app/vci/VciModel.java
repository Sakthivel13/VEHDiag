package com.nirixx.app.vci;

/** The NirixiLINK hardware family NirixX talks to.  Only real interface
 *  variants exist: Bluetooth, Wi-Fi and USB — no imaginary catalogues. */
public class VciModel {

    public final String name;
    public final String linkType;   // "BT Classic + BLE" | "Wi-Fi" | "USB OTG"
    public final String drawable;   // drawable resource name for the icon
    public final String blurb;
    public final String firmware;
    public final boolean thirdParty;

    public VciModel(String name, String linkType, String drawable, String blurb, String firmware, boolean thirdParty) {
        this.name = name;
        this.linkType = linkType;
        this.drawable = drawable;
        this.blurb = blurb;
        this.firmware = firmware;
        this.thirdParty = thirdParty;
    }

    public static VciModel[] all() {
        return new VciModel[]{
            new VciModel("NirixiLINK (Bluetooth)", "BT Classic + BLE", "vci",
                "Service VCI dongle over Bluetooth SPP/BLE. Full UDS on 7E0/7E8 plus K-line.", "1.07", false),
            new VciModel("NirixiLINK (Wi-Fi)", "Wi-Fi", "vci",
                "Same VCI broadcasting its NirixiLINK_xxxxxx hotspot for phone-to-dongle Wi-Fi.", "1.07", false),
            new VciModel("NirixiLINK (USB)", "USB OTG", "vci",
                "Wired USB link through an OTG cable for flashing-sensitive sessions.", "1.07", false),
        };
    }

    /** Models surfaced by the pairing scanner's (simulated) radio.
     *  Serials mirror the real devices seen in the reference session logs. */
    public static String[][] discoveredPool() {
        return new String[][]{
            {"NirixiLINK_504856", "NirixiLINK (Bluetooth)", "BT Classic + BLE", "vci"},
            {"NirixiLINK_502808", "NirixiLINK (Bluetooth)", "BLE", "vci"},
            {"NirixiLINK_502809", "NirixiLINK (Wi-Fi)", "Wi-Fi", "vci"},
        };
    }
}
