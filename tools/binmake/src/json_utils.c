#include "json_utils.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>   // for strtoul

/* ---------- local helpers ---------- */

static void write_string(char *dest, const char *src, size_t max_len)
{
    if (src && *src) {
        strncpy(dest, src, max_len - 1);
        dest[max_len - 1] = '\0';
    } else {
        dest[0] = '\0';
    }
}

const char* json_get_str(cJSON *obj, const char *key)
{
    cJSON *it = cJSON_GetObjectItem(obj, key);
    return (it && cJSON_IsString(it) && it->valuestring && it->valuestring[0]) ? it->valuestring : NULL;
}

static int parse_uint_array(cJSON *array, uint8_t *out_array, size_t max_len)
{
    if (!cJSON_IsArray(array)) return -1;

    size_t count = (size_t)cJSON_GetArraySize(array);
    size_t out_offset = 0;
    memset(out_array, 0, max_len);

    for (size_t i = 0; i < count; ++i) {
        cJSON *item = cJSON_GetArrayItem(array, (int)i);
        if (!cJSON_IsString(item) || item->valuestring == NULL)
            return -1;

        uint32_t val = (uint32_t)strtoul(item->valuestring, NULL, 0);

        size_t size = 1;
        if (val > 0xFF)     size = 2;
        if (val > 0xFFFF)   size = 3;
        if (val > 0xFFFFFF) size = 4;

        if (out_offset + size > max_len)
            return -1;

        for (size_t b = 0; b < size; ++b)
            out_array[out_offset + b] = (uint8_t)((val >> (8 * (size - 1 - b))) & 0xFF);

        out_offset += size;
    }
    return 0;
}

/* ---------- field table ---------- */

typedef enum { FIELD_U8, FIELD_U16, FIELD_U32, FIELD_STRING, FIELD_UINT_ARRAY } FieldType;
typedef struct { const char *key; FieldType type; } FieldDesc;

static FieldDesc fields[] = {
    {"model_id"         , FIELD_U32},
    {"revision_minor"   , FIELD_U16},
    {"revision_major"   , FIELD_U16},
    {"model_string"     , FIELD_STRING},
    {"mfg_name"         , FIELD_STRING},

    {"bl2_loc"          , FIELD_U8},
    {"bl2_dtb_loc"      , FIELD_U8},
    {"u_boot_loc"       , FIELD_U8},
    {"u_boot_dtb_loc"   , FIELD_U8},
    {"kernel_loc"       , FIELD_U8},
    {"kernel_dtb_loc"   , FIELD_U8},

    {"bl2_id"           , FIELD_U8},
    {"bl2_dtb_id"       , FIELD_U8},
    {"u_boot_id"        , FIELD_U8},
    {"u_boot_dtb_id"    , FIELD_U8},
    {"kernel_id"        , FIELD_U8},
    {"kernel_dtb_id"    , FIELD_U8},

    {"bl2_desc"         , FIELD_UINT_ARRAY},
    {"bl2_dtb_desc"     , FIELD_UINT_ARRAY},
    {"u_boot_desc"      , FIELD_UINT_ARRAY},
    {"u_boot_dtb_desc"  , FIELD_UINT_ARRAY},
    {"kernel_desc"      , FIELD_UINT_ARRAY},
    {"kernel_dtb_desc"  , FIELD_UINT_ARRAY},
};

/* ---------- public API ---------- */

cJSON* json_find_board_by_model_string(cJSON *root_all, const char *model_string)
{
    if (!root_all || !model_string) return NULL;
    for (cJSON *child = root_all->child; child; child = child->next) {
        if (!cJSON_IsObject(child)) continue;
        const char *ms = json_get_str(child, "model_string");
        if (ms && strcmp(ms, model_string) == 0) return child;
    }
    return NULL;
}

int json_validate_base_required(cJSON *board_obj, const char *board_name)
{
    for (size_t i = 0; i < sizeof(fields)/sizeof(fields[0]); ++i) {
        if (!cJSON_GetObjectItem(board_obj, fields[i].key)) {
            fprintf(stderr, "Missing field '%s' in JSON for board '%s'\n", fields[i].key, board_name);
            return -1;
        }
    }
    return 0;
}

int json_apply_fields_from_obj(cJSON *obj, const char *board_name, platform_desc_t *desc)
{
    for (size_t i = 0; i < sizeof(fields) / sizeof(fields[0]); ++i) {
        FieldDesc *fd = &fields[i];
        cJSON *item = cJSON_GetObjectItem(obj, fd->key);
        if (!item) continue;

        switch (fd->type) {
        case FIELD_U8: {
            if (!cJSON_IsNumber(item)) { fprintf(stderr, "Field '%s' must be number (board %s)\n", fd->key, board_name); return -1; }
            uint8_t v = (uint8_t)item->valueint;
            if      (!strcmp(fd->key, "bl2_loc"))         desc->bl2_loc = v;
            else if (!strcmp(fd->key, "bl2_dtb_loc"))     desc->bl2_dtb_loc = v;
            else if (!strcmp(fd->key, "u_boot_loc"))      desc->u_boot_loc = v;
            else if (!strcmp(fd->key, "u_boot_dtb_loc"))  desc->u_boot_dtb_loc = v;
            else if (!strcmp(fd->key, "kernel_loc"))      desc->kernel_loc = v;
            else if (!strcmp(fd->key, "kernel_dtb_loc"))  desc->kernel_dtb_loc = v;
            else if (!strcmp(fd->key, "bl2_id"))          desc->bl2_id = v;
            else if (!strcmp(fd->key, "bl2_dtb_id"))      desc->bl2_dtb_id = v;
            else if (!strcmp(fd->key, "u_boot_id"))       desc->u_boot_id = v;
            else if (!strcmp(fd->key, "u_boot_dtb_id"))   desc->u_boot_dtb_id = v;
            else if (!strcmp(fd->key, "kernel_id"))       desc->kernel_id = v;
            else if (!strcmp(fd->key, "kernel_dtb_id"))   desc->kernel_dtb_id = v;
            break;
        }
        case FIELD_U16:
            if (!cJSON_IsNumber(item)) { fprintf(stderr, "Field '%s' must be number (board %s)\n", fd->key, board_name); return -1; }
            if      (!strcmp(fd->key, "revision_minor")) desc->revision_minor = (uint16_t)item->valueint;
            else if (!strcmp(fd->key, "revision_major")) desc->revision_major = (uint16_t)item->valueint;
            break;
        case FIELD_U32:
            if (!cJSON_IsNumber(item)) { fprintf(stderr, "Field '%s' must be number (board %s)\n", fd->key, board_name); return -1; }
            if (!strcmp(fd->key, "model_id")) desc->model_id = (uint32_t)item->valueint;
            break;
        case FIELD_STRING:
            if (!cJSON_IsString(item)) { fprintf(stderr, "Field '%s' must be string (board %s)\n", fd->key, board_name); return -1; }
            if      (!strcmp(fd->key, "model_string")) write_string(desc->model_string, item->valuestring, MAX_MODEL_STRING_LEN);
            else if (!strcmp(fd->key, "mfg_name"))     write_string(desc->mfg_name,   item->valuestring, MAX_SIZE_LEN);
            break;
        case FIELD_UINT_ARRAY:
            if      (!strcmp(fd->key, "bl2_desc"))        { if (parse_uint_array(item, desc->bl2_desc,        MAX_SIZE_LEN)) return -1; }
            else if (!strcmp(fd->key, "bl2_dtb_desc"))    { if (parse_uint_array(item, desc->bl2_dtb_desc,    MAX_SIZE_LEN)) return -1; }
            else if (!strcmp(fd->key, "u_boot_desc"))     { if (parse_uint_array(item, desc->u_boot_desc,     MAX_SIZE_LEN)) return -1; }
            else if (!strcmp(fd->key, "u_boot_dtb_desc")) { if (parse_uint_array(item, desc->u_boot_dtb_desc, MAX_SIZE_LEN)) return -1; }
            else if (!strcmp(fd->key, "kernel_desc"))     { if (parse_uint_array(item, desc->kernel_desc,     MAX_SIZE_LEN)) return -1; }
            else if (!strcmp(fd->key, "kernel_dtb_desc")) { if (parse_uint_array(item, desc->kernel_dtb_desc, MAX_SIZE_LEN)) return -1; }
            break;
        }
    }
    return 0;
}

bool json_series_match(cJSON *obj, uint32_t base_model_id, const char *base_model_string)
{
    cJSON *mid  = cJSON_GetObjectItem(obj, "model_id");
    cJSON *mstr = cJSON_GetObjectItem(obj, "model_string");
    if (!cJSON_IsNumber(mid) || !cJSON_IsString(mstr)) return false;
    return ((uint32_t)mid->valueint == base_model_id) &&
           (strcmp(mstr->valuestring, base_model_string) == 0);
}

void json_print_available_revisions(cJSON *root_all,
                                    uint32_t series_model_id,
                                    const char *series_model_string)
{
    typedef struct { uint16_t maj, min; } revpair_t;
    revpair_t revs[512];
    int n = 0;

    for (cJSON *child = root_all->child; child; child = child->next) {
        if (!cJSON_IsObject(child)) continue;
        if (!json_series_match(child, series_model_id, series_model_string)) continue;

        cJSON *rmin = cJSON_GetObjectItem(child, "revision_minor");
        cJSON *rmaj = cJSON_GetObjectItem(child, "revision_major");
        if (!cJSON_IsNumber(rmin) || !cJSON_IsNumber(rmaj)) continue;

        uint16_t mi = (uint16_t)rmin->valueint;
        uint16_t ma = (uint16_t)rmaj->valueint;

        bool seen = false;
        for (int i = 0; i < n; ++i) {
            if (revs[i].maj == ma && revs[i].min == mi) { seen = true; break; }
        }
        if (!seen && n < (int)(sizeof(revs)/sizeof(revs[0]))) {
            revs[n].maj = ma; revs[n].min = mi; n++;
        }
    }

    if (n == 0) {
        fprintf(stderr, "No revisions declared for this series.\n");
        return;
    }

    for (int i = 0; i + 1 < n; ++i) {
        for (int j = i + 1; j < n; ++j) {
            if (revs[j].maj < revs[i].maj ||
               (revs[j].maj == revs[i].maj && revs[j].min < revs[i].min)) {
                revpair_t t = revs[i];
                revs[i] = revs[j];
                revs[j] = t;
            }
        }
    }

    fprintf(stderr, "Available revisions for %s:\n", series_model_string);
    for (int i = 0; i < n; ++i)
        fprintf(stderr, "  - %u.%u\n", revs[i].maj, revs[i].min);
}

char *load_file_as_string(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) {
        perror("Failed to open input JSON");
        return NULL;
    }

    if (fseek(f, 0, SEEK_END) != 0) {
        perror("fseek failed");
        fclose(f);
        return NULL;
    }

    long file_len = ftell(f);
    if (file_len < 0) {
        perror("ftell failed");
        fclose(f);
        return NULL;
    }
    rewind(f);

    size_t len = (size_t)file_len;
    char *buf = (char *)malloc(len + 1);
    if (!buf) {
        perror("malloc failed");
        fclose(f);
        return NULL;
    }

    size_t n = fread(buf, 1, len, f);
    fclose(f);
    if (n != len) {
        fprintf(stderr, "Failed to read entire JSON file.\n");
        free(buf);
        return NULL;
    }

    buf[len] = '\0';
    return buf;
}

cJSON *load_json_from_file(const char *path)
{
    char *text = load_file_as_string(path);
    if (!text) return NULL;

    cJSON *root = cJSON_Parse(text);
    free(text);

    if (!root) {
        fprintf(stderr, "JSON parsing error in %s\n", path);
        return NULL;
    }
    return root;
}