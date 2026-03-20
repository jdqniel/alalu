/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#0B0E11',
          card: '#161A1E',
          hover: '#1E2329',
          elevated: '#1D2126',
        },
        brand: {
          green: '#0ECB81',
          red: '#F6465D',
          gold: '#F0B90B',
        },
        tx: {
          primary: '#EAECEF',
          secondary: '#848E9C',
          muted: '#5E6673',
        },
        line: '#2B3139',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Space Grotesk', 'monospace'],
      },
    },
  },
  plugins: [],
}
