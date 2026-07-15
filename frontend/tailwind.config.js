/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        nws: {
          bg: '#0d0f0a',
          surface: '#141710',
          surface2: '#1b1f16',
          border: '#2a2f23',
          accent: '#7ec850',
          accent2: '#c8e86c',
          warn: '#e8a23c',
          danger: '#e85c4a',
          blue: '#5ca0e8',
          text: '#e8ead4',
          muted: '#8a9077',
        },
      },
      fontFamily: {
        mono: ['var(--font-dm-mono)', 'monospace'],
        display: ['var(--font-syne)', 'sans-serif'],
      },
      borderRadius: {
        card: '16px',
      },
    },
  },
  plugins: [],
}
