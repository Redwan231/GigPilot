import type { Config } from "tailwindcss";

// Minimal config to boot the app. The full semantic design-token system
// (03_UI_Spec.md §2-4) is wired up in task P3-1.
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
