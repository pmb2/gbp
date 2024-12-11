/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
  ],
  darkMode: false,
  theme: {
    extend: {
      fontSmoothing: {
        'antialiased': ['antialiased'],
      },
      backgroundColor: {
        light: {
          primary: '#ffffff',
          secondary: '#f3f4f6',
          card: '#ffffff',
          hover: '#f9fafb',
          accent: '#3B82F6'
        },
        dark: {
          primary: '#000000',
          secondary: '#111111',
          card: '#111111', 
          hover: '#1a1a1a',
          accent: '#3B82F6'
        }
      },
      textColor: {
        light: {
          primary: '#111827',
          secondary: '#4b5563',
          muted: '#6b7280'
        },
        dark: {
          primary: '#ffffff',
          secondary: '#d1d5db',
          muted: '#9ca3af'
        }
      },
      borderColor: {
        light: {
          default: '#e5e7eb',
          hover: '#d1d5db'
        },
        dark: {
          default: '#262626',
          hover: '#404040'
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
