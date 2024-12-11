/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontSmoothing: {
        'antialiased': ['antialiased'],
      },
      backgroundColor: {
        dark: {
          primary: '#1a1a1a',
          secondary: '#2d2d2d',
        }
      },
      textColor: {
        dark: {
          primary: '#ffffff',
          secondary: '#a0aec0',
        }
      }
    },
  },
  plugins: [],
  future: {
    removeDeprecatedGapUtilities: true,
    purgeLayersByDefault: true,
  },
  corePlugins: {
    preflight: true,
  },
  experimental: {
    optimizeUniversalDefaults: true
  }
}
