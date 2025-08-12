#ifndef PLATFORM_H
#define PLATFORM_H

#include <stdint.h>

#define MAX_SIZE_LEN 256
#define MAX_MODEL_STRING_LEN 256

typedef struct __attribute__((packed)) platform_desc {
    uint32_t model_id;
    uint32_t revision_minor : 16;   /* printed SECOND */
    uint32_t revision_major : 16;   /* printed FIRST  */
    char     model_string[MAX_MODEL_STRING_LEN];
    char     mfg_name[MAX_SIZE_LEN];

    uint32_t bl2_loc        : 4;
    uint32_t bl2_dtb_loc    : 4;
    uint32_t u_boot_loc     : 4;
    uint32_t u_boot_dtb_loc : 4;
    uint32_t kernel_loc     : 4;
    uint32_t kernel_dtb_loc : 4;
    uint32_t res_loc        : 4;
    uint32_t res1_loc       : 4;

    uint32_t bl2_id         : 4;
    uint32_t bl2_dtb_id     : 4;
    uint32_t u_boot_id      : 4;
    uint32_t u_boot_dtb_id  : 4;
    uint32_t kernel_id      : 4;
    uint32_t kernel_dtb_id  : 4;
    uint32_t res_id         : 4;
    uint32_t res1_id        : 4;

    uint8_t bl2_desc[MAX_SIZE_LEN];
    uint8_t bl2_dtb_desc[MAX_SIZE_LEN];
    uint8_t u_boot_desc[MAX_SIZE_LEN];
    uint8_t u_boot_dtb_desc[MAX_SIZE_LEN];
    uint8_t kernel_desc[MAX_SIZE_LEN];
    uint8_t kernel_dtb_desc[MAX_SIZE_LEN];
} platform_desc_t;

#endif /* PLATFORM_H */
