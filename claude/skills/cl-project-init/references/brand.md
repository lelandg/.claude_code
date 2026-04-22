# Company Brand Guidelines (Example)

> This is a sanitized example template. Replace "YourCompany", colors, fonts, and conventions with your own brand system.


## Company Info
- **Company**: YourCompany
- **Domain**: yourdomain.com
- **Products**: ProductOne, ProductTwo, ProductThree
- **Contact**: contact@yourdomain.com

## Colors

### Primary Brand
| Token | Hex | Use |
|-------|-----|-----|
| `brand-cyan` | `#00D4FF` | Primary CTA, highlights, glows |
| `brand-cyan-light` | `#00BCD4` | Hover states, secondary highlights |
| `brand-cyan-dark` | `#0099CC` | Active states |
| `brand-navy` | `#0A0E27` | Backgrounds, dark surfaces |
| `brand-navy-light` | `#1a1e3f` | Cards, elevated surfaces |
| `brand-navy-dark` | `#050711` | Deepest background |

### Rainbow Spectrum
The brand includes a full spectrum for product differentiation and UI variety:
```
magenta: #FF1493   pink: #E91E63    purple: #9C27B0   violet: #673AB7
blue: #2196F3      blue-light: #03A9F4  cyan: #00BCD4
green: #4CAF50     green-light: #8BC34A  lime: #CDDC39
yellow: #FFEB3B    amber: #FFC107    orange: #FF9800
orange-deep: #FF5722   red: #F44336
```

Use spectrum colors for:
- Product logos and accent colors
- Data visualization
- Feature badges and tags
- Gradient backgrounds

## Typography
| Role | Font | Import |
|------|------|--------|
| Body/UI | Roboto | Google Fonts |
| Display/Headings | Limelight | Google Fonts |

```css
/* CSS variable names used in Next.js layout */
font-sans: var(--font-roboto)
font-heading: var(--font-limelight)
```

## Dark Mode
- Default is **dark mode** (navy backgrounds)
- Tailwind `darkMode: 'class'` strategy
- Light mode supported via `class` toggle

## Animations
Standard animation tokens:
- `animate-fade-in` — 0.5s ease-in opacity
- `animate-slide-up` — 0.5s ease-out translate + opacity
- `animate-glow` — 2s infinite cyan box-shadow pulse
- `animate-bounce-dot` — chat loading indicator

## Tailwind Config Setup
For new projects, copy from your main project's tailwind config:
```ts
// tailwind.config.ts — core brand setup
colors: {
  'brand-cyan': { DEFAULT: '#00D4FF', light: '#00BCD4', dark: '#0099CC' },
  'brand-navy': { DEFAULT: '#0A0E27', light: '#1a1e3f', dark: '#050711' },
  'spectrum': { /* full spectrum */ }
}
fontFamily: {
  sans: ['var(--font-roboto)', 'Roboto', 'sans-serif'],
  heading: ['var(--font-limelight)', 'Limelight', 'sans-serif'],
}
```

## Logo & Assets
- Logo files live in main project under `public/`
- Favicon: multi-size `.ico` in `public/`
- Use consistent mascot/brand imagery for marketing materials

## UI Patterns
- Cards: dark navy background, subtle cyan border or glow on hover
- Buttons (primary): cyan background, navy text
- Buttons (secondary): navy background, cyan border + text
- Gradients: navy → navy-light, or cyan → blue spectrum sweeps
- Glass effect: `backdrop-blur` + semi-transparent navy overlay
