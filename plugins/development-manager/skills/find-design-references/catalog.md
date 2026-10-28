# Where to look: a starting catalog

This catalog lists places worth searching, not picks. The researchers in step 3 start here, then
search beyond it. A place becomes a pick only once a checker has looked at it against the brief
and written down what to borrow in `references.yaml`.

When a researcher finds a good place that is not listed, the checker adds it here, in the right
section.

Links and licenses were last checked on 2026-10-16. Links were checked by requesting each page.
Licenses come from GitHub's own reading of each repo. "Read its LICENSE" means GitHub could not
name a standard license, so open the file before borrowing anything.

The words in brackets are the `good_for` words from `references.yaml`.

## Design systems with public token files

These are the best references for exact values. Their source holds the real colours, type
sizes and spacing, so we read them rather than guess them from a picture.

| Name | Site | Repo and license | Good for | Look at |
|---|---|---|---|---|
| GitHub Primer | https://primer.style | https://github.com/primer/primitives (MIT) | [sidebar, table, type] | Dense tool UI that stays calm: the nav list, data tables, the type scale |
| IBM Carbon | https://carbondesignsystem.com | https://github.com/carbon-design-system/carbon (Apache-2.0) | [table, forms, stats, type] | Data tables, form fields, the 2px grid, its charts guidance |
| Radix Colors and Themes | https://www.radix-ui.com/themes | https://github.com/radix-ui/colors (MIT), https://github.com/radix-ui/themes (MIT) | [type, forms] | 12-step colour scales with a stated use for each step, in light and dark |
| shadcn/ui | https://ui.shadcn.com | https://github.com/shadcn-ui/ui (MIT) | [sidebar, forms, table, calendar] | Its sidebar and calendar blocks. The default look is very common, so borrow structure, not the look |
| Open Props | https://open-props.style | https://github.com/argyleink/open-props (MIT) | [type] | Ready-made spacing, type and shadow scales as CSS variables |
| GOV.UK Design System | https://design-system.service.gov.uk | https://github.com/alphagov/govuk-frontend (MIT) | [forms, type, review] | Plain-words forms, error messages, a "check your answers" summary |
| US Web Design System | https://designsystem.digital.gov | https://github.com/uswds/uswds (read its LICENSE) | [forms, type] | Readable type at body sizes, form patterns |
| Adobe Spectrum | https://spectrum.adobe.com | https://github.com/adobe/spectrum-design-data (Apache-2.0) | [type, forms] | Token naming, and how a big system splits colour by purpose |
| Microsoft Fluent | https://react.fluentui.dev | https://github.com/microsoft/fluentui (read its LICENSE) | [sidebar, forms] | Nav and command bars in a dense desktop app |
| Mantine | https://mantine.dev | https://github.com/mantinedev/mantine (MIT) | [calendar, forms, stats] | Date pickers, calendars, small charts |
| Shopify Polaris | https://shopify.dev/docs/api/polaris | The old repo is archived (https://github.com/Shopify/polaris-react-archive) | [table, filing, forms] | Admin index tables, filters, bulk actions. Values come from the docs now |
| Tufte CSS | https://edwardtufte.github.io/tufte-css/ | https://github.com/edwardtufte/tufte-css (MIT) | [type, stats, landing] | Editorial reading type, side notes, charts that sit inside the text |

## Open-source apps with something to see

Shoot the live demo or the product site; read the source for values. Never clone or run one.

| Name | Site or demo | Repo and license | Good for | Look at |
|---|---|---|---|---|
| Plausible Analytics | https://plausible.io/plausible.io (a live dashboard) | https://github.com/plausible/analytics (AGPL-3.0) | [stats] | One-screen stats: a headline number row, one chart, ranked lists beside it |
| Umami | https://umami.is | https://github.com/umami-software/umami (MIT) | [stats, sidebar] | A quiet analytics dashboard with a left nav |
| Plane | https://plane.so | https://github.com/makeplane/plane (AGPL-3.0) | [board, table, sidebar] | Board columns, issue lists, the sidebar |
| Nullboard | https://nullboard.io/preview | https://github.com/apankrat/nullboard (read its LICENSE) | [board] | A board with almost no chrome: plain columns, small type, no shadows |
| Focalboard | https://www.focalboard.com | https://github.com/mattermost-community/focalboard (read its LICENSE) | [board, table] | Board and table views of the same cards |
| Cal.diy (from Cal.com) | https://cal.diy | https://github.com/calcom/cal.diy (MIT) | [calendar, forms] | Month and week calendars, the booking form |
| Ghost | https://ghost.org | https://github.com/TryGhost/Ghost (MIT) | [review, filing, type, sidebar] | Post list and editor screens, publishing settings, editorial type |
| Outline | https://www.getoutline.com | https://github.com/outline/outline (read its LICENSE) | [sidebar, filing, type] | A document sidebar with nested pages, and reading type |
| Docmost | https://docmost.com | https://github.com/docmost/docmost (AGPL-3.0) | [sidebar, filing] | A wiki sidebar and its page tree |
| Twenty | https://twenty.com | https://github.com/twentyhq/twenty (read its LICENSE) | [table, board, sidebar] | CRM tables and boards with a left nav |
| Excalidraw | https://excalidraw.com | https://github.com/excalidraw/excalidraw (MIT) | [type] | A hand-drawn feel that still reads as a tool |

## Closed products worth shooting

These have no source to read, so they are sites only. Name the exact screen to shoot.

| Name | Site | Good for | Look at |
|---|---|---|---|
| Linear | https://linear.app | [sidebar, board, table, landing] | 32px nav rows, muted group labels, how little colour it uses |

## Galleries of real product screens

Use these to find candidates, then shoot the product itself, not the gallery page. Several put
part of their content behind a sign-in. Skip what needs one; never sign in for a shot.

| Name | Site | Good for | Note |
|---|---|---|---|
| Component Gallery | https://component.gallery | [sidebar, table, forms, calendar] | The same component across 90-odd design systems, with links to each |
| Refero | https://refero.design | [sidebar, board, table, forms, stats] | Real app screens searchable by screen type. Some of it needs a sign-in |
| Mobbin | https://mobbin.com | [forms, sidebar] | Real app flows, mostly phone. Most of it needs a sign-in |
| Recent Design (was Godly) | https://recent.design | [landing] | Landing pages. Good for a front page, rarely for a tool |
| Land-book | https://land-book.com | [landing] | Landing pages. Turns away scripted requests, so browse by hand |
| Design Systems Repo | https://designsystemsrepo.com | [type, forms] | A directory of public design systems |
| awesome-design-systems | https://github.com/alexpate/awesome-design-systems (Unlicense) | [type, forms] | A long list of design systems, marked by whether their code and tokens are public |

## Type with character

These are open or free type sources, for the C1 principle in `design-engaging-ui`. Each font
carries its own license, so read it before using the font. Serve the font from the repo, never a
font CDN.

| Name | Site | Good for | Note |
|---|---|---|---|
| Fontsource | https://fontsource.org | [type] | Open-license fonts as npm packages, so a Vite page serves them itself. Repo: https://github.com/fontsource/fontsource (MIT) |
| Velvetyne | https://velvetyne.fr | [type] | Libre display faces with a strong voice, for headings and numbers, not body text |
| Collletttivo | https://www.collletttivo.it | [type] | Open-source fonts from an Italian type collective |
| Open Foundry | https://open-foundry.com | [type] | A curated set of open-source fonts, shown in use |
| Fontshare | https://www.fontshare.com | [type] | Free fonts from the Indian Type Foundry, under their own free-font license |

## Colour themes with character

Editor themes and colour systems are tested by people who stare at them all day. Use them for
C2: a leading colour and a sharp accent that hold together in light and dark.

| Name | Site | Repo and license | Good for | Note |
|---|---|---|---|---|
| Solarized | https://ethanschoonover.com/solarized/ | https://github.com/altercation/solarized (MIT) | [colour] | Exact light and dark pairs built on fixed lightness steps |
| Nord | https://www.nordtheme.com | https://github.com/nordtheme/nord (MIT) | [colour] | A cold, quiet palette with a few clear accents |
| Rosé Pine | https://rosepinetheme.com | https://github.com/rose-pine/rose-pine-theme (MIT) | [colour] | Muted warm tones in three variants, one light |
| Catppuccin | https://catppuccin.com | https://github.com/catppuccin/catppuccin (MIT) | [colour] | Pastel and very widely used. Borrow its structure (named roles for each colour), not its look |

## Tools for type and colour

These are not references to compare against. They help turn a borrowed value into a full scale.

| Name | Site | Use it for |
|---|---|---|
| Utopia | https://utopia.fyi | A type and spacing scale that grows smoothly between the phone and desktop widths |
| Type Scale | https://typescale.com | Trying a type ratio on real text |
| Leonardo | https://leonardocolor.io | Colour steps chosen for a contrast target, in light and dark |
| Google Fonts | https://fonts.google.com | Open-license typefaces; check each one's license page |

## What to skip

- Concept shots on Dribbble or Behance. They were never shipped, so nobody has tested them with
  real content.
- Template stores and "admin dashboard" kits. They show the common look this skill exists to
  avoid.
- Anything whose only shot is behind a sign-in, a paywall or a cookie wall.
