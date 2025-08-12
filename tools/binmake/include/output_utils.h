#ifndef OUTPUT_UTILS_H
#define OUTPUT_UTILS_H

#include <stddef.h>
#include <stdbool.h>
#include "platform.h"

/* filesystem helpers */
bool  ou_is_directory(const char *path);
void  ou_join_path(char *dst, size_t dstsz, const char *dir_or_prefix, const char *leaf, const char *ext_if_needed);
void  ou_ensure_bin_ext(char *path, size_t sz);

/* write binary */
int   ou_write_desc_to_file(const char *path, const platform_desc_t *desc);

#endif
