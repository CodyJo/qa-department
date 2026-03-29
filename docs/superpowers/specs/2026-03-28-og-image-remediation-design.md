# OG Image & Favicon Remediation System

## Summary

A Back Office remediation tool that audits and generates Open Graph images, favicons, and social meta tags across all Cody Jo Method projects. Produces enticing SVG source files, converts them to raster PNGs, and ensures every site has proper social previews, favicons, and meta tags.

## Problem

- CertStudy has no favicon; manifest references missing icon files
- Cordivent's PWA icons show Selah's branding (leftover from scaffold)
- codyjo.com uses a single generic OG image for all 11+ product pages
- Existing OG SVGs across apps are plain text-on-background — not enticing
- Game pages (Hydration Hustle, Cthulhu Fact Frenzy) have no dedicated promo images
- No repeatable process to regenerate these assets when branding changes

## Scope

### Sites covered

| Site | Domain | Framework |
|------|--------|-----------|
| The New Beautiful Me | thenewbeautifulme.com | Next.js 16 |
| Selah | selah.codyjo.com | Next.js 16 |
| Fuel | fuel.codyjo.com | Next.js 16 |
| CertStudy | study.codyjo.com | Next.js 16 |
| Cordivent | cordivent.com | Next.js 16 |
| codyjo.com | www.codyjo.com | Astro 5 |

### Deliverables per site

1. OG image SVG source (`public/og.svg` — matches existing convention in TNBM, Selah, Cordivent)
2. OG image PNG raster (`public/og-image.png`, 1200x630)
3. Favicon SVG (if missing)
4. PWA icons 192x192 and 512x512 PNG (if missing or wrong)
5. Meta tag fixes in layout files

### File naming convention

Existing apps (TNBM, Selah, Cordivent) already use `og.svg` as the SVG source and `og-image.png` as the raster. New and updated files follow this same convention. The old `og.svg` files in TNBM, Selah, and Cordivent are replaced in-place with the new designs.

### Additional deliverables

- Game promo OG images for Fuel (Hydration Hustle) and CertStudy (Cthulhu Fact Frenzy)
- Per-product OG images for codyjo.com product pages (~11 images)
- Back Office remediation script + make target

## OG Image Design System

### Shared structure (1200x630 SVG)

All OG images follow a consistent template:

1. **Background**: Dark gradient (per-app colors)
2. **Grid overlay**: Subtle grid pattern in accent color at 3% opacity, 40px spacing
3. **Radial glow**: 500px radial gradient behind icon area at 12% accent opacity
4. **Top accent bar**: 4px gradient line across top edge
5. **Icon**: Lucide SVG path, centered, 80px, in accent color
6. **App name**: 72px bold white text, centered
7. **Tagline**: 26px muted text, centered
8. **Feature badges**: Pill-shaped badges in accent color (10% bg, 20% border)
9. **URL**: 16px muted text at bottom

### Per-site specifications

| Site | BG Gradient | Accent Colors | Icon Source | Badges |
|------|------------|---------------|-------------|--------|
| TNBM | #0c0a1a to #1a1530 | #8B5CF6 to #D4A055 | Moon/stars from moon-favicon.svg | Tarot, Journaling, Insights, Daily Card |
| Selah | #0f152a to #131a2e | #4A8FE7 to #8AB6FF | Cross from favicon.svg | Scripture, Study, Reflection, Journal |
| Fuel | #0a0a0f solid | #22c55e | Flame (lucide) | Nutrition, Workouts, Wellness, AI Insights |
| CertStudy | #0a0f14 to #101820 | #00d4aa | GraduationCap (lucide) | Study Plans, Practice Tests, AI Tutor, Games |
| Cordivent | #0c0e14 to #14171f | #6366f1 to #a78bfa | CalendarDays (lucide) | Events, QR Badges, Galleries, Role Access |
| codyjo.com | #050505 to #0a0a0f | #ffffff (neutral) | Existing logo mark | Per-product |

### Game promo cards

Same template structure but with game-specific theming:

**Hydration Hustle** (Fuel):
- Colors: Fuel green #22c55e + water blue #38bdf8
- Visual: Llama silhouette + water droplet illustration
- Title: "Hydration Hustle"
- Subtitle: "Tap the llama. Keep the droplet alive."
- Badge: "Play Free" in blue accent
- URL: fuel.codyjo.com/games/hydration-hustle
- Note: Fuel already has dynamic `opengraph-image.tsx` files at `/games/` and `/games/hydration-hustle/` using Next.js `ImageResponse`. These generate OG images at build time. Replace them with static SVG+PNG approach for consistency. Remove the `opengraph-image.tsx` files and add explicit `images` to the page metadata instead.

**Cthulhu Fact Frenzy** (CertStudy):
- Colors: CertStudy teal #00d4aa + eldritch purple #7c3aed
- Visual: Tentacle + quiz card illustration
- Title: "Cthulhu Fact Frenzy"
- Subtitle: "Fact or fake? 45 seconds. No mercy."
- Badge: "Play Free" in purple accent
- URL: study.codyjo.com/games
- Note: CertStudy's game lives at `/games` (inline, no sub-route)

### codyjo.com per-product OG images

Each product page on codyjo.com gets an OG image matching the individual app's OG design. Files placed at `/public/images/og-{slug}.png`:

- og-fuel.png
- og-certstudy.png
- og-selah.png
- og-tnbm-tarot.png
- og-cordivent.png
- og-back-office.png
- og-analogify.png
- og-chromahaus.png
- og-pattern.png
- og-search.png
- og-continuum.png

Each product page passes `ogImage` to its layout. This requires modifying `ProductPage.astro` to accept and forward an `ogImage` prop to `Base.astro` (which already supports it). Currently ProductPage only passes `title`, `description`, and `schema`.

Change in `src/components/ProductPage.astro`:
1. Add `ogImage?: string` to the Props interface
2. Destructure `ogImage` from `Astro.props`
3. Forward it: `<Base title={title} description={description} ogImage={ogImage} schema={schema}>`

Then each product page (e.g., `fuel.astro`) passes `ogImage="/images/og-fuel.png"`.

Non-product pages (home, about, collaborate, privacy, 404) continue using the default `og-cody-jo-method.jpg`.

## Favicon Fixes

### CertStudy (create new)

- `public/favicon.svg`: GraduationCap lucide icon, stroke #00d4aa, on #0a0f14 background
- `public/icon-192.png`: Rasterized from favicon SVG at 192x192
- `public/icon-512.png`: Rasterized from favicon SVG at 512x512
- Add `<link rel="icon">` to layout.tsx

### Cordivent (replace wrong icons)

- `public/favicon.svg`: CalendarDays lucide icon, stroke #6366f1, on #0c0e14 background
- `public/icon-192.png`: Rasterized from favicon SVG (replacing Selah-branded version)
- `public/icon-512.png`: Rasterized from favicon SVG (replacing Selah-branded version)
- Ensure favicon.svg is referenced via the icons metadata config in layout.tsx (see Meta Tag Fixes section)

## Meta Tag Fixes

### CertStudy

- Title: "CertStudy" becomes "CertStudy — AI Certification Study Platform"
- Spread `buildAppMetadata` and add icons config to the metadata export in layout.tsx:
  ```typescript
  export const metadata: Metadata = {
    ...buildAppMetadata(siteConfig, {
      title: 'CertStudy — AI Certification Study Platform',
      description: 'AI-powered certification study platform',
      imageAlt: 'CertStudy — AI-powered certification study platform',
    }),
    icons: {
      icon: '/favicon.svg',
      shortcut: '/favicon.svg',
      apple: '/icon-192.png',
    },
  };
  ```
- CertStudy's manifest.json already references `/icon-192.png` and `/icon-512.png` at the correct paths — just need to create the files
- Existing `og-image.png` will be overwritten with the new raster output

### Cordivent

- Add icons config to the metadata export in layout.tsx (Cordivent uses a raw metadata object, so add `icons` as a new property):
  ```typescript
  icons: {
    icon: '/favicon.svg',
    shortcut: '/favicon.svg',
    apple: '/icon-192.png',
  },
  ```
- Existing `icon-192.png` and `icon-512.png` will be overwritten (currently Selah-branded)
- Existing `og-image.png` will be overwritten with the new raster output

### codyjo.com

- Each product page in `src/pages/` gets `ogImage: '/images/og-{slug}.png'` in frontmatter
- Base.astro already supports per-page ogImage override

## Back Office Integration

### Files

- `agents/og-remediation.sh` -- Shell launcher (follows fix-bugs.sh pattern)
- `agents/prompts/og-remediation.md` -- System prompt with design system specs
- `lib/og-standards.md` -- Reference: OG image requirements, meta tag patterns, favicon specs
- `scripts/svg-to-png.mjs` -- Node script using @resvg/resvg-js for batch SVG-to-PNG conversion
- `package.json` -- Created at back-office root for Node script dependencies (only @resvg/resvg-js)

### Font handling

SVG text elements use `system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif` font stack. The `@resvg/resvg-js` renderer uses system fonts available on the build machine. For consistent rendering across environments, the SVGs embed font-weight and font-size explicitly. The rendered output will use whatever sans-serif font is available — this is acceptable since the OG images are generated once and committed as PNGs.

### Make target

```makefile
og-remediate:
	@bash agents/og-remediation.sh $(TARGET)
```

### Conversion script (`scripts/svg-to-png.mjs`)

- Input: directory path containing SVG files
- Output: PNG files alongside SVGs
- Sizes: 1200x630 for OG images, 192x192 and 512x512 for favicons
- Dependency: @resvg/resvg-js (pure Rust WASM, no native deps)

### Flow

1. `make og-remediate TARGET=~/projects/fuel`
2. Agent scans target for OG/favicon status
3. Generates/updates SVG source files in `public/`
4. Runs `svg-to-png.mjs` to produce raster versions
5. Updates meta tags in layout files if needed
6. Writes results to `results/<repo>/og-remediation.json`

### Output JSON schema (`og-remediation.json`)

```json
{
  "repo_name": "fuel",
  "remediated_at": "ISO-8601",
  "summary": {
    "og_images_created": 1,
    "og_images_updated": 1,
    "favicons_created": 0,
    "pwa_icons_created": 0,
    "meta_tags_fixed": 0
  },
  "actions": [
    {
      "type": "og_image_created|og_image_updated|favicon_created|pwa_icon_created|meta_tag_fixed",
      "file": "public/og-image.png",
      "description": "Generated OG image from og.svg"
    }
  ]
}
```

### Cleanup

When replacing OG images, remove stale files:
- Fuel: remove `public/og-template.html` (HTML template previously used to generate OG images via browser screenshot — replaced by SVG approach)
- Fuel: remove `src/app/games/opengraph-image.tsx` and `src/app/games/hydration-hustle/opengraph-image.tsx` (dynamic Next.js ImageResponse generators — replaced by static images)
- Fuel: existing `og-image.png` will be overwritten with new raster output

## What is NOT in scope

- Animated or dynamic OG images (server-rendered per-page)
- OG images for individual blog posts on codyjo.com
- Redesigning existing favicons that are already correct (TNBM, Selah, Fuel)
- Dashboard panel in Back Office HQ (this is a remediation tool, not an audit department)
- Changes to analogify/galleries.codyjo.com (production, requires explicit approval)
