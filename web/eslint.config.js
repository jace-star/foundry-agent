import { curev } from "@curev/eslint-config";

export default curev({
  ignores: [
    "**/*.md",
    "**/dist/**",
    "**/coverage/**",
    "**/node_modules/**",
  ],
});
