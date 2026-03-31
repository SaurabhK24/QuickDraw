import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/{**,.client,.server}/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        sand: {
          50: "#fdf8f0",
          100: "#f5ebe0",
          200: "#e6d5c1",
          300: "#d4b896",
          400: "#c4956a",
          500: "#b07d52",
          600: "#9a6840",
          700: "#7d5234",
          800: "#5e3d27",
          900: "#3f291a",
          950: "#1f140d",
        },
        neural: {
          trust: "#10b981",
          resistance: "#ef4444",
          engagement: "#3b82f6",
          load: "#f59e0b",
          salience: "#8b5cf6",
        },
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
