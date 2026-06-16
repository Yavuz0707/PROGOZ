---
name: Obsidian Sentinel
colors:
  surface: '#141313'
  surface-dim: '#141313'
  surface-bright: '#3a3939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353434'
  on-surface: '#e5e2e1'
  on-surface-variant: '#c4c7c8'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#8e9192'
  outline-variant: '#444748'
  surface-tint: '#c6c6c7'
  primary: '#ffffff'
  on-primary: '#2f3131'
  primary-container: '#e2e2e2'
  on-primary-container: '#636565'
  inverse-primary: '#5d5f5f'
  secondary: '#c9c6c5'
  on-secondary: '#313030'
  secondary-container: '#4a4949'
  on-secondary-container: '#bab8b7'
  tertiary: '#ffffff'
  on-tertiary: '#2f3131'
  tertiary-container: '#e2e2e2'
  on-tertiary-container: '#636565'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e2e2e2'
  primary-fixed-dim: '#c6c6c7'
  on-primary-fixed: '#1a1c1c'
  on-primary-fixed-variant: '#454747'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c9c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474646'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c6c7'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#141313'
  on-background: '#e5e2e1'
  surface-variant: '#353434'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  headline-sm:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
  body-lg:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  container-padding-mobile: 16px
  container-padding-desktop: 32px
  gutter: 16px
  section-gap: 40px
  stack-gap: 12px
---

## Brand & Style
The design system is engineered for high-stakes security environments where clarity and rapid cognition are paramount. It adopts a **Minimalist** approach with a strict monochromatic foundation, eliminating visual noise to ensure that the user's attention is directed solely toward critical data and system alerts. 

The aesthetic is inspired by high-end professional tools: austere, authoritative, and precise. By utilizing a "Dark Mode Only" architecture, the design system minimizes eye strain during prolonged monitoring sessions and creates a sophisticated, cinematic atmosphere. The tone is serious and utilitarian, prioritizing information density and structural hierarchy over decorative elements.

## Colors
This design system employs a strict, low-luminance palette to maintain a professional "command center" feel. 

- **Monochromatic Core:** The interface is built on absolute black (#000000) to ensure perfect contrast with text and borders. Surfaces and cards use subtle increments of gray to create depth without relying on shadows.
- **Accents:** Color is used exclusively as a functional tool for incident categorization. 
    - **Red (#ff3b30):** Immediate threat / Active conflict.
    - **Orange (#ff9500):** Escalated risk / Possible conflict.
    - **Yellow (#ffcc00):** Suspicious activity / Manual review required.
- **Strict Adherence:** No gradients or secondary brand colors are permitted. Grayscale is the only language for navigation and state, ensuring that any splash of color is immediately perceived as an actionable alert.

## Typography
Typography is the primary driver of the visual hierarchy in this design system. We use **Geist** for its technical precision and readability in high-density data environments. 

- **Hierarchy:** Large, bold headlines are used for system status and section headers. 
- **Monospaced Accents:** **JetBrains Mono** is introduced for labels, timestamps, and camera IDs to evoke a sense of technical logging and to ensure numerical data remains legible and aligned.
- **Mobile Scaling:** For mobile viewports, `display-lg` and `headline-lg` should scale down by 20% to maintain a comfortable reading width while preserving the "bold" typographic character.
- **Negative Space:** Type is given ample breathing room, utilizing wide margins to prevent the interface from feeling cluttered despite the dark theme.

## Layout & Spacing
The layout follows a structured **Fixed Grid** philosophy on desktop and a fluid, single-column approach on mobile. 

- **Grid:** A 12-column grid is used for desktop monitoring dashboards, allowing for side-by-side camera feeds and data streams.
- **Spacing Rhythm:** Based on an 8px scale. Component internal padding should be generous (20px-24px) to create the "Apple-style" airy feel.
- **Negative Space:** Use "macro-whitespace" (black space) between major sections to define boundaries rather than using heavy fills. 
- **Breakpoints:**
    - Mobile: < 768px (1 column, 16px margins)
    - Tablet: 768px - 1024px (6 columns, 24px margins)
    - Desktop: > 1024px (12 columns, 32px margins)

## Elevation & Depth
In this design system, depth is communicated through **Tonal Layering** and **1px Outlines** rather than traditional shadows.

- **Stacking Logic:** 
    - Level 0 (Background): #000000
    - Level 1 (Surface/Sidebar): #0d0d0d
    - Level 2 (Cards/Modals): #161616
- **Borders:** All elevated elements (cards, inputs, dropdowns) must feature a 1px solid border (#2a2a2a). This provides crisp definition against the true black background.
- **No Shadows:** Shadows are strictly prohibited to maintain a flat, modern digital-interface aesthetic.
- **Glassmorphism:** Do not use backdrop blurs or transparency. Surfaces must be opaque to ensure maximum legibility of the data they contain.

## Shapes
The shape language is sophisticated and modern, using a consistent corner radius to soften the technical nature of the application.

- **Cards & Containers:** Use a 16px to 20px radius (`rounded-lg` to `rounded-xl` equivalent) to create a premium, hardware-inspired look.
- **Interactive Elements:** Buttons and input fields follow the same radius for consistency.
- **Icons:** Use thin-stroke (1px or 1.5px) outline icons. Icons should be drawn from the SF Symbols library or similar technical outline sets, maintaining a consistent weight across all sizes.

## Components
Consistent component behavior is vital for a reliable monitoring experience.

- **Buttons:**
    - **Active/Primary:** Pure white background (#ffffff) with black text (#000000). High contrast, immediate visibility.
    - **Passive/Secondary:** Transparent background with a 1px border (#2a2a2a) and white text.
- **Alarm Badges:** Small, pill-shaped indicators using the alarm colors (Red, Orange, Yellow). Text inside should be black for maximum legibility against the bright background.
- **Input Fields:** 1px border (#2a2a2a) with #0d0d0d background. On focus, the border changes to #ffffff.
- **Cards:** Used for camera feeds or data widgets. Flat #161616 background with 1px #2a2a2a border. No header fill; titles should sit directly on the card surface.
- **Live Feed Indicators:** A simple 8px circle using the alert colors to signify status, placed in the top right of camera feed cards.
- **Lists:** Clean rows separated by 1px #2a2a2a dividers. No alternating row colors.