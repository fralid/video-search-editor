/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                // Semantic Colors (mapped to CSS variables)
                app: 'var(--color-bg-app)',
                panel: 'var(--color-bg-panel)',
                element: 'var(--color-bg-element)',
                main: 'var(--color-text-main)',
                muted: 'var(--color-text-muted)',

                // Functional Colors
                void: '#050505', // Keeping for legacy/specific needs
                charcoal: '#121212',
                plasma: {
                    DEFAULT: 'var(--color-plasma)',
                    glow: 'rgba(126, 206, 242, 0.5)'
                },
                electric: {
                    DEFAULT: 'var(--color-electric)',
                    glow: 'rgba(126, 206, 242, 0.5)'
                },
                cyber: {
                    DEFAULT: 'var(--color-cyber)',
                    glow: 'rgba(126, 206, 242, 0.5)'
                }
            },
            boxShadow: {
                'telegram': '0 4px 12px var(--color-shadow)',
            },
            borderColor: {
                DEFAULT: 'var(--color-border)',
                subtle: 'var(--color-border)',
            },
            fontFamily: {
                sans: ['Outfit', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            boxShadow: {
                'neon-plasma': '0 0 10px rgba(255, 107, 0, 0.3), 0 0 20px rgba(255, 107, 0, 0.1)',
                'neon-blue': '0 0 10px rgba(0, 240, 255, 0.3), 0 0 20px rgba(0, 240, 255, 0.1)',
                'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
            }
        },
    },
    plugins: [],
}
