#ifndef JSON_UTILS_H
#define JSON_UTILS_H

#include <stdbool.h>
#include "cJSON.h"
#include "platform.h"

/* Look up a board by model_string (strict) */
cJSON* json_find_board_by_model_string(cJSON *root_all, const char *model_string);

/* Validate all required base fields exist */
int json_validate_base_required(cJSON *board_obj, const char *board_name);

/* Overlay: copy only present fields from obj into desc */
int json_apply_fields_from_obj(cJSON *obj, const char *board_name, platform_desc_t *desc);

/* Do (model_id, model_string) match the base board? */
bool json_series_match(cJSON *obj, uint32_t base_model_id, const char *base_model_string);

/* Print available revisions (major.minor) for series */
void json_print_available_revisions(cJSON *root_all,
                                    uint32_t series_model_id,
                                    const char *series_model_string);

/* Read entire file into a malloc'd, NUL-terminated string. */
char *load_file_as_string(const char *path);

/* Convenience: read + parse JSON in one call. */
cJSON *load_json_from_file(const char *path);

/* Helpers */
const char* json_get_str(cJSON *obj, const char *key);

#endif
