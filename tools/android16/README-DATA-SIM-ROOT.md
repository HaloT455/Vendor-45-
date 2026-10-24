# ALICE S8+ Android16 — real data subscription switching via rooted ISub

**Status: source + build workflow committed; NOT validated on user's device, NOT a Dual LTE fix.**

**Target device only:** Samsung Galaxy S8+ Exynos8895, \`dream2lte\`, Android 16, KernelSU. User's verified mapping: slot0/Viettel=subId1, slot1/MobiFone=subId2; baseline default/active data subId1, Viettel PS WWAN HOME LTE and MobiFone CS WWAN HOME UMTS. This is a single DATA-SIM handoff test, **not** an attempt to turn LTE into two concurrent 4G stacks.

Verified AOSP Android16 \`SubscriptionManagerService.setDefaultDataSubId(int)\` invokes \`remapRafIfApplicable()\` and \`MultiSimSettingController.notifyDefaultDataSubChanged()\`. Native service interface method is \`ISub.setDefaultDataSubId(int)\`: https://android.googlesource.com/platform/frameworks/opt/telephony/+/android16-release/src/java/com/android/internal/telephony/subscription/SubscriptionManagerService.java

## Building once on Linux (requires Java JDK + Android SDK Build-Tools d8)

\`\`\`sh
mkdir -p "$HOME/Downloads/ALICE_DDS/tools/android16"
cd "$HOME/Downloads/ALICE_DDS"
BASE="https://raw.githubusercontent.com/HaloT455/Vendor-45-/work/a16-sim2-lte-ab-20261023/tools/android16"
curl -fL "$BASE/AliceDataSimSwitch.java" -o tools/android16/AliceDataSimSwitch.java
curl -fL "$BASE/build_alice_data_sim_switch.sh" -o tools/android16/build_alice_data_sim_switch.sh
bash tools/android16/build_alice_data_sim_switch.sh "$PWD/alice-data-sim-switch.jar"
\`\`\`

No Android SDK locally? Open the GitHub Actions workflow \`alice-a16-root-data-sim-helper.yml\` to find an artifact named \`ALICE-S8Plus-Android16-ISub-RootHelper-UNTESTED\` when and only when its build passes. The artifact is a ZIP containing \`alice-data-sim-switch.jar\` and SHA256. **Verify its contents and keep provenance.** Do not assume that the action ran or passed merely because this workflow exists.

## Run READ-ONLY before changing anything

\`\`\`sh
adb -d push alice-data-sim-switch.jar /data/local/tmp/alice-data-sim-switch.jar
adb -d shell 'su -c "CLASSPATH=/data/local/tmp/alice-data-sim-switch.jar app_process /system/bin AliceDataSimSwitch status"'
\`\`\`

Required status before trying \`set 2\`:
\`\`\`text
ALICE_DATA_SIM: Viettel subId=1 phoneId=0; MobiFone subId=2 phoneId=1; defaultDataSubId=1
ALICE_DATA_SIM_STATUS_ONLY: no modem/settings modifications
\`\`\`
If class cannot load, hidden API restrictions deny access, \`SecurityException\`, no \`isub\` service, or slot map different, **STOP**. Do not use guessed \`service call isub\` transaction IDs and do not edit \`multi_sim_data_call\` by hand.

## Intentional, reversible data-SIM handoff (ONLY after status is correct)

\`\`\`sh
adb -d shell 'su -c "CLASSPATH=/data/local/tmp/alice-data-sim-switch.jar app_process /system/bin AliceDataSimSwitch set 2"'
adb -d shell dumpsys isub | grep -E 'defaultDataSubId=|activeDataSubId='
adb -d shell dumpsys telephony.registry | grep -iE 'mServiceState=|NetworkRegistrationInfo'
\`\`\`
Network may briefly disconnect. \`defaultDataSubId=2\` confirms accepted configuration; \`activeDataSubId=2\` may lag because network handoff is asynchronous. Check the SIM 2 \`PS WWAN\` accessNetworkTechnology and registrationState, not \`gsm.network.type\` (IWLAN on WLAN is not LTE on cellular).

To restore Viettel data when needed:
\`\`\`sh
adb -d shell 'su -c "CLASSPATH=/data/local/tmp/alice-data-sim-switch.jar app_process /system/bin AliceDataSimSwitch set 1"'
adb -d shell dumpsys isub | grep -E 'defaultDataSubId=|activeDataSubId='
\`\`\`

These source files do not modify modem firmware, EFS, boot, vendor, either SIM's enable status, or APN. Permission/SELinux restrictions may block root process despite uid=0; a denial is diagnostic, not a reason to disable SELinux. The \`Phone.java\` RAF0 source compatibility trial is independently default OFF and not installed into the ROM.
