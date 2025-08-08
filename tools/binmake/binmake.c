#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/stat.h>
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
    {"bl2_desc"         , FIELD_UINT_ARRAY  },
    {"bl2_dtb_desc"     , FIELD_UINT_ARRAY  },
    {"u_boot_desc"      , FIELD_UINT_ARRAY  },
    {"u_boot_dtb_desc"  , FIELD_UINT_ARRAY  },
    {"kernel_desc"      , FIELD_UINT_ARRAY  },
    {"kernel_dtb_desc"  , FIELD_UINT_ARRAY  },
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

void write_string(char *dest, const char *src, size_t max_len)
{
    if (src)
    {
        strncpy(dest, src, max_len - 1);
        dest[max_len - 1] = '\0';
    }
    else
    {
        dest[0] = '\0';
    }
}

int parse_uint_array(cJSON *array, uint8_t *out_array, size_t max_len)
{
    if (!cJSON_IsArray(array))
        return -1;

    size_t count = cJSON_GetArraySize(array);
    size_t out_offset = 0;
    memset(out_array, 0, max_len);

    for (size_t array_idx = 0; array_idx < count; ++array_idx)
    {
        cJSON *item = cJSON_GetArrayItem(array, array_idx);
        if (!cJSON_IsString(item) || item->valuestring == NULL)
            return -1;

        uint32_t val = (uint32_t)strtoul(item->valuestring, NULL, 0);

        // Determine minimum size needed
        size_t size = 1;
        if (val > 0xFF)        size = 2;
        if (val > 0xFFFF)      size = 3;
        if (val > 0xFFFFFF)    size = 4;

        if (out_offset + size > max_len)
            return -1;

        for (size_t byte_idx = 0; byte_idx < size; ++byte_idx)
        {
            out_array[out_offset + byte_idx] = (val >> (8 * (size - 1 - byte_idx))) & 0xFF;
        }

        out_offset += size;
    }

    return 0;
}

static int handle_parse_error(const char *field_name, cJSON *root, char *json_data) {
    fprintf(stderr, "Failed to parse array field '%s'\n", field_name);
    cJSON_Delete(root);
    free(json_data);
    return EXIT_FAILURE;
}

void print_help(const char *prog_name) {
    printf("Usage: %s --input=platform_info.json --board=BOARD_NAME --output=BOARD_NAME.bin\n", prog_name);
    printf("Options:\n");
    printf("  --input=FILE      Path to input JSON file containing board information\n");
    printf("  --board=NAME      Board name to select from the JSON file\n");
    printf("  --output=FILE     Path to output binary file\n");
    printf("  -h, --help        Show this help message and exit\n");
}

int main(int argc, char *argv[]) {
    const char *json_path = NULL;
    const char *board_name = NULL;
    const char *output_path = NULL;

    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "--input=", 8) == 0) {
            json_path = argv[i] + 8;
        } else if (strncmp(argv[i], "--board=", 8) == 0) {
            board_name = argv[i] + 8;
        } else if (strncmp(argv[i], "--output=", 9) == 0) {
            output_path = argv[i] + 9;
        } else if ((strcmp(argv[i], "-h") == 0) || (strcmp(argv[i], "--help") == 0)) {
            print_help(argv[0]);
            return EXIT_SUCCESS;
        } else {
            fprintf(stderr, "Unknown option: %s\n", argv[i]);
            print_help(argv[0]);
            return EXIT_FAILURE;
        }
    }    

    if (!json_path || !board_name || !output_path) {
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
        cJSON *child = root_all->child;
        while (child) {
            if (cJSON_IsObject(child)) {
                fprintf(stderr, "  - %s\n", child->string);
            }
            child = child->next;
        }
        cJSON_Delete(root_all);
        free(json_data);
        return EXIT_FAILURE;
    }


    platform_desc_t desc;
    memset(&desc, 0, sizeof(desc));

    for (size_t i = 0; i < sizeof(fields) / sizeof(fields[0]); i++)
    {
        FieldDesc *field = &fields[i];
        cJSON *item = cJSON_GetObjectItem(root, field->key);
        if (!item)
        {
            fprintf(stderr, "Missing field '%s' in JSON for board '%s'\n", field->key, board_name);
            cJSON_Delete(root_all);
            free(json_data);
            return EXIT_FAILURE;
        }

        switch (field->type)
        {
        case FIELD_U8:
            if (!cJSON_IsNumber(item)) {
                fprintf(stderr, "Field '%s' must be a number\n", field->key);
                cJSON_Delete(root_all);
                free(json_data);
                return EXIT_FAILURE;
            }
            uint8_t val = (uint8_t)item->valueint;
            if (strcmp(field->key, "bl2_loc") == 0) {
                desc.bl2_loc = val;
            } else if (strcmp(field->key, "bl2_dtb_loc") == 0) {
                desc.bl2_dtb_loc = val;
            } else if (strcmp(field->key, "u_boot_loc") == 0) {
                desc.u_boot_loc = val;
            } else if (strcmp(field->key, "u_boot_dtb_loc") == 0) {
                desc.u_boot_dtb_loc = val;
            } else if (strcmp(field->key, "kernel_loc") == 0) {
                desc.kernel_loc = val;
            } else if (strcmp(field->key, "kernel_dtb_loc") == 0) {
                desc.kernel_dtb_loc = val;
            } else if (strcmp(field->key, "bl2_id") == 0) {
                desc.bl2_id = val;
            } else if (strcmp(field->key, "bl2_dtb_id") == 0) {
                desc.bl2_dtb_id = val;
            } else if (strcmp(field->key, "u_boot_id") == 0) {
                desc.u_boot_id = val;
            } else if (strcmp(field->key, "u_boot_dtb_id") == 0) {
                desc.u_boot_dtb_id = val;
            } else if (strcmp(field->key, "kernel_id") == 0) {
                desc.kernel_id = val;
            } else if (strcmp(field->key, "kernel_dtb_id") == 0) {
                desc.kernel_dtb_id = val;
            }
            break;
        case FIELD_U16:
            if (!cJSON_IsNumber(item)) {
                fprintf(stderr, "Field '%s' must be a number\n", field->key);
                cJSON_Delete(root_all);
                free(json_data);
                return EXIT_FAILURE;
            }
            if (strcmp(field->key, "revision_minor") == 0)
                desc.revision_minor = (uint16_t)item->valueint;
            else if (strcmp(field->key, "revision_major") == 0)
                desc.revision_major = (uint16_t)item->valueint;
            break;
        case FIELD_U32:
            if (!cJSON_IsNumber(item)) {
                fprintf(stderr, "Field '%s' must be a number\n", field->key);
                cJSON_Delete(root_all);
                free(json_data);
                return EXIT_FAILURE;
            }
            if (strcmp(field->key, "model_id") == 0)
                desc.model_id = (uint32_t)item->valueint;
            break;
        case FIELD_STRING:
            if (!cJSON_IsString(item)) {
                fprintf(stderr, "Field '%s' must be a string\n", field->key);
                cJSON_Delete(root_all);
                free(json_data);
                return EXIT_FAILURE;
            }
            if (strcmp(field->key, "model_string") == 0)
                write_string(desc.model_string, item->valuestring, MAX_SIZE_LEN);
            else if (strcmp(field->key, "mfg_name") == 0)
                write_string(desc.mfg_name, item->valuestring, MAX_SIZE_LEN);
            break;
        case FIELD_UINT_ARRAY:
            if (strcmp(field->key, "bl2_desc") == 0) {
                if (parse_uint_array(item, desc.bl2_desc, MAX_SIZE_LEN) != 0)
                    return handle_parse_error(field->key, root_all, json_data);
            }
            else if (strcmp(field->key, "bl2_dtb_desc") == 0) {
                if (parse_uint_array(item, desc.bl2_dtb_desc, MAX_SIZE_LEN) != 0)
                    return handle_parse_error(field->key, root_all, json_data);
            }
            else if (strcmp(field->key, "u_boot_desc") == 0) {
                if (parse_uint_array(item, desc.u_boot_desc, MAX_SIZE_LEN) != 0)
                    return handle_parse_error(field->key, root_all, json_data);
            }
            else if (strcmp(field->key, "u_boot_dtb_desc") == 0) {
                if (parse_uint_array(item, desc.u_boot_dtb_desc, MAX_SIZE_LEN) != 0)
                    return handle_parse_error(field->key, root_all, json_data);
            }
            else if (strcmp(field->key, "kernel_desc") == 0) {
                if (parse_uint_array(item, desc.kernel_desc, MAX_SIZE_LEN) != 0)
                    return handle_parse_error(field->key, root_all, json_data);
            }
            else if (strcmp(field->key, "kernel_dtb_desc") == 0) {
                if (parse_uint_array(item, desc.kernel_dtb_desc, MAX_SIZE_LEN) != 0)
                    return handle_parse_error(field->key, root_all, json_data);
            }
            break;        
        default:
            fprintf(stderr, "Unknown field type for '%s'\n", field->key);
            cJSON_Delete(root_all);
            free(json_data);
            return EXIT_FAILURE;
        }
    }
    FILE *out = fopen(output_path, "wb");
    if (!out) {     
        perror("Failed to open output file");
        cJSON_Delete(root_all);
        free(json_data);
        return EXIT_FAILURE;
    }

    fwrite(&desc, 1, sizeof(desc), out);
    fclose(out);

    cJSON_Delete(root_all);
    free(json_data);

    printf("Binary created: %s (board: %s)\n", output_path, board_name);
    struct stat st;
    if (stat(output_path, &st) == 0) {
        printf("Output binary size: 0x%lx bytes\n", st.st_size);
    } else {
        perror("Could not determine output file size");
    }

    return EXIT_SUCCESS;
}
