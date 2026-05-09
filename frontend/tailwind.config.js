/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#0C0C14',
          surface: '#131320',
          elevated: '#1A1A2C',
          card: '#1F1F32',
          hover: '#252538',
        },
        primary: {
          DEFAULT: '#8B5CF6',
          light: '#A78BFA',
          dark: '#7C3AED',
          muted: 'rgba(139,92,246,0.15)',
          glow: 'rgba(139,92,246,0.3)',
        },
        accent: {
          DEFAULT: '#06B6D4',
          light: '#22D3EE',
          muted: 'rgba(6,182,212,0.15)',
        },
        border: {
          DEFAULT: 'rgba(139,92,246,0.12)',
          hover: 'rgba(139,92,246,0.3)',
          subtle: 'rgba(255,255,255,0.05)',
        },
        txt: {
          primary: '#F1F0FF',
          secondary: '#A0A0C0',
          muted: '#60607A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      animation: {
        'blink': 'blink 1s step-end infinite',
        'fade-in': 'fadeIn 0.25s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-in-left': 'slideInLeft 0.3s ease-out',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'spin-slow': 'spin 3s linear infinite',
        'shimmer': 'shimmer 2s infinite',
      },
      keyframes: {
        blink: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0' } },
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideInLeft: {
          from: { opacity: '0', transform: 'translateX(-12px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      boxShadow: {
        'glow-sm': '0 0 12px rgba(139,92,246,0.25)',
        'glow': '0 0 24px rgba(139,92,246,0.35)',
        'glow-lg': '0 0 40px rgba(139,92,246,0.4)',
        'card': '0 4px 24px rgba(0,0,0,0.4)',
        'modal': '0 8px 64px rgba(0,0,0,0.6)',
      },
    },
  },
  plugins: [],
}
