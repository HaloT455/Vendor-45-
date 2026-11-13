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
#define SHOT_LOG(...) __android_log_print(ANDROID_LOG_INFO,"ALICE_CameraShutter",__VA_ARGS__)
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

/* Android 9 camera3 metadata ABI. */
#define AOSP_CONTROL_AE_MODE 0x00010003u
#define AOSP_CONTROL_CAPTURE_INTENT 0x0001000du
#define AOSP_CONTROL_MODE 0x0001000fu
#define AOSP_CONTROL_ENABLE_ZSL 0x00010029u
#define AOSP_FLASH_MODE 0x00040002u
#define AOSP_AVAILABLE_CAPABILITIES 0x000c000cu
#define AOSP_AVAILABLE_REQUEST_KEYS 0x000c000du
#define CAPABILITY_PRIVATE_REPROCESSING 4
#define CAPABILITY_YUV_REPROCESSING 7
#define TYPE_BYTE 0
#define STILL_CAPTURE_INTENT 2
#define STILL_CAPTURE_TEMPLATE 2
#define CONTROL_AUTO 1
#define AE_MODE_ON 1
#define FLASH_MODE_OFF 0
#define DEVICE_API_3_0 0x300
#define DEVICE_API_3_5 0x305

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
struct hw_device {
    uint32_t tag;
    uint32_t version;
    hw_module_t *module;
#ifdef __LP64__
    uint64_t reserved[12];
#else
    uint32_t reserved[12];
#endif
    int (*close)(hw_device_t *);
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

typedef struct camera3_device camera3_device_t;
struct camera3_callback_ops;
struct camera3_stream_configuration;
struct camera3_stream_buffer_set;
struct camera3_capture_request;
struct vendor_tag_query_ops;
typedef struct camera3_device_ops {
    int (*initialize)(const camera3_device_t *, const struct camera3_callback_ops *);
    int (*configure_streams)(const camera3_device_t *, struct camera3_stream_configuration *);
    int (*register_stream_buffers)(const camera3_device_t *, const struct camera3_stream_buffer_set *);
    const camera_metadata_t *(*construct_default_request_settings)(const camera3_device_t *, int);
    int (*process_capture_request)(const camera3_device_t *, struct camera3_capture_request *);
    void (*get_metadata_vendor_tag_ops)(const camera3_device_t *, struct vendor_tag_query_ops *);
    void (*dump)(const camera3_device_t *, int);
    int (*flush)(const camera3_device_t *);
    void *reserved[8];
} camera3_device_ops_t;
struct camera3_device {
    hw_device_t common;
    camera3_device_ops_t *ops;
    void *priv;
};

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
typedef camera_metadata_t *(*clone_fn)(const camera_metadata_t *);
struct camera_metadata_entry;
typedef int (*update_fn)(camera_metadata_t *, size_t, const void *, size_t,
                         struct camera_metadata_entry *);

struct still_template {
    camera3_device_t *device;
    camera3_device_ops_t *original_ops;
    int (*original_close)(hw_device_t *);
    camera3_device_ops_t ops;
    camera_metadata_t *metadata;
    free_fn release;
    void *metadata_lib;
};

static camera_module_t *delegate;
static hw_module_methods_t delegated_methods;
static vendor_tag_ops_t legacy_ops;
static vendor_tag_ops_t merged_ops;
static camera_metadata_t *static_metadata[MAX_CAMERAS];
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static void *metadata_handle;
static pthread_mutex_t still_mu = PTHREAD_MUTEX_INITIALIZER;
static struct still_template still_devices[MAX_CAMERAS];

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

static bool byte_tag_is(find_fn find, const camera_metadata_t *metadata,
                        uint32_t tag, uint8_t value) {
    camera_metadata_ro_entry_t entry = {0};
    return find(metadata,tag,&entry)==0 && entry.type==TYPE_BYTE &&
        entry.count==1 && entry.data.u8 && entry.data.u8[0]==value;
}

static bool supports_still_zsl(find_fn find, const camera_metadata_t *metadata) {
    camera_metadata_ro_entry_t capabilities = {0}, keys = {0};
    if (find(metadata,AOSP_AVAILABLE_CAPABILITIES,&capabilities)!=0 ||
        capabilities.type!=TYPE_BYTE || !capabilities.data.u8 ||
        find(metadata,AOSP_AVAILABLE_REQUEST_KEYS,&keys)!=0 ||
        keys.type!=TYPE_INT32 || !keys.data.i32)
        return false;
    bool reprocessing=false;
    for (size_t i=0;i<capabilities.count;++i) {
        uint8_t cap=capabilities.data.u8[i];
        if (cap==CAPABILITY_PRIVATE_REPROCESSING || cap==CAPABILITY_YUV_REPROCESSING) {
            reprocessing=true;
            break;
        }
    }
    if (!reprocessing) return false;
    for (size_t i=0;i<keys.count;++i)
        if ((uint32_t)keys.data.i32[i]==AOSP_CONTROL_ENABLE_ZSL) return true;
    return false;
}

static camera_metadata_t *fast_still_template(const camera_metadata_t *source,
                                              find_fn find, clone_fn clone,
                                              update_fn update, free_fn release) {
    camera_metadata_ro_entry_t zsl = {0};
    const uint8_t enable=1;
    if (!source || !byte_tag_is(find,source,AOSP_CONTROL_CAPTURE_INTENT,STILL_CAPTURE_INTENT) ||
        !byte_tag_is(find,source,AOSP_CONTROL_MODE,CONTROL_AUTO) ||
        !byte_tag_is(find,source,AOSP_CONTROL_AE_MODE,AE_MODE_ON) ||
        !byte_tag_is(find,source,AOSP_FLASH_MODE,FLASH_MODE_OFF) ||
        find(source,AOSP_CONTROL_ENABLE_ZSL,&zsl)!=0 || zsl.type!=TYPE_BYTE ||
        zsl.count!=1 || !zsl.data.u8 || zsl.data.u8[0]!=0)
        return NULL;

    camera_metadata_t *copy=clone(source);
    if (!copy) return NULL;
    if (update(copy,zsl.index,&enable,1,NULL)!=0) {
        release(copy);
        return NULL;
    }
    return copy;
}

static const camera_metadata_t *still_default_request(const camera3_device_t *device,
                                                      int type) {
    struct still_template *state=(void *)((char *)device->ops -
        offsetof(struct still_template,ops));
    const camera_metadata_t *original=
        state->original_ops->construct_default_request_settings(device,type);
    if (!original || type!=STILL_CAPTURE_TEMPLATE) return original;

    pthread_mutex_lock(&still_mu);
    if (!state->metadata) {
        find_fn find=(find_fn)dlsym(state->metadata_lib,"find_camera_metadata_ro_entry");
        clone_fn clone=(clone_fn)dlsym(state->metadata_lib,"clone_camera_metadata");
        update_fn update=(update_fn)dlsym(state->metadata_lib,"update_camera_metadata_entry");
        if (find && clone && update)
            state->metadata=fast_still_template(original,find,clone,update,state->release);
        if (state->metadata)
            SHOT_LOG("Rear still template enables the HAL ZSL request key");
    }
    const camera_metadata_t *result=state->metadata ? state->metadata : original;
    pthread_mutex_unlock(&still_mu);
    return result;
}

static int still_device_close(hw_device_t *hw) {
    camera3_device_t *device=(camera3_device_t *)hw;
    struct still_template *state=(void *)((char *)device->ops -
        offsetof(struct still_template,ops));

    pthread_mutex_lock(&still_mu);
    camera_metadata_t *metadata=state->metadata;
    free_fn release=state->release;
    void *metadata_lib=state->metadata_lib;
    int (*close_device)(hw_device_t *)=state->original_close;
    device->ops=state->original_ops;
    device->common.close=close_device;
    state->device=NULL;
    pthread_mutex_unlock(&still_mu);

    int status=close_device(hw);
    if (metadata) release(metadata);
    dlclose(metadata_lib);
    return status;
}

static void enable_still_zsl(const char *id, hw_device_t *hw) {
    if (!id || !hw || hw->version<DEVICE_API_3_0 || hw->version>DEVICE_API_3_5 ||
        !hw->close || id[0]<'0' || id[0]>'7' || id[1]!='\0')
        return;

    camera3_device_t *device=(camera3_device_t *)hw;
    if (!device->ops || !device->ops->construct_default_request_settings)
        return;

    camera_info_t info = {0};
    if (delegate->get_camera_info(id[0]-'0',&info)!=0 || info.facing!=0 ||
        !info.static_camera_characteristics)
        return;

    void *metadata_lib=dlopen("libcamera_metadata.so",RTLD_NOW|RTLD_LOCAL);
    if (!metadata_lib) return;
    find_fn find=(find_fn)dlsym(metadata_lib,"find_camera_metadata_ro_entry");
    free_fn release=(free_fn)dlsym(metadata_lib,"free_camera_metadata");
    if (!find || !release ||
        !supports_still_zsl(find,info.static_camera_characteristics)) {
        SHOT_LOG("Camera %s has no reported still ZSL capability",id);
        dlclose(metadata_lib);
        return;
    }

    /* Keep each default template valid until its HAL device closes. */
    pthread_mutex_lock(&still_mu);
    for (size_t i=0;i<MAX_CAMERAS;++i) {
        struct still_template *state=&still_devices[i];
        if (state->device) continue;
        state->device=device;
        state->original_ops=device->ops;
        state->original_close=hw->close;
        state->ops=*device->ops;
        state->ops.construct_default_request_settings=still_default_request;
        state->metadata=NULL;
        state->release=release;
        state->metadata_lib=metadata_lib;
        device->ops=&state->ops;
        hw->close=still_device_close;
        pthread_mutex_unlock(&still_mu);
        return;
    }
    pthread_mutex_unlock(&still_mu);
    dlclose(metadata_lib);
}

static int wrapped_open(const hw_module_t *ignored,const char *id,hw_device_t **device) {
    (void)ignored;
    if (!delegate || !delegate->common.methods ||
        !delegate->common.methods->open) return -ENODEV;
    int status=delegate->common.methods->open(&delegate->common,id,device);
    if (status==0 && device)
        enable_still_zsl(id,*device);
    return status;
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
