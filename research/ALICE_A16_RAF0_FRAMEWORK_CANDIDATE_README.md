# ALICE Android16 / Samsung Exynos8895 — RAF=0 fallback research

**STATUS: SOURCE-LEVEL CANDIDATE ONLY. NEVER FLASH THIS BRANCH AS A VENDOR FIX.**

## Verified on the user's S8+ (2026-10-20)

- Both SIMs loaded under DSDS; `ro.telephony.default_network=9,9`.
- Android vendor RRO is **enabled** and `cmd overlay lookup` returns `GSM|CDMA|EVDO|WCDMA|LTE` for framework `config_radio_access_family`.
- Telephony radio logs contain **8 `setPreferredNetworkType: Abort, unknown RAF: 0` lines** at 11:37:10–11:37:15. These are historical and **not yet attributed to either SIM**.
- SIM1 registration is denied (UMTS); SIM2 registered (UMTS/HSPA+). **LTE never confirmed**.
- The 8 RAF aborts prove that the framework had no valid cached modem RAF at the time of those calls; they do not prove the proprietary Samsung modem's physical capabilities or why its cache was zero.

## Implementation hypothesis and exact scope

The upstream LineageOS Android16 HIDL RadioResponse uses a static RadioCapability fallback when `getRadioCapabilityResponse` returns `REQUEST_NOT_SUPPORTED` or `GENERIC_FAILURE`. A success response whose `RadioCapability.raf == 0` is normally delivered without fallback. That could leave `Phone.getRadioAccessFamily()` equal to `RAF_UNKNOWN` and block `updateAllowedNetworkTypes`.

Candidate patch: `research/patches/0001-radioresponse-raf0-success-fallback-RESEARCH.patch`
- Target: `frameworks/opt/telephony/src/java/com/android/internal/telephony/RadioResponse.java` from LineageOS Android16 `lineage-23.2`.
- Only for **successful GET_RADIO_CAPABILITY responses whose converted RAF is UNKNOWN (0)**.
- Take an existing `RIL.makeStaticRadioCapability()` fallback **only if its RAF is nonzero**.
- Leave valid vendor RAF, other radio response errors, and HIDL request/response ownership unchanged.
- Does **not** alter `libsec-ril.so`, kernel, `vendor.img`, CP firmware, NV or EFS, `9,9`, or the known-good Camera+Video6 vendor.
- Does **not** add a second RAF overlay: the Android framework is confirmed already using the original vendor overlay.
- Cannot prove the Samsung HAL returns `SUCCESS + RAF=0`; that remains a **hypothesis**, not a demonstrated cause.

## Offline validation

`.github/workflows/alice-a16-raf0-framework-candidate.yml` fetches one pinned LineageOS Android16 `RadioResponse.java` source file (revision `a6e94555e0d750e4557f5371811b776637ab7c50`), applies the candidate patch and executes isolated Java tests of the **actual patched method**:
- Valid modem LTE RAF untouched.
- `SUCCESS, RAF0` uses valid static fallback.
- `SUCCESS, RAF0` with `UNKNOWN` static fallback remains UNKNOWN.
- Existing `REQUEST_NOT_SUPPORTED` and `GENERIC_FAILURE` behavior maintained.
- Other radio errors are not hidden by the new fallback.

This is **not** a full Android system build. It does not establish compatibility with the user's specific proprietary One UI 8 system, active RIL callback data, or mobile network.

## Requirements before any device image or vendor-system integration

1. Capture the exact live HIDL `getRadioCapabilityResponse` status and `rc.raf` on each slot, ideally at radio startup. Do not log/upload raw SIM identifiers.
2. Identify actual Android16 Telephony source and system build for user's One UI 8 ROM; a LineageOS source patch is not automatically compatible with Samsung framework binary.
3. Integrate with an isolated **system/framework** source branch and compile/tests; vendor-only property or a new RRO is the wrong level if `SUCCESS+RAF0` is confirmed.
4. Keep original Camera+Video6 vendor bit-for-bit unchanged and verify rollback path. Test actual LTE attach for one SIM before any claim of dual 4G support.

This research branch is not flash-ready and deliberately produces no flashable output.
