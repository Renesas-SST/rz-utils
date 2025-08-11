#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>
#include <stdbool.h>
#include "cjson/cJSON.h"

#define MAX_SIZE_LEN 256
#define MAX_MODEL_STRING_LEN 256

typedef enum
{
    FIELD_U8,
    FIELD_U16,
    FIELD_U32,
    FIELD_STRING,
    FIELD_UINT_ARRAY
} FieldType;

typedef struct
{
    const char *key;
    FieldType type;
} FieldDesc;

FieldDesc fields[] = {
    {"model_id"         , FIELD_U32        },
    {"revision_minor"   , FIELD_U16        },
    {"revision_major"   , FIELD_U16        },
    {"model_string"     , FIELD_STRING     },
    {"mfg_name"         , FIELD_STRING     },
    {"bl2_loc"          , FIELD_U8         },
    {"bl2_dtb_loc"      , FIELD_U8         },
    {"u_boot_loc"       , FIELD_U8         },
    {"u_boot_dtb_loc"   , FIELD_U8         },
    {"kernel_loc"       , FIELD_U8         },
    {"kernel_dtb_loc"   , FIELD_U8         },
    {"bl2_id"           , FIELD_U8         },
    {"bl2_dtb_id"       , FIELD_U8         },
    {"u_boot_id"        , FIELD_U8         },
    {"u_boot_dtb_id"    , FIELD_U8         },
    {"kernel_id"        , FIELD_U8         },
    {"kernel_dtb_id"    , FIELD_U8         },
    {"bl2_desc"         , FIELD_UINT_ARRAY },
    {"bl2_dtb_desc"     , FIELD_UINT_ARRAY },
    {"u_boot_desc"      , FIELD_UINT_ARRAY },
    {"u_boot_dtb_desc"  , FIELD_UINT_ARRAY },
    {"kernel_desc"      , FIELD_UINT_ARRAY },
    {"kernel_dtb_desc"  , FIELD_UINT_ARRAY },
};

typedef struct __attribute__((packed)) platform_desc {
    uint32_t model_id;
    uint32_t revision_minor : 16;
    uint32_t revision_major : 16;
    char model_string[MAX_MODEL_STRING_LEN];
    char mfg_name[MAX_SIZE_LEN];

    uint32_t bl2_loc        : 4;
    uint32_t bl2_dtb_loc    : 4;
    uint32_t u_boot_loc     : 4;
    uint32_t u_boot_dtb_loc : 4;
    uint32_t kernel_loc     : 4;
    uint32_t kernel_dtb_loc : 4;
    uint32_t res_loc        : 4;    // reserved
    uint32_t res1_loc       : 4;    // reserved

    uint32_t bl2_id         : 4;
    uint32_t bl2_dtb_id     : 4;
    uint32_t u_boot_id      : 4;
    uint32_t u_boot_dtb_id  : 4;
    uint32_t kernel_id      : 4;
    uint32_t kernel_dtb_id  : 4;
    uint32_t res_id         : 4;    // reserved
    uint32_t res1_id        : 4;    // reserved

    uint8_t bl2_desc[MAX_SIZE_LEN];
    uint8_t bl2_dtb_desc[MAX_SIZE_LEN];
    uint8_t u_boot_desc[MAX_SIZE_LEN];
    uint8_t u_boot_dtb_desc[MAX_SIZE_LEN];
    uint8_t kernel_desc[MAX_SIZE_LEN];
    uint8_t kernel_dtb_desc[MAX_SIZE_LEN];
} platform_desc_t;

/* ---------- helpers ---------- */

static void write_string(char *dest, const char *src, size_t max_len)
{
    if (src && *src)
    {
        strncpy(dest, src, max_len - 1);
        dest[max_len - 1] = '\0';
    }
    else
    {
        dest[0] = '\0';
    }
}

static int parse_uint_array(cJSON *array, uint8_t *out_array, size_t max_len)
{
    if (!cJSON_IsArray(array))
        return -1;

    size_t count = (size_t)cJSON_GetArraySize(array);
    size_t out_offset = 0;
    memset(out_array, 0, max_len);

    for (size_t array_idx = 0; array_idx < count; ++array_idx)
    {
        cJSON *item = cJSON_GetArrayItem(array, (int)array_idx);
        if (!cJSON_IsString(item) || item->valuestring == NULL)
            return -1;

        uint32_t val = (uint32_t)strtoul(item->valuestring, NULL, 0);

        size_t size = 1;
        if (val > 0xFF)        size = 2;
        if (val > 0xFFFF)      size = 3;
        if (val > 0xFFFFFF)    size = 4;

        if (out_offset + size > max_len)
            return -1;

        for (size_t byte_idx = 0; byte_idx < size; ++byte_idx)
            out_array[out_offset + byte_idx] = (uint8_t)((val >> (8 * (size - 1 - byte_idx))) & 0xFF);

        out_offset += size;
    }

    return 0;
}

/* Overlay: apply only keys that exist in obj */
static int apply_fields_from_json(cJSON *obj, const char *board_name, platform_desc_t *desc) {
    for (size_t i = 0; i < sizeof(fields) / sizeof(fields[0]); i++) {
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
            if (!strcmp(fd->key, "revision_minor")) desc->revision_minor = (uint16_t)item->valueint;
            else if (!strcmp(fd->key, "revision_major")) desc->revision_major = (uint16_t)item->valueint;
            break;
        case FIELD_U32:
            if (!cJSON_IsNumber(item)) { fprintf(stderr, "Field '%s' must be number (board %s)\n", fd->key, board_name); return -1; }
            if (!strcmp(fd->key, "model_id")) desc->model_id = (uint32_t)item->valueint;
            break;
        case FIELD_STRING:
            if (!cJSON_IsString(item)) { fprintf(stderr, "Field '%s' must be string (board %s)\n", fd->key, board_name); return -1; }
            if (!strcmp(fd->key, "model_string"))
                write_string(desc->model_string, item->valuestring, MAX_MODEL_STRING_LEN);
            else if (!strcmp(fd->key, "mfg_name"))
                write_string(desc->mfg_name, item->valuestring, MAX_SIZE_LEN);
            break;
        case FIELD_UINT_ARRAY:
            if (!strcmp(fd->key, "bl2_desc")) {
                if (parse_uint_array(item, desc->bl2_desc, MAX_SIZE_LEN)) return -1;
            } else if (!strcmp(fd->key, "bl2_dtb_desc")) {
                if (parse_uint_array(item, desc->bl2_dtb_desc, MAX_SIZE_LEN)) return -1;
            } else if (!strcmp(fd->key, "u_boot_desc")) {
                if (parse_uint_array(item, desc->u_boot_desc, MAX_SIZE_LEN)) return -1;
            } else if (!strcmp(fd->key, "u_boot_dtb_desc")) {
                if (parse_uint_array(item, desc->u_boot_dtb_desc, MAX_SIZE_LEN)) return -1;
            } else if (!strcmp(fd->key, "kernel_desc")) {
                if (parse_uint_array(item, desc->kernel_desc, MAX_SIZE_LEN)) return -1;
            } else if (!strcmp(fd->key, "kernel_dtb_desc")) {
                if (parse_uint_array(item, desc->kernel_dtb_desc, MAX_SIZE_LEN)) return -1;
            }
            break;
        }
    }
    return 0;
}

/* Ensure the base board provides all required keys once */
static int validate_base_required(cJSON *board_obj, const char *board_name) {
    for (size_t i = 0; i < sizeof(fields)/sizeof(fields[0]); ++i) {
        if (!cJSON_GetObjectItem(board_obj, fields[i].key)) {
            fprintf(stderr, "Missing field '%s' in JSON for board '%s'\n",
                    fields[i].key, board_name);
            return -1;
        }
    }
    return 0;
}

static bool parse_rev_string(const char *s, uint16_t *out_minor, uint16_t *out_major)
{
    unsigned int minor = 0, major = 0;

    // Expect "minor.major"
    if (!s || sscanf(s, "%u.%u", &minor, &major) != 2)
        return false;

    *out_minor = (uint16_t)minor;
    *out_major = (uint16_t)major;
    return true;
}

static bool series_match(cJSON *obj, uint32_t base_model_id, const char *base_model_string)
{
    cJSON *mid = cJSON_GetObjectItem(obj, "model_id");
    cJSON *mstr = cJSON_GetObjectItem(obj, "model_string");
    if (!cJSON_IsNumber(mid) || !cJSON_IsString(mstr)) return false;
    return ((uint32_t)mid->valueint == base_model_id) &&
           (strcmp(mstr->valuestring, base_model_string) == 0);
}

static int write_desc_to_file(const char *path, const platform_desc_t *desc)
{
    FILE *out = fopen(path, "wb");
    if (!out) {
        fprintf(stderr, "Failed to open output file '%s': %s\n", path, strerror(errno));
        return -1;
    }
    size_t w = fwrite(desc, 1, sizeof(*desc), out);
    fclose(out);
    if (w != sizeof(*desc)) {
        fprintf(stderr, "Short write to '%s'\n", path);
        return -1;
    }
    struct stat st;
    if (stat(path, &st) == 0) {
        printf("  -> %s (size: 0x%lx)\n", path, (unsigned long)st.st_size);
    }
    return 0;
}

static bool is_directory(const char *path)
{
    struct stat st;
    if (!path) return false;
    if (stat(path, &st) != 0) return false;
    return S_ISDIR(st.st_mode);
}

static void join_path(char *dst, size_t dstsz, const char *dir_or_prefix, const char *leaf, const char *ext_if_needed)
{
    if (!dir_or_prefix || !*dir_or_prefix) {
        if (ext_if_needed && *ext_if_needed)
            snprintf(dst, dstsz, "%s%s", leaf, ext_if_needed);
        else
            snprintf(dst, dstsz, "%s", leaf);
        return;
    }

    if (is_directory(dir_or_prefix)) {
#ifdef _WIN32
        const char sep = '\\';
#else
        const char sep = '/';
#endif
        if (ext_if_needed && *ext_if_needed)
            snprintf(dst, dstsz, "%s%c%s%s", dir_or_prefix, sep, leaf, ext_if_needed);
        else
            snprintf(dst, dstsz, "%s%c%s", dir_or_prefix, sep, leaf);
    } else {
        /* treat as plain path (likely single file), just copy */
        snprintf(dst, dstsz, "%s", dir_or_prefix);
    }
}

/* ---------- CLI & main ---------- */

static void print_help(const char *prog_name) {
    printf("Usage:\n");
    printf("  %s --input=platform_info.json --board=BOARD --output=BOARD.bin [--revision=X.Y]\n", prog_name);
    printf("  %s --input=platform_info.json --board=BOARD [--output=OUT_DIR] --all-revisions\n", prog_name);
    printf("\nOptions:\n");
    printf("  --input=FILE       Path to input JSON file\n");
    printf("  --board=NAME       Base board key in JSON (e.g. rzv2h-evk)\n");
    printf("  --output=PATH      Output file (single build) or output directory (with --all-revisions).\n");
    printf("  --revision=X.Y     (Optional) select revision (minor.major). Example: 1.21\n");
    printf("  --all-revisions    Build binaries for every JSON object in the same series\n");
    printf("  -h, --help         Show this help\n");
}

int main(int argc, char *argv[]) {
    const char *json_path = NULL;
    const char *board_name = NULL;
    const char *output_path = NULL;
    const char *rev_key = NULL;
    int all_revs_mode = 0;

    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "--input=", 8) == 0) {
            json_path = argv[i] + 8;
        } else if (strncmp(argv[i], "--board=", 8) == 0) {
            board_name = argv[i] + 8;
        } else if (strncmp(argv[i], "--output=", 9) == 0) {
            output_path = argv[i] + 9;
        } else if (strncmp(argv[i], "--revision=", 11) == 0) {
            rev_key = argv[i] + 11;
        } else if (strcmp(argv[i], "--all-revisions") == 0) {
            all_revs_mode = 1;
        } else if ((strcmp(argv[i], "-h") == 0) || (strcmp(argv[i], "--help") == 0)) {
            print_help(argv[0]);
            return EXIT_SUCCESS;
        } else {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            print_help(argv[0]);
            return EXIT_FAILURE;
        }
    }

    if (!json_path || !board_name) {
        print_help(argv[0]);
        return EXIT_FAILURE;
    }
    if (!output_path && !all_revs_mode) {
        fprintf(stderr, "Error: --output is required for single build.\n");
        print_help(argv[0]);
        return EXIT_FAILURE;
    }

    FILE *f = fopen(json_path, "rb");
    if (!f) {
        perror("Failed to open input JSON");
        return EXIT_FAILURE;
    }

    fseek(f, 0, SEEK_END);
    long file_len = ftell(f);
    if (file_len < 0) {
        perror("ftell failed");
        fclose(f);
        return EXIT_FAILURE;
    }
    size_t len = (size_t)file_len;
    rewind(f);

    char *json_data = (char *)malloc(len + 1);
    if (!json_data) {
        perror("malloc failed");
        fclose(f);
        return EXIT_FAILURE;
    }

    if (fread(json_data, 1, len, f) != len) {
        fprintf(stderr, "Failed to read entire JSON file.\n");
        free(json_data);
        fclose(f);
        return EXIT_FAILURE;
    }
    json_data[len] = '\0';
    fclose(f);

    cJSON *root_all = cJSON_Parse(json_data);
    if (!root_all) {
        fprintf(stderr, "JSON parsing error\n");
        free(json_data);
        return EXIT_FAILURE;
    }

    cJSON *root = cJSON_GetObjectItem(root_all, board_name);
    if (!root) {
        fprintf(stderr, "Board '%s' not found in JSON.\n", board_name);
        fprintf(stderr, "Available boards:\n");
        for (cJSON *child = root_all->child; child; child = child->next) {
            if (cJSON_IsObject(child) && child->string)
                fprintf(stderr, "  - %s\n", child->string);
        }
        cJSON_Delete(root_all);
        free(json_data);
        return EXIT_FAILURE;
    }

    platform_desc_t base_desc;
    memset(&base_desc, 0, sizeof(base_desc));

    /* Validate & apply base board fields */
    if (validate_base_required(root, board_name) != 0) {
        cJSON_Delete(root_all);
        free(json_data);
        return EXIT_FAILURE;
    }
    if (apply_fields_from_json(root, board_name, &base_desc) != 0) {
        cJSON_Delete(root_all);
        free(json_data);
        return EXIT_FAILURE;
    }

    /* Capture series identity from base */
    cJSON *mid = cJSON_GetObjectItem(root, "model_id");
    cJSON *mstr = cJSON_GetObjectItem(root, "model_string");
    uint32_t series_model_id = (uint32_t)(mid ? mid->valueint : 0);
    const char *series_model_string = (mstr && cJSON_IsString(mstr)) ? mstr->valuestring : "";

    /* Handle all revisions mode */
    if (all_revs_mode) {
        printf("Building all revisions for series: model_id=%u, model_string=\"%s\"\n",
            series_model_id, series_model_string);

        /* First pass: count how many revisions exist in this series */
        int total_revs = 0;
        for (cJSON *child = root_all->child; child; child = child->next) {
            if (!cJSON_IsObject(child)) continue;
            if (!series_match(child, series_model_id, series_model_string)) continue;
            total_revs++;
        }

        int built = 0;
        for (cJSON *child = root_all->child; child; child = child->next) {
            if (!cJSON_IsObject(child))
                continue;

            if (!series_match(child, series_model_id, series_model_string))
                continue;

            /* Build: start from base, overlay child */
            platform_desc_t desc = base_desc;
            const char *child_key = child->string ? child->string : "unknown";

            if (apply_fields_from_json(child, child_key, &desc) != 0) {
                fprintf(stderr, "Skipping '%s' due to field error\n", child_key);
                continue;
            }

            char outpath[1024];
            char filename[512];

            /* Filename format depends on how many revisions exist */
            if (total_revs > 1) {
                snprintf(filename, sizeof(filename),
                        "%s-ver%u.%u-platform-settings.bin",
                        desc.model_string,
                        desc.revision_minor,
                        desc.revision_major);
            } else {
                snprintf(filename, sizeof(filename),
                        "%s-platform-settings.bin",
                        desc.model_string);
            }

            /* In all-revisions mode, --output must be a directory (or omitted) */
            if (output_path) {
                if (is_directory(output_path)) {
                    join_path(outpath, sizeof(outpath), output_path, filename, NULL);
                } else {
                    fprintf(stderr,
                            "Warning: --output is not a directory, ignoring it in --all-revisions mode.\n");
                    snprintf(outpath, sizeof(outpath), "%s", filename);
                }
            } else {
                snprintf(outpath, sizeof(outpath), "%s", filename);
            }

            printf("Writing %s (rev %u.%u)\n", outpath,
                desc.revision_minor, desc.revision_major);

            if (write_desc_to_file(outpath, &desc) != 0) {
                fprintf(stderr, "Failed writing '%s'\n", outpath);
                continue;
            }
            built++;
        }

        if (built == 0) {
            fprintf(stderr, "No matching revisions/variants found for the series.\n");
            cJSON_Delete(root_all);
            free(json_data);
            return EXIT_FAILURE;
        }

        cJSON_Delete(root_all);
        free(json_data);
        return EXIT_SUCCESS;
    }

    /* If revision specified, try to select the correct variant */
    platform_desc_t final_desc = base_desc;
    if (rev_key && *rev_key) {
        uint16_t want_minor=0, want_major=0;
        if (!parse_rev_string(rev_key, &want_minor, &want_major)) {
            fprintf(stderr, "Invalid --revision format. Use minor.major (e.g., 1.21)\n");
            cJSON_Delete(root_all);
            free(json_data);
            return EXIT_FAILURE;
        }

        bool applied = false;

        /* Look for a sibling object in same series with matching rev */
        for (cJSON *child = root_all->child; child; child = child->next) {
            if (!cJSON_IsObject(child)) continue;
            if (!series_match(child, series_model_id, series_model_string))
                continue;

            cJSON *rmin = cJSON_GetObjectItem(child, "revision_minor");
            cJSON *rmaj = cJSON_GetObjectItem(child, "revision_major");
            if (cJSON_IsNumber(rmin) && cJSON_IsNumber(rmaj) &&
                (uint16_t)rmin->valueint == want_minor &&
                (uint16_t)rmaj->valueint == want_major) {

                final_desc = base_desc; /* start from base */
                if (apply_fields_from_json(child, child->string ? child->string : "variant", &final_desc) != 0) {
                    fprintf(stderr, "Error applying variant fields.\n");
                    cJSON_Delete(root_all);
                    free(json_data);
                    return EXIT_FAILURE;
                }
                applied = true;
                break;
            }
        }

        if (!applied) {
            fprintf(stderr, "Revision %s not found for series (model_id=%u, model_string=%s)\n",
                    rev_key, series_model_id, series_model_string);
            cJSON_Delete(root_all);
            free(json_data);
            return EXIT_FAILURE;
        }
    }

    /* Single-file write */
    if (write_desc_to_file(output_path, &final_desc) != 0) {
        cJSON_Delete(root_all);
        free(json_data);
        return EXIT_FAILURE;
    }

    printf("Binary created: %s (board: %s, rev %u.%u)\n",
           output_path, board_name, final_desc.revision_minor, final_desc.revision_major);

    cJSON_Delete(root_all);
    free(json_data);
    return EXIT_SUCCESS;
}
