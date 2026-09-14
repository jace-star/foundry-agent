import { defineConfig, presetWind4, transformerDirectives } from "unocss";
import { presetBlock } from "unocss-preset-block";
import { presetPalette } from "unocss-preset-palette";

export default defineConfig({
  presets: [
    presetWind4(),
    presetBlock(),
    presetPalette({
      colorFormat: "rgb",
      themeColors: {
        "primary": [59, 130, 246],
        "primary-hover": [37, 99, 235],
        "primary-light": [239, 246, 255],
        "success": [34, 197, 94],
        "fail": [255, 72, 72],
        "warning": [245, 158, 11],
        "danger": [239, 68, 68],
        "back": [255, 255, 255],
        "grey": [148, 163, 184],
        "regular": [100, 116, 139],
        "standard": [51, 65, 85],
        "neutral": [248, 250, 252],
        "boundary": [241, 245, 249],
        "sidebar": [255, 255, 255],
        "sidebar-hover": [232, 239, 255],
      },
      cssVarName: "color-[name]",
    }),
  ],
  shortcuts: {
    "page-wrapper": "pb-24 px-6 pt-4 relative h-full",
    "page-footer": "absolute flex justify-center bottom-0 left-0 right-0 items-center h-24",
  },
  rules: [
    [
      "text-justify-last",
      {
        "text-align-last": "justify",
        "text-align": "justify",
      },
    ],
    [
      /divider-(x|y)/,
      ([_]) => {
        return {
          "--divider-width": "0.5px",
          "--divider-color": "currentColor",
          "--divider-style": "solid",
          "border-width": "var(--divider-width)",
          "border-color": "var(--divider-color)",
          "border-style": "var(--divider-style)",
        };
      },
      {
        autocomplete: ["divider-(x|y)"],
      },
    ],
    [
      /divider-(dashed|dotted|solid)/,
      ([_, style]) => {
        return {
          "--divider-style": style,
        };
      },
      {
        autocomplete: ["divider-(dashed|dotted|solid)"],
      },
    ],
  ],
  transformers: [
    transformerDirectives({
      applyVariable: ["--at-apply", "--uno-apply", "--uno"],
    }),
  ],
});
