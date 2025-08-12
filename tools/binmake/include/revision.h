#ifndef REVISION_H
#define REVISION_H
#include <stdint.h>
#include <stdbool.h>

/* Parse "MAJOR.MINOR" into out_major/out_minor */
bool parse_rev_string(const char *s, uint16_t *out_major, uint16_t *out_minor);

#endif
