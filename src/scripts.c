#include "global.h"

SCRIPT_DATA const u32 std_scripts[] = INCBIN_U32("script_en/std_scripts.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_0_script[] = INCBIN_U8("script_en/scenario_0_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_1_0_script[] = INCBIN_U8("script_en/scenario_1_0_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_1_1_script[] = INCBIN_U8("script_en/scenario_1_1_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_1_2_script[] = INCBIN_U8("script_en/scenario_1_2_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_1_3_script[] = INCBIN_U8("script_en/scenario_1_3_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_2_0_script[] = INCBIN_U8("script_en/scenario_2_0_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_2_1_script[] = INCBIN_U8("script_en/scenario_2_1_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_2_2_script[] = INCBIN_U8("script_en/scenario_2_2_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_2_3_script[] = INCBIN_U8("script_en/scenario_2_3_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_2_4_script[] = INCBIN_U8("script_en/scenario_2_4_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_2_5_script[] = INCBIN_U8("script_en/scenario_2_5_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_3_0_script[] = INCBIN_U8("script_en/scenario_3_0_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_3_1_script[] = INCBIN_U8("script_en/scenario_3_1_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_3_2_script[] = INCBIN_U8("script_en/scenario_3_2_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_3_3_script[] = INCBIN_U8("script_en/scenario_3_3_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_3_4_script[] = INCBIN_U8("script_en/scenario_3_4_script.phscr");
SCRIPT_DATA __attribute__((aligned(4))) const u8 scenario_3_5_script[] = INCBIN_U8("script_en/scenario_3_5_script.phscr");

// English patch: the size of each scenario script (same order as
// gScriptTable), so a save made with another build can be checked against
// the script it lands in (vwf.c). Kept after the scripts so they don't move.
SCRIPT_DATA const u32 gScriptSizes[] = {
    sizeof(scenario_0_script),
    sizeof(scenario_1_0_script), sizeof(scenario_1_1_script), sizeof(scenario_1_2_script), sizeof(scenario_1_3_script),
    sizeof(scenario_2_0_script), sizeof(scenario_2_1_script), sizeof(scenario_2_2_script),
    sizeof(scenario_2_3_script), sizeof(scenario_2_4_script), sizeof(scenario_2_5_script),
    sizeof(scenario_3_0_script), sizeof(scenario_3_1_script), sizeof(scenario_3_2_script),
    sizeof(scenario_3_3_script), sizeof(scenario_3_4_script), sizeof(scenario_3_5_script),
};
