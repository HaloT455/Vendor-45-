/*
 * ALICE Exynos8895 Samsung Camera metadata compatibility experiment.
 * Derived from documented AOSP camera_module_t ABI, not S9+ ARM opcodes.
 * Keeps the pinned UN1GAGA wrapper as delegate; adds Samsung preview, still-picture and video metadata tags.
 * Native code never touches CP, EFS or existing Samsung Camera APK.
 *
 * EXPERIMENTAL: API + ELF CI validation != safe to flash / working camera.
 */
#include <android/log.h>
#include <dlfcn.h>
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define LOG(...) __android_log_print(ANDROID_LOG_ERROR,"ALICE_CameraPreview",__VA_ARGS__)
#define PREVIEW_TAG 0x80030000u
#define PICTURE_TAG 0x80030001u
#define VIDEO_TAG 0x80030002u
#define AOSP_STREAM_CONFIGS 0x000d000au
#define AOSP_MIN_FRAME_DURATIONS 0x000d000bu
#define AOSP_AE_FPS_RANGES 0x00010014u
#define TYPE_INT32 1
#define TYPE_INT64 3
#define VIDEO_FPS 30
/* Real Samsung Exynos HAL emits 6-int video tuples: w,h,minFps,maxFps,crop,timeLimit.
 * Never use [pixelFormat,width,height,direction] here. Source:
 * ExynosCameraMetadataConverterVendor::m_createVendorControlAvailableVideoConfigurations */
#define VIDEO_FIELDS 6
#define FMT_IMPLEMENTATION_DEFINED 34
#define FMT_BLOB 33
#define OUTPUT 0
#define MAX_CAMERAS 8
#define MAX_SIZE_TUPLES 128

typedef struct camera_metadata camera_metadata_t;
struct hw_module;
struct hw_device;
typedef struct hw_module hw_module_t;
typedef struct hw_device hw_device_t;
typedef struct hw_module_methods {
    int (*open)(const hw_module_t *,const char *,hw_device_t **);
} hw_module_methods_t;
struct hw_module {
    uint32_t tag;
    uint16_t module_api_version;
    uint16_t hal_api_version;
    const char *id, *name, *author;
    hw_module_methods_t *methods;
    void *dso;
#ifdef __LP64__
    uint64_t reserved[25];
#else
    uint32_t reserved[25];
#endif
};
typedef struct camera_info {
    int facing, orientation;
    uint32_t device_version;
    const camera_metadata_t *static_camera_characteristics;
    int resource_cost;
    char **conflicting_devices;
    size_t conflicting_devices_length;
} camera_info_t;
typedef struct vendor_tag_ops vendor_tag_ops_t;
struct vendor_tag_ops {
    int (*get_tag_count)(const vendor_tag_ops_t *);
    void (*get_all_tags)(const vendor_tag_ops_t *,uint32_t *);
    const char *(*get_section_name)(const vendor_tag_ops_t *,uint32_t);
    const char *(*get_tag_name)(const vendor_tag_ops_t *,uint32_t);
    int (*get_tag_type)(const vendor_tag_ops_t *,uint32_t);
    void *reserved[8];
};
typedef struct camera_module {
    hw_module_t common;
    int (*get_number_of_cameras)(void);
    int (*get_camera_info)(int,camera_info_t *);
    int (*set_callbacks)(const void *);
    void (*get_vendor_tag_ops)(vendor_tag_ops_t *);
    int (*open_legacy)(const hw_module_t *,const char *,uint32_t,hw_device_t **);
    int (*set_torch_mode)(const char *,bool);
    int (*init)(void);
    void *reserved[5];
} camera_module_t;
typedef struct camera_metadata_ro_entry {
    size_t index;
    uint32_t tag;
    uint8_t type;
    size_t count;
    union {
        const uint8_t *u8;
        const int32_t *i32;
        const float *f;
        const int64_t *i64;
        const double *d;
        const void *ptr;
    } data;
} camera_metadata_ro_entry_t;

typedef size_t (*count_fn)(const camera_metadata_t *);
typedef int (*find_fn)(const camera_metadata_t *,uint32_t,camera_metadata_ro_entry_t *);
typedef camera_metadata_t *(*alloc_fn)(size_t,size_t);
typedef int (*append_fn)(camera_metadata_t *,const camera_metadata_t *);
typedef int (*add_fn)(camera_metadata_t *,uint32_t,const void *,size_t);
typedef int (*sort_fn)(camera_metadata_t *);
typedef int (*set_ops_fn)(const vendor_tag_ops_t *);
typedef uint64_t (*get_vendor_id_fn)(const camera_metadata_t *);
typedef void (*set_vendor_id_fn)(camera_metadata_t *,uint64_t);
typedef void (*free_fn)(camera_metadata_t *);

static camera_module_t *delegate;
static hw_module_methods_t delegated_methods;
static vendor_tag_ops_t legacy_ops;
static vendor_tag_ops_t merged_ops;
static camera_metadata_t *static_metadata[MAX_CAMERAS];
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static void *metadata_handle;

__attribute__((visibility("default")))
camera_module_t HMI = {
    .common = {
        .tag = 0x48574d54,
        .module_api_version = 0x204,
        .hal_api_version = 0,
        .id = "camera",
        .name = "ALICE preview metadata bridge (UN1GAGA delegate)",
        .author = "ALICE experiment"
    }
};

static int tag_count(const vendor_tag_ops_t *ops) {
    (void)ops;
    int old = legacy_ops.get_tag_count ?
        legacy_ops.get_tag_count(&legacy_ops) : 0;
    return old >= 0 && old < 4094 ? old + 3 : -1;
}
static void all_tags(const vendor_tag_ops_t *ops,uint32_t *tags) {
    (void)ops;
    if (!tags) return;
    int old = legacy_ops.get_tag_count ?
        legacy_ops.get_tag_count(&legacy_ops) : 0;
    if (old < 0 || old >= 4094) return;
    if (old && legacy_ops.get_all_tags)
        legacy_ops.get_all_tags(&legacy_ops,tags);
    tags[old] = PREVIEW_TAG;
    tags[old+1] = PICTURE_TAG;
    tags[old+2] = VIDEO_TAG;
}
static const char *section_name(const vendor_tag_ops_t *ops,uint32_t tag) {
    (void)ops;
    if (tag == PREVIEW_TAG || tag == PICTURE_TAG || tag == VIDEO_TAG) return "samsung.android.scaler";
    return legacy_ops.get_section_name ?
        legacy_ops.get_section_name(&legacy_ops,tag) : NULL;
}
static const char *tag_name(const vendor_tag_ops_t *ops,uint32_t tag) {
    (void)ops;
    if (tag == PREVIEW_TAG) return "availablePreviewStreamConfigurations";
    if (tag == PICTURE_TAG) return "availablePictureStreamConfigurations";
    if (tag == VIDEO_TAG) return "availableVideoConfigurations";
    return legacy_ops.get_tag_name ?
        legacy_ops.get_tag_name(&legacy_ops,tag) : NULL;
}
static int tag_type(const vendor_tag_ops_t *ops,uint32_t tag) {
    (void)ops;
    if (tag == PREVIEW_TAG || tag == PICTURE_TAG || tag == VIDEO_TAG) return 1; /* TYPE_INT32 */
    return legacy_ops.get_tag_type ?
        legacy_ops.get_tag_type(&legacy_ops,tag) : -1;
}

static bool prepare_ops(void) {
    if (!delegate || !delegate->get_vendor_tag_ops) return false;
    if (merged_ops.get_tag_count) return true;
    memset(&legacy_ops,0,sizeof(legacy_ops));
    delegate->get_vendor_tag_ops(&legacy_ops);
    int count=legacy_ops.get_tag_count ?
        legacy_ops.get_tag_count(&legacy_ops) : -1;
    if (count < 0 || count > 256 || !legacy_ops.get_all_tags ||
        !legacy_ops.get_section_name || !legacy_ops.get_tag_name ||
        !legacy_ops.get_tag_type) {
        LOG("Reject missing/invalid original Samsung vendor ops");
        return false;
    }
    uint32_t tags[256]={0};
    legacy_ops.get_all_tags(&legacy_ops,tags);
    for (int i=0;i<count;i++) {
        if (tags[i]==PREVIEW_TAG || tags[i]==PICTURE_TAG || tags[i]==VIDEO_TAG) {
            LOG("Synthetic Samsung scaler tag collides with stock vendor tag; disabled");
            return false;
        }
    }
    merged_ops = legacy_ops; /* preserve original ABI/reserved */
    merged_ops.get_tag_count = tag_count;
    merged_ops.get_all_tags = all_tags;
    merged_ops.get_section_name = section_name;
    merged_ops.get_tag_name = tag_name;
    merged_ops.get_tag_type = tag_type;
    return true;
}
static void wrapped_get_vendor_tag_ops(vendor_tag_ops_t *ops) {
    if (!ops) return;
    pthread_mutex_lock(&mu);
    bool ok=prepare_ops();
    if (ok) *ops=merged_ops;
    pthread_mutex_unlock(&mu);
    if (!ok && delegate && delegate->get_vendor_tag_ops)
        delegate->get_vendor_tag_ops(ops);
}
static int wrapped_open(const hw_module_t *ignored,const char *id,hw_device_t **device) {
    (void)ignored;
    if (!delegate || !delegate->common.methods ||
        !delegate->common.methods->open) return -ENODEV;
    return delegate->common.methods->open(&delegate->common,id,device);
}
static int wrapped_open_legacy(const hw_module_t *ignored,const char *id,
                               uint32_t version,hw_device_t **device) {
    (void)ignored;
    if (!delegate || !delegate->open_legacy) return -ENOSYS;
    return delegate->open_legacy(&delegate->common,id,version,device);
}

/* 1440x1080 exists in the real S8+ metadata; never invent unsupported sizes. */
static camera_metadata_t *augment(const camera_metadata_t *original) {
    if (!original) return NULL;
    if (!metadata_handle)
        metadata_handle=dlopen("libcamera_metadata.so",RTLD_NOW|RTLD_LOCAL);
    if (!metadata_handle) {LOG("Camera metadata library unavailable");return NULL;}
#define SYM(type,name) ((type)dlsym(metadata_handle,name))
    count_fn entries=SYM(count_fn,"get_camera_metadata_entry_count");
    count_fn bytes=SYM(count_fn,"get_camera_metadata_data_count");
    find_fn find=SYM(find_fn,"find_camera_metadata_ro_entry");
    alloc_fn alloc=SYM(alloc_fn,"allocate_camera_metadata");
    append_fn append=SYM(append_fn,"append_camera_metadata");
    add_fn add=SYM(add_fn,"add_camera_metadata_entry");
    sort_fn sort=SYM(sort_fn,"sort_camera_metadata");
    set_ops_fn register_ops=SYM(set_ops_fn,"set_camera_metadata_vendor_ops");
    get_vendor_id_fn get_id=SYM(get_vendor_id_fn,"get_camera_metadata_vendor_id");
    set_vendor_id_fn set_id=SYM(set_vendor_id_fn,"set_camera_metadata_vendor_id");
    free_fn release=SYM(free_fn,"free_camera_metadata");
#undef SYM
    if (!entries||!bytes||!find||!alloc||!append||!add||!sort||!register_ops||!release)
        {LOG("Camera metadata API missing; no synthetic tags");return NULL;}
    if (register_ops(&merged_ops)!=0)
        {LOG("Vendor tag registration failed");return NULL;}
    camera_metadata_ro_entry_t available={0};
    if (find(original,AOSP_STREAM_CONFIGS,&available)!=0 ||
        available.type!=1 || available.count<4 ||
        (available.count%4)!=0 || !available.data.i32)
        {LOG("No typed AOSP stream metadata");return NULL;}

    /* Keep full HAL stream tuple ABI: [pixel_format, width, height, output=0].
     * Do not replace BLOB/JPEG with PRIVATE=34 or invent sizes. Samsung
     * SemCameraCharacteristics reads the full four-int structure for each. */
    int32_t preview_config[MAX_SIZE_TUPLES*4];
    int32_t picture_config[MAX_SIZE_TUPLES*4];
    size_t preview_n=0, picture_n=0;
    for (size_t i=0;i<available.count;i+=4) {
        int32_t fmt=available.data.i32[i];
        int32_t w=available.data.i32[i+1];
        int32_t h=available.data.i32[i+2];
        int32_t direction=available.data.i32[i+3];
        if(direction!=OUTPUT||w<=0||h<=0||w>8192||h>8192) continue;
        int32_t *target;
        size_t *count;
        if(fmt==FMT_IMPLEMENTATION_DEFINED) {
            target=preview_config;
            count=&preview_n;
        } else if(fmt==FMT_BLOB) {
            target=picture_config;
            count=&picture_n;
        } else {
            continue;
        }
        bool duplicate=false;
        for(size_t j=0;j<*count;j++) {
            if(target[4*j+1]==w && target[4*j+2]==h) {
                duplicate=true;
                break;
            }
        }
        if(duplicate) continue;
        if(*count>=MAX_SIZE_TUPLES) {
            LOG("Samsung stream list exceeds capacity; disabling augmentation");
            return NULL;
        }
        const size_t pos=4*(*count);
        target[pos]=fmt;
        target[pos+1]=w;
        target[pos+2]=h;
        target[pos+3]=OUTPUT;
        ++*count;
    }
    if(!preview_n || !picture_n) {
        LOG("Missing real 34/private preview or 33/BLOB JPEG output sizes");
        return NULL;
    }

    /* The current S8+ Camera2 dump advertises the fixed [30,30] AE FPS range
     * and 33331760ns minimum frame duration for supported PRIVATE streams.
     * Build Samsung video tuples only for REAL supported resolution + FPS
     * combinations, rather than treating preview format 34 as an FPS limit.
     * Conservative 1080p cap intentionally excludes unverified UHD/60fps. */
    camera_metadata_ro_entry_t ae_fps={0}, min_durations={0};
    if(find(original,AOSP_AE_FPS_RANGES,&ae_fps)!=0 ||
       ae_fps.type!=TYPE_INT32 || (ae_fps.count%2)!=0 ||
       !ae_fps.data.i32 ||
       find(original,AOSP_MIN_FRAME_DURATIONS,&min_durations)!=0 ||
       min_durations.type!=TYPE_INT64 || (min_durations.count%4)!=0 ||
       !min_durations.data.i64) {
        LOG("Missing typed native AE FPS / minimum frame duration, refuse video metadata");
        return NULL;
    }
    bool has_30fps=false;
    for(size_t i=0;i<ae_fps.count;i+=2) {
        if(ae_fps.data.i32[i]==VIDEO_FPS &&
           ae_fps.data.i32[i+1]==VIDEO_FPS) {has_30fps=true; break;}
    }
    if(!has_30fps) {
        LOG("No real fixed 30fps AE mode, refuse Samsung video metadata");
        return NULL;
    }
    int32_t video_config[MAX_SIZE_TUPLES*VIDEO_FIELDS];
    size_t video_n=0;
    for(size_t i=0;i<preview_n;i++) {
        int32_t w=preview_config[4*i+1], h=preview_config[4*i+2];
        /* Standard 30fps recording only: checked against both actual
         * AOSP output stream size and minFrameDuration per camera. */
        if(w<640 || h<360 || w>1920 || h>1080) continue;
        bool duration_ok=false;
        for(size_t j=0;j<min_durations.count;j+=4) {
            const int64_t *v=&min_durations.data.i64[j];
            if(v[0]==FMT_IMPLEMENTATION_DEFINED && v[1]==w && v[2]==h &&
               v[3]>0 && v[3]<=(1000000000LL/VIDEO_FPS)) {
                duration_ok=true;
                break;
            }
        }
        if(!duration_ok) continue;
        if(video_n>=MAX_SIZE_TUPLES) return NULL;
        const size_t pos=video_n*VIDEO_FIELDS;
        video_config[pos+0]=w;
        video_config[pos+1]=h;
        video_config[pos+2]=VIDEO_FPS; /* min fps */
        video_config[pos+3]=VIDEO_FPS; /* max fps; valid Range [30,30] */
        video_config[pos+4]=0;         /* no stabilization crop requested */
        video_config[pos+5]=0;         /* no artificial recording time limit */
        ++video_n;
    }
    if(!video_n) {
        LOG("No genuine 30fps PRIVATE output for Samsung video configuration");
        return NULL;
    }
    const size_t old_count=entries(original), old_data=bytes(original);
    if(old_count>4096 || old_data>(1u<<22))return NULL;
    const size_t extra_bytes=((preview_n+picture_n)*4+video_n*VIDEO_FIELDS)*sizeof(int32_t);
    camera_metadata_t *merged=alloc(old_count+4,old_data+extra_bytes*2+1024);
    if(!merged)return NULL;
    if(get_id&&set_id)set_id(merged,get_id(original));
    if(append(merged,original)!=0 ||
       add(merged,PREVIEW_TAG,preview_config,preview_n*4)!=0 ||
       add(merged,PICTURE_TAG,picture_config,picture_n*4)!=0 ||
       add(merged,VIDEO_TAG,video_config,video_n*VIDEO_FIELDS)!=0 ||
       sort(merged)!=0) {
        LOG("Preview/photo metadata augmentation rejected by system metadata library");
        release(merged);
        return NULL;
    }
    LOG("Samsung 6-int VIDEO_TAG shape; real sizes + fixed 30fps: %zu preview, %zu JPEG, %zu conservative video configs (not device-tested)",
        preview_n,picture_n,video_n);
    return merged; /* camera_info pointers must remain valid for module lifetime */
}
static int wrapped_get_info(int id,camera_info_t *info) {
    if(!delegate||!delegate->get_camera_info)return -ENODEV;
    int res=delegate->get_camera_info(id,info);
    if(res!=0||!info||!info->static_camera_characteristics)return res;
    if(id<0||id>=MAX_CAMERAS)return res;
    /* The original bridge always took a process-wide mutex even when the
     * immutable camera characteristics had already been augmented.
     * Publish once with release ordering; all subsequent Camera2 metadata
     * queries can read the cached pointer without waiting for another camera.
     * No changes to sensor, capture requests, JPEG, video or face/iris. */
    camera_metadata_t *cached=__atomic_load_n(&static_metadata[id],__ATOMIC_ACQUIRE);
    if(!cached) {
        pthread_mutex_lock(&mu);
        cached=__atomic_load_n(&static_metadata[id],__ATOMIC_RELAXED);
        if(!cached && prepare_ops()) {
            cached=augment(info->static_camera_characteristics);
            if(cached)
                __atomic_store_n(&static_metadata[id],cached,__ATOMIC_RELEASE);
        }
        pthread_mutex_unlock(&mu);
    }
    if(cached)
        info->static_camera_characteristics=cached;
    return res;
}

__attribute__((constructor))static void initialize(void) {
#ifdef __LP64__
    const char *path="/vendor/lib64/hw/camera.alice-hlong.universal8895.so";
#else
    const char *path="/vendor/lib/hw/camera.alice-hlong.universal8895.so";
#endif
    void *handle=dlopen(path,RTLD_NOW|RTLD_LOCAL);
    if(!handle) { LOG("UN1GAGA delegate loader error: %s",dlerror()); return; }
    camera_module_t *candidate=(camera_module_t *)dlsym(handle,"HMI");
    if(!candidate||!candidate->common.id||
       strcmp(candidate->common.id,"camera")!=0||
       !candidate->common.methods||!candidate->get_camera_info||
       !candidate->common.methods->open) {
        LOG("UN1GAGA delegate HMI ABI mismatch, refusing module override");
        return;
    }
    delegate=candidate;
    HMI=*delegate; /* preserves Samsung/version/flags/callbacks */
    delegated_methods=*delegate->common.methods;
    delegated_methods.open=wrapped_open;
    HMI.common.methods=&delegated_methods;
    HMI.get_camera_info=wrapped_get_info;
    HMI.get_vendor_tag_ops=wrapped_get_vendor_tag_ops;
    if (delegate->open_legacy) HMI.open_legacy=wrapped_open_legacy;
    LOG("ALICE Exynos8895 native Camera tag bridge initialized (trial)");
}
