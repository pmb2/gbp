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
          card: '#2d2d2d',
          hover: '#3d3d3d',
          accent: '#3b82f6'
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
