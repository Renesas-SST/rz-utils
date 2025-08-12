#include "revision.h"
#include <stdio.h>

bool parse_rev_string(const char *s, uint16_t *out_major, uint16_t *out_minor)
{
    unsigned int major = 0, minor = 0;
    if (!s || sscanf(s, "%u.%u", &major, &minor) != 2)
        return false;
    *out_major = (uint16_t)major;
    *out_minor = (uint16_t)minor;
    return true;
}
