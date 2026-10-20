# stephenlewandowski.github.io

Professional website, post-service public CV, teaching portfolio, and project index for Stephen A. Lewandowski.

## Structure

- `index.html` - professional homepage
- `cv/index.html` - web-readable public CV
- `teaching/index.html` - teaching philosophy, experience, and representative materials
- `teaching/materials/` - teaching-material collection with seven context pages and portable files
- `teaching/materials/research-methods-analysis/` - RSCH650 project overview, playable lesson, interactive simulation, synthetic data, SPSS syntax, and readable teaching notes
- `_layouts/teaching-document.html` - shared GitHub Pages layout for readable Markdown teaching documents
- `projects/index.html` - current projects and selected earlier GitHub work
- `projects/air-quality/` - observed hourly PM2.5 comparison for 2024, with Seoul's district network and London/Beijing stations, averaging controls and source data
- `projects/uss-terror/index.html` - documented overview of the USS Terror R/Shiny spatial reconstruction
- `projects/korean-peninsula-aedes-suitability/index.html` - portfolio overview of the audited Korean Peninsula Aedes suitability publication
- `projects/western-basin-worldbuilding/index.html` - illustrated Western Basin Atlas overview, with routes into maps, stories, and the scientific track
- `assets/western-basin-previews.json` - provenance for the Atlas artwork reproduced in this portfolio
- `assets/styles.css` - shared responsive and print styles
- `404.html` - missing-page recovery with links to projects, teaching materials, and CV
- `scripts/check_site.py` - dependency-free source and local-link checks
- `assets/Stephen-Lewandowski-Public-CV.pdf` - downloadable public CV

The site uses plain HTML and CSS. GitHub Pages applies its standard Jekyll pass to render teaching Markdown through the shared document layout; there is no package manager, analytics, or third-party runtime dependency.

## Publishing

GitHub Pages publishes the `main` branch from the repository root after an approved pull request is merged.

## Check changes

Run from the repository root with Python 3:

```sh
python scripts/check_site.py
git diff --check
```

The checker verifies page landmarks, unique HTML IDs, image alternative-text attributes,
local assets and links, HTML fragment targets, and sitemap destinations. Teaching
`.html` links resolve to their Jekyll Markdown sources. External sites and generated
Markdown heading IDs require separate checks; this command does not render pages.

When adding a public page, update `sitemap.xml` and link it from the relevant landing
page. Keep redirects and the 404 page out of the sitemap. The portfolio overview at
`/projects/korean-peninsula-aedes-suitability/` and the separate analytical publication
at `/korean-peninsula-aedes-suitability/` serve different purposes; preserve both routes.

Keep the homepage summaries brief, with methods and detailed evidence on project pages.
Retain the plain HTML/CSS structure and the shared teaching-document layout.

The air-quality page serves retained measured data directly, without an external
API call from the visitor's browser. Source provenance, seasonal coverage and
reproduction instructions are in `projects/air-quality/data/README.md`. Seoul is
required; other records must cover all four seasons. Run
`node --test scripts/test_air_quality.mjs scripts/test_pm25_benchmarks.mjs` when changing its calculations and
`python scripts/check_air_quality_data.py` when refreshing its datasets.
The PM2.5 standards panel uses full-year local standard-time statistics; custom
threshold counts use the selected UTC range. Preserve that distinction and the
explicit three-year/site-suitability limitations when changing the interface.
When releasing changes, refresh the page-specific module, changed module imports
and manifest version URLs together so returning visitors receive consistent data
and calculation code.

## Content and maintenance

Use plain, specific headings that name the subject or the reader’s task. Avoid
invented slogans, forced three-part phrases, and abstract promises about evidence
or decisions. Write introductions in natural prose, using concrete examples from
the work. Keep technical terms where they add precision, preserve factual limits
and source attribution, and retain the character of personal stories and fiction.

The site presents a concise post-service professional profile, selected teaching materials, and public project work. Teaching materials retain dates, attribution, synthetic-data boundaries, and distinctions among regulations, guidance, recommendations, and scientific evidence. Changeable regulatory and dataset claims should be checked before classroom or professional use.

The current USS Terror project is documented at <https://github.com/stephenlewandowski/uss-terror>.
The hosted Shiny application is available at <https://019ff822-911b-41e4-494c-8ca10f1f35ec.share.connect.posit.cloud>.

The Korean Peninsula Aedes suitability project is documented at <https://github.com/stephenlewandowski/korean-peninsula-aedes-suitability>.
The full results, methods, and downloadable products are available at <https://stephenlewandowski.github.io/korean-peninsula-aedes-suitability/>.

The Western Basin Atlas is featured on the homepage and Projects page:
<https://stephenlewandowski.github.io/western-basin-worldbuilding/>.
Its portfolio overview introduces illustrated regions, interactive encounters, and
the distinction between observed river flow, synthetic Model Lab cases, and future
design concepts. The existing project route and `#western-basin` index anchor are
retained. The portfolio reproduces two accepted WebP illustrations without changes;
a smaller JPEG map supports social previews. Their source paths, commit, hashes, and
image-generation records are recorded in `assets/western-basin-previews.json`.
Full source imagery remains in the worldbuilding repository.

Earlier public work remains archived at:

- <https://github.com/sal2222>
- <https://sal2222.github.io/>

## Research Methods and Analysis teaching project

The overview at `/teaching/materials/research-methods-analysis/` connects the RSCH650
teaching resources to the teaching portfolio and project index. The animation,
captions, synthetic datasets, and SPSS syntax are copied from the public
`stephenlewandowski/research-methods-analysis` project at revision
`87c593ba3e9240b1f4ec4d4fa290daa1d3da9e54`. The classroom player retains its embedded
video for offline use. The simulation retains its sandbox and requires internet
access for D3. Instructor notes and the SPSS lab use the shared Jekyll document
layout. `provenance.json` records source paths, source and published-file hashes,
and presentation-only adaptations. Refresh deliberately from a reviewed source
revision and update the manifest; do not silently replace the numerical examples.
