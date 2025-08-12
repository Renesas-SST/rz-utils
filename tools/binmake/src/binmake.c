#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cJSON.h"

#include "platform.h"
#include "revision.h"
#include "json_utils.h"
#include "output_utils.h"

static void print_help(const char *prog_name) {
    printf("Usage:\n");
    printf("  %s --input=platform_info.json --board=MODEL_STRING [--output=OUT]\n", prog_name);
    printf("  %s --input=platform_info.json --board=MODEL_STRING [--output=OUT_DIR] --all-revisions\n", prog_name);
    printf("\nOptions:\n");
    printf("  --input=FILE       Path to input JSON file\n");
    printf("  --board=MODEL      model_string in JSON (e.g. rzg2l-evk)\n");
    printf("  --output=PATH      Output file (single build) or output directory (with --all-revisions)\n");
    printf("  --revision=X.Y     (Optional) select revision (major.minor). Example: 2.0\n");
    printf("  --all-revisions    Build binaries for every JSON object in the same series\n");
    printf("  -h, --help         Show this help\n");
}

int main(int argc, char *argv[])
{
    const char *json_path = NULL;
    const char *board_ms  = NULL;
    const char *output_path = NULL;
    const char *rev_key = NULL;
    int all_revs_mode = 0;

    for (int i = 1; i < argc; i++) {
        if      (strncmp(argv[i], "--input=", 8)    == 0) json_path   = argv[i] + 8;
        else if (strncmp(argv[i], "--board=", 8)    == 0) board_ms    = argv[i] + 8;
        else if (strncmp(argv[i], "--output=", 9)   == 0) output_path = argv[i] + 9;
        else if (strncmp(argv[i], "--revision=",11) == 0) rev_key     = argv[i] + 11;
        else if (strcmp(argv[i], "--all-revisions") == 0) all_revs_mode = 1;
        else if (!strcmp(argv[i], "-h") || !strcmp(argv[i], "--help")) { print_help(argv[0]); return 0; }
        else { fprintf(stderr, "Unknown option: %s\n", argv[i]); print_help(argv[0]); return 1; }
    }

    if (!json_path || !board_ms) { print_help(argv[0]); return 1; }

    /* Read JSON */
    cJSON *root_all = load_json_from_file(json_path);
    if (!root_all) return 1;

    /* Resolve board by model_string */
    cJSON *root = json_find_board_by_model_string(root_all, board_ms);
    if (!root) {
        fprintf(stderr, "Board (model_string) '%s' not found.\nAvailable model_strings:\n", board_ms);
        for (cJSON *child = root_all->child; child; child = child->next) {
            if (!cJSON_IsObject(child)) continue;
            const char *ms = json_get_str(child, "model_string");
            if (ms && *ms) fprintf(stderr, "  - %s\n", ms);
        }
        cJSON_Delete(root_all); return 1;
    }

    const char *effective_name = json_get_str(root, "model_string");

    /* Build base */
    platform_desc_t base_desc; memset(&base_desc, 0, sizeof(base_desc));
    if (json_validate_base_required(root, effective_name) != 0) { cJSON_Delete(root_all); return 1; }
    if (json_apply_fields_from_obj(root, effective_name, &base_desc) != 0) { cJSON_Delete(root_all); return 1; }

    /* Series identity */
    cJSON *mid  = cJSON_GetObjectItem(root, "model_id");
    cJSON *mstr = cJSON_GetObjectItem(root, "model_string");
    uint32_t series_model_id = (uint32_t)(mid ? mid->valueint : 0);
    const char *series_model_string = (mstr && cJSON_IsString(mstr)) ? mstr->valuestring : "";

    /* --all-revisions */
    if (all_revs_mode) {
        printf("Building all revisions for series: model_id=%u, model_string=\"%s\"\n",
               series_model_id, series_model_string);

        int total_revs = 0;
        for (cJSON *child = root_all->child; child; child = child->next)
            if (cJSON_IsObject(child) && json_series_match(child, series_model_id, series_model_string)) total_revs++;

        int built = 0;
        for (cJSON *child = root_all->child; child; child = child->next) {
            if (!cJSON_IsObject(child) || !json_series_match(child, series_model_id, series_model_string)) continue;

            platform_desc_t desc = base_desc;
            if (json_apply_fields_from_obj(child, child->string ? child->string : "variant", &desc) != 0) {
                fprintf(stderr, "Skipping '%s' due to field error\n", child->string ? child->string : "(unnamed)");
                continue;
            }

            char filename[512], outpath[1024];
            if (total_revs > 1) {
                snprintf(filename, sizeof(filename),
                         "%s-ver%u.%u-platform-settings.bin",
                         desc.model_string, desc.revision_major, desc.revision_minor);
            } else {
                snprintf(filename, sizeof(filename), "%s-platform-settings.bin", desc.model_string);
            }

            if (output_path && ou_is_directory(output_path))
                ou_join_path(outpath, sizeof(outpath), output_path, filename, NULL);
            else if (output_path)
                snprintf(outpath, sizeof(outpath), "%s", filename); /* warn & ignore non-dir; keep simple */
            else
                snprintf(outpath, sizeof(outpath), "%s", filename);

            printf("Writing %s (rev %u.%u)\n", outpath, desc.revision_major, desc.revision_minor);
            if (ou_write_desc_to_file(outpath, &desc) != 0) continue;
            built++;
        }

        if (built == 0) {
            fprintf(stderr, "No matching revisions/variants found for the series.\n");
            cJSON_Delete(root_all); return 1;
        }

        cJSON_Delete(root_all); return 0;
    }

    /* single build (+ optional --revision overlay) */
    platform_desc_t final_desc = base_desc;
    if (rev_key && *rev_key) {
        uint16_t want_major=0, want_minor=0;
        if (!parse_rev_string(rev_key, &want_major, &want_minor)) {
            fprintf(stderr, "Invalid --revision format. Use major.minor (e.g., 2.0)\n");
            cJSON_Delete(root_all); return 1;
        }

        bool applied = false;
        for (cJSON *child = root_all->child; child; child = child->next) {
            if (!cJSON_IsObject(child) || !json_series_match(child, series_model_id, series_model_string)) continue;

            cJSON *rmin = cJSON_GetObjectItem(child, "revision_minor");
            cJSON *rmaj = cJSON_GetObjectItem(child, "revision_major");
            if (cJSON_IsNumber(rmaj) && cJSON_IsNumber(rmin) &&
                (uint16_t)rmaj->valueint == want_major &&
                (uint16_t)rmin->valueint == want_minor) {

                final_desc = base_desc;
                if (json_apply_fields_from_obj(child, child->string ? child->string : "variant", &final_desc) != 0) {
                    fprintf(stderr, "Error applying variant fields.\n");
                    cJSON_Delete(root_all); return 1;
                }
                applied = true; break;
            }
        }

        if (!applied) {
            fprintf(stderr, "Revision %s not found for series (model_id=%u, model_string=%s)\n",
                    rev_key, series_model_id, series_model_string);
            json_print_available_revisions(root_all, series_model_id, series_model_string);
            cJSON_Delete(root_all); return 1;
        }
    }

    /* decide output path */
    char out_single[1024] = {0};
    if (!output_path) {
        snprintf(out_single, sizeof(out_single), "%s.bin", effective_name);
        output_path = out_single;
    } else if (ou_is_directory(output_path)) {
        char leaf[512];
        snprintf(leaf, sizeof(leaf), "%s.bin", effective_name);
        ou_join_path(out_single, sizeof(out_single), output_path, leaf, NULL);
        output_path = out_single;
    } else {
        strncpy(out_single, output_path, sizeof(out_single)-1);
        ou_ensure_bin_ext(out_single, sizeof(out_single));
        output_path = out_single;
    }

    if (ou_write_desc_to_file(output_path, &final_desc) != 0) {
        cJSON_Delete(root_all); return 1;
    }

    printf("Binary created: %s (board: %s, rev %u.%u)\n",
           output_path, effective_name, final_desc.revision_major, final_desc.revision_minor);

    cJSON_Delete(root_all);
    return 0;
}
