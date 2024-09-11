# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2024 Tiny Tapeout
# Author: Uri Shaked

import yaml
import os

info_yaml_path = os.path.join(os.path.dirname(__file__), "../info.yaml")
with open(info_yaml_path, "r") as stream:
    try:
        info = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)

sources = info["project"]["source_files"]
top_module = info["project"]["top_module"]
result = []

header = """
// SPDX-FileCopyrightText: © 2023-2024 Uri Shaked <uri@wokwi.com>
// SPDX-License-Identifier: Apache-2.0

/*
 * Simon Says game in Verilog. Wokwi Simulation project:
 * https://wokwi.com/projects/408757730664700929
 */

`default_nettype none

module wokwi (
    input  CLK,
    input  RST,
    input  BTN0,
    input  BTN1,
    input  BTN2,
    input  BTN3,
    output LED0,
    output LED1,
    output LED2,
    output LED3,
    output SND,
    output SEG_A,
    output SEG_B,
    output SEG_C,
    output SEG_D,
    output SEG_E,
    output SEG_F,
    output SEG_G,
    output DIG1,
    output DIG2
);

  simon simon_inst (
      .clk      (CLK),
      .rst      (RST),
      .ticks_per_milli (16'd50),
      .btn      ({BTN3, BTN2, BTN1, BTN0}),
      .led      ({LED3, LED2, LED1, LED0}),
      .segments_invert(1'b1), // For common anode 7-segment display
      .segments({SEG_G, SEG_F, SEG_E, SEG_D, SEG_C, SEG_B, SEG_A}),
      .segment_digits({DIG2, DIG1}),
      .sound    (SND)
  );

endmodule
""".strip()

# Ensure simon.v is first
sources.remove("simon.v")
sources.insert(0, "simon.v")

for source in sources:
    if source == "project.v":
        continue
    source_path = os.path.join(os.path.dirname(__file__), "../src/" + source)
    with open(source_path, "r") as f:
        code = f.read()
    code = code[code.find("module ") :]
    result.append(code + "\n\n")

print(header + "\n\n" + "".join(result).strip())
