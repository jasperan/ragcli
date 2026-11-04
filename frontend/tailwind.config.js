/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Instrument Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        paper: {
          DEFAULT: '#F7F4EE',
          card: '#FDFBF7',
          sunken: '#F1EDE5',
          line: '#E3DCD0',
        },
        ink: {
          DEFAULT: '#1F1B16',
          secondary: '#57504A',
          muted: '#7A7268',
        },
        wax: {
          DEFAULT: '#B3341F',
          dim: '#8E2716',
          soft: '#F4E3DD',
        },
        positive: '#15803D',
        negative: '#B42318',
      },
      maxWidth: {
        shell: '1440px',
      },
      transitionTimingFunction: {
        standard: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
}
