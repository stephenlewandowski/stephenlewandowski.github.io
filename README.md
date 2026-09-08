# stephenlewandowski.github.io

Professional website, post-service public CV, teaching portfolio, and project index for Stephen A. Lewandowski.

## Structure

- `index.html` - professional homepage
- `cv/index.html` - web-readable public CV
- `teaching/index.html` - teaching philosophy, experience, and representative materials
- `teaching/materials/` - teaching-material collection with six context pages and portable files
- `_layouts/teaching-document.html` - shared GitHub Pages layout for readable Markdown teaching documents
- `projects/index.html` - current projects and selected earlier GitHub work
- `projects/uss-terror/index.html` - documented overview of the USS Terror R/Shiny spatial reconstruction
- `projects/korean-peninsula-aedes-suitability/index.html` - portfolio overview of the audited Korean Peninsula Aedes suitability publication
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

## Content and maintenance

The site presents a concise post-service professional profile, selected teaching materials, and public project work. Teaching materials retain dates, attribution, synthetic-data boundaries, and distinctions among regulations, guidance, recommendations, and scientific evidence. Changeable regulatory and dataset claims should be checked before classroom or professional use.

The current USS Terror project is documented at <https://github.com/stephenlewandowski/uss-terror>.
The hosted Shiny application is available at <https://019ff822-911b-41e4-494c-8ca10f1f35ec.share.connect.posit.cloud>.

The Korean Peninsula Aedes suitability project is documented at <https://github.com/stephenlewandowski/korean-peninsula-aedes-suitability>.
The full results, methods, and downloadable products are available at <https://stephenlewandowski.github.io/korean-peninsula-aedes-suitability/>.

Earlier public work remains archived at:

- <https://github.com/sal2222>
- <https://sal2222.github.io/>
