#include "output_utils.h"
#include <sys/stat.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>

#ifdef _WIN32
  #include <direct.h>
  #define strcasecmp _stricmp
#endif

bool ou_is_directory(const char *path)
{
    struct stat st;
    if (!path) return false;
    if (stat(path, &st) != 0) return false;
    return S_ISDIR(st.st_mode);
}

void ou_join_path(char *dst, size_t dstsz, const char *dir_or_prefix, const char *leaf, const char *ext_if_needed)
{
    if (!dir_or_prefix || !*dir_or_prefix) {
        snprintf(dst, dstsz, "%s%s", leaf, (ext_if_needed ? ext_if_needed : ""));
        return;
    }
    if (ou_is_directory(dir_or_prefix)) {
    #ifdef _WIN32
        const char sep = '\\';
    #else
        const char sep = '/';
    #endif
        snprintf(dst, dstsz, "%s%c%s%s", dir_or_prefix, sep, leaf, (ext_if_needed ? ext_if_needed : ""));
    } else {
        snprintf(dst, dstsz, "%s", dir_or_prefix);
    }
}

void ou_ensure_bin_ext(char *path, size_t sz)
{
    if (!path || !*path) return;
    size_t n = strlen(path);
    if (n >= 4) {
        const char *tail = path + (n - 4);
        if (strcasecmp(tail, ".bin") == 0) return;
    }
    strncat(path, ".bin", sz - strlen(path) - 1);
}

int ou_write_desc_to_file(const char *path, const platform_desc_t *desc)
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
