/**
 * Tailwind config for the compiled production build (see docs/TAILWIND_BUILD.md).
 *
 * `theme.extend` is copied verbatim from the old Play-CDN inline config that used to live in
 * app/templates/partials/tailwind_head.html — same tokens, same values, so the compiled output
 * renders pixel-identical to what the CDN produced. If a design token changes, change it here
 * (the one place) and rebuild; nothing else references these values.
 */
module.exports = {
  content: [
    "./app/templates/**/*.html",
  ],
  // A handful of admin "chip" macros build their Tailwind class names at render time
  // (`bg-{{ tone }}-100 text-{{ tone }}-700` in app/templates/admin/{ds260_prep,itin_case,
  // w7_prep}.html) — the literal compound class string never appears anywhere in the template
  // source, so Tailwind's content scanner can never find it on its own. Every `tone` value
  // those macros are actually called with (slate/red/amber/emerald — verified by grepping every
  // call site) is safelisted here. If a new tone color is ever introduced at a call site, add
  // its two classes here too, or that chip will silently render unstyled.
  safelist: [
    "bg-slate-100", "text-slate-700",
    "bg-red-100", "text-red-700",
    "bg-amber-100", "text-amber-700",
    "bg-emerald-100", "text-emerald-700",
  ],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: {
        /* Deep navy — headings, navigation, dark surfaces, trust */
        brand: {
          50: "#eef1f6", 100: "#d7deea", 300: "#8b9bbd",
          500: "#2d3f61", 600: "#1c2c4a", 700: "#141f38",
          800: "#0f1829", 900: "#0a1120",
        },
        /* OG cyan — primary actions, selected states, icons, accents */
        accent: {
          50: "#e6fbff", 100: "#c6f4fe", 200: "#93e8fb", 400: "#3fd0f3", 500: "#12c0ee",
          600: "#0aa3cf", 700: "#0a83a8",
        },
        /* Very light cyan/blue — secondary surfaces, grouped cards */
        mist: {
          50: "#f4fbfd", 100: "#e8f6fb", 200: "#d3edf6", 300: "#b7e0ee",
        },
        /* Neutral light grey — section separation */
        fog: { 50: "#f7f9fb", 100: "#f0f3f7", 200: "#e4e9f0" },
        /* WhatsApp green — WhatsApp actions only */
        wa: { DEFAULT: "#25D366", 600: "#1fbd5a", 700: "#128C4A" },
        /* Warm gold — OG Academy sub-brand only */
        academy: {
          50: "#fdf6e8", 100: "#f7e6bb", 500: "#b8860b",
          600: "#9a6f09", 700: "#7c5907",
        },
      },
      borderRadius: { card: "1rem", panel: "1.25rem" },
      boxShadow: {
        card: "0 1px 2px rgba(15,24,41,.04), 0 4px 14px -6px rgba(15,24,41,.10)",
        pop: "0 10px 30px -12px rgba(15,24,41,.25)",
      },
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
  ],
};
