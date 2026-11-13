#!/usr/bin/env python3
"""Verify the still template changes only an existing, advertised ZSL key."""

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "android").mkdir()
        (work / "android/log.h").write_text(
            "#define ANDROID_LOG_ERROR 6\n#define ANDROID_LOG_INFO 4\n"
            "int __android_log_print(int, const char *, const char *, ...);\n"
        )
        source = work / "test.c"
        source.write_text(r'''
#include <assert.h>
#include "tools/native_camera/alice_preview_bridge.c"

struct camera_metadata {
    uint8_t capabilities[1];
    int32_t keys[1];
    uint8_t values[5];
    uint32_t missing;
};
static unsigned clones, frees;

int __android_log_print(int priority, const char *tag, const char *format, ...)
{
    (void)priority;
    (void)tag;
    (void)format;
    return 0;
}

static int lookup(const camera_metadata_t *metadata, uint32_t tag,
                  camera_metadata_ro_entry_t *entry)
{
    static const uint32_t tags[] = { AOSP_CONTROL_CAPTURE_INTENT, AOSP_CONTROL_MODE,
        AOSP_CONTROL_AE_MODE, AOSP_FLASH_MODE, AOSP_CONTROL_ENABLE_ZSL };
    if (metadata->missing == tag) return -1;
    entry->count = 1;
    entry->type = TYPE_BYTE;
    if (tag == AOSP_AVAILABLE_CAPABILITIES) {
        entry->data.u8 = metadata->capabilities;
        return 0;
    }
    if (tag == AOSP_AVAILABLE_REQUEST_KEYS) {
        entry->data.i32 = metadata->keys;
        entry->type = TYPE_INT32;
        return 0;
    }
    for (size_t i = 0; i < sizeof(tags) / sizeof(tags[0]); ++i) {
        if (tag != tags[i]) continue;
        entry->index = i;
        entry->data.u8 = &metadata->values[i];
        return 0;
    }
    return -1;
}

static camera_metadata_t *clone_metadata(const camera_metadata_t *original)
{
    camera_metadata_t *copy = malloc(sizeof(*copy));
    assert(copy);
    *copy = *original;
    ++clones;
    return copy;
}

static int update_byte(camera_metadata_t *copy, size_t index, const void *value,
                       size_t count, struct camera_metadata_entry *entry)
{
    assert(count == 1 && entry == NULL && index == 4);
    copy->values[index] = *(const uint8_t *)value;
    return 0;
}

static void release_metadata(camera_metadata_t *metadata)
{
    ++frees;
    free(metadata);
}

int main(void)
{
    camera_metadata_t original = {
        .capabilities = { CAPABILITY_PRIVATE_REPROCESSING },
        .keys = { AOSP_CONTROL_ENABLE_ZSL },
        .values = { STILL_CAPTURE_INTENT, CONTROL_AUTO, AE_MODE_ON, FLASH_MODE_OFF, 0 },
    };
    assert(supports_still_zsl(lookup, &original));
    original.capabilities[0] = CAPABILITY_YUV_REPROCESSING;
    assert(supports_still_zsl(lookup, &original));
    original.capabilities[0] = 0;
    assert(!supports_still_zsl(lookup, &original));
    original.capabilities[0] = CAPABILITY_PRIVATE_REPROCESSING;
    original.keys[0] = AOSP_CONTROL_AE_MODE;
    assert(!supports_still_zsl(lookup, &original));
    original.keys[0] = AOSP_CONTROL_ENABLE_ZSL;

    camera_metadata_t *fast =
        fast_still_template(&original, lookup, clone_metadata, update_byte, release_metadata);
    assert(fast && fast->values[4] == 1 && original.values[4] == 0);
    assert(!memcmp(original.values, fast->values, 4));
    release_metadata(fast);
    assert(clones == 1 && frees == 1);
    for (size_t i = 0; i < 5; ++i) {
        camera_metadata_t different = original;
        different.values[i] = 3;
        assert(!fast_still_template(&different, lookup, clone_metadata,
                                    update_byte, release_metadata));
    }
    original.missing = AOSP_CONTROL_ENABLE_ZSL;
    assert(!fast_still_template(&original, lookup, clone_metadata,
                                update_byte, release_metadata));
    assert(clones == 1 && frees == 1);
    return 0;
}
''')
        output = work / "test"
        subprocess.run(
            [os.environ.get("CC", "cc"), "-Wall", "-Wextra", "-Werror", "-I", work,
             "-I", ROOT, source, "-ldl", "-pthread", "-o", output],
            check=True,
        )
        subprocess.run([output], check=True)
        print("Still ZSL template capability, fallback and metadata tests passed")


if __name__ == "__main__":
    main()
