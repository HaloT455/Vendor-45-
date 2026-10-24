import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

/**
 * Root app_process bridge for an explicit SubscriptionManagerService DDS handoff.
 *
 * Does NOT use fragile Binder transaction numbers, write global Settings,
 * disable either physical SIM, or touch CP/EFS. It uses reflection only because
 * ISub/ServiceManager are hidden Android platform APIs.
 *
 * Compiled dex is meant to run ON the connected S8+ Android16 via app_process.
 * "status" is read only, "set 2" explicitly changes default mobile data to
 * MobiFone (owner's current mapping), "set 1" restores Viettel.
 */
public final class AliceDataSimSwitch {
    private static final int SLOT0_SUB = 1;
    private static final int SLOT1_SUB = 2;

    private static Object call(Class<?> api, Object instance, String method,
                               Class<?>[] types, Object... args) throws Exception {
        try {
            Method target = api.getMethod(method, types);
            return target.invoke(instance, args);
        } catch (InvocationTargetException exception) {
            Throwable cause = exception.getCause();
            if (cause instanceof SecurityException) {
                throw new SecurityException("Telephony rejected caller permission: " +
                        cause.getMessage(), cause);
            }
            throw new IllegalStateException("ISub." + method + " rejected request: " +
                    cause, cause);
        }
    }

    private static int readInt(Class<?> api, Object obj, String method,
                               Class<?>[] argTypes, Object... params) throws Exception {
        return ((Number) call(api, obj, method, argTypes, params)).intValue();
    }

    private static void usage() {
        System.err.println("USAGE: AliceDataSimSwitch status | set 2 | set 1");
        System.err.println("  status = read only; set 2 = MobiFone, set 1 = Viettel.");
        System.err.println("  Requires Android root WITH MODIFY_PHONE_STATE access.");
    }

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            usage();
            System.exit(2);
            return;
        }
        boolean status = args.length == 1 && args[0].equals("status");
        boolean setting = args.length == 2 && args[0].equals("set") &&
                (args[1].equals("1") || args[1].equals("2"));
        if (!status && !setting) {
            usage();
            System.exit(2);
            return;
        }

        Class<?> serviceManager = Class.forName("android.os.ServiceManager");
        Object binder = serviceManager
                .getMethod("getService", String.class).invoke(null, "isub");
        if (binder == null) {
            throw new IllegalStateException("Android service 'isub' unavailable");
        }
        Class<?> binderClass = Class.forName("android.os.IBinder");
        Class<?> stub = Class.forName("com.android.internal.telephony.ISub$Stub");
        Object isub = stub.getMethod("asInterface", binderClass).invoke(null, binder);
        if (isub == null) {
            throw new IllegalStateException("ISub.Stub.asInterface returned null");
        }
        Class<?> api = Class.forName("com.android.internal.telephony.ISub");
        int phone0 = readInt(api, isub, "getPhoneId",
                new Class<?>[]{int.class}, SLOT0_SUB);
        int phone1 = readInt(api, isub, "getPhoneId",
                new Class<?>[]{int.class}, SLOT1_SUB);
        int before = readInt(api, isub, "getDefaultDataSubId",
                new Class<?>[0]);

        System.out.println("ALICE_DATA_SIM: Viettel subId=1 phoneId=" + phone0
                + "; MobiFone subId=2 phoneId=" + phone1
                + "; defaultDataSubId=" + before);

        // Refuse ANY write if SIMs were swapped, removed or reassigned since
        // the owner's known-good dual-SIM baseline was captured.
        if (phone0 != 0 || phone1 != 1) {
            throw new IllegalStateException("Slot/subId mapping unexpected; refusing data SIM change");
        }
        if (!setting) {
            System.out.println("ALICE_DATA_SIM_STATUS_ONLY: no modem/settings modifications");
            return;
        }
        int targetSub = Integer.parseInt(args[1]);
        if (before != 1 && before != 2) {
            throw new IllegalStateException("Unexpected previous data subscription " + before
                    + "; refusing write");
        }
        if (before == targetSub) {
            System.out.println("ALICE_DATA_SIM_ALREADY_SELECTED: subId=" + targetSub);
            return;
        }

        // Android16 AOSP SubscriptionManagerService.setDefaultDataSubId calls
        // remapRafIfApplicable + MultiSimSettingController notifications.
        // The vendor may still deny a root process in SELinux/permissions.
        System.out.println("ALICE_DATA_SIM_REQUEST: " + before + " -> " + targetSub);
        call(api, isub, "setDefaultDataSubId",
                new Class<?>[]{int.class}, targetSub);
        int after = readInt(api, isub, "getDefaultDataSubId",
                new Class<?>[0]);
        System.out.println("ALICE_DATA_SIM_READBACK: " + after);
        if (after != targetSub) {
            throw new IllegalStateException("Data subscription did not change; do not claim LTE handoff");
        }
        System.out.println("ALICE_DATA_SIM_DDS_APPLIED: radio/network registration not yet verified");
    }
}
