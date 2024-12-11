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
          primary: '#111827',
          secondary: '#1F2937',
          card: '#1F2937',
          hover: '#374151',
          accent: '#3B82F6'
        }
      },
      textColor: {
        dark: {
          primary: '#ffffff',
          secondary: '#a0aec0',
          muted: '#6b7280'
        }
      },
      borderColor: {
        dark: {
          default: '#404040',
          hover: '#525252'
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
