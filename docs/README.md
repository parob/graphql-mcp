# GraphQL MCP Documentation

This directory contains the documentation site for GraphQL MCP, built with [Hugo](https://gohugo.io/) and the [Hugo Book theme](https://github.com/alex-shpak/hugo-book).

## Quick Start

1. Install Hugo Extended (v0.146.0 or later)
2. Clone the Hugo Book theme:
   ```bash
   cd docs
   git clone --depth 1 https://github.com/alex-shpak/hugo-book.git themes/hugo-book
   ```
3. Run the development server:
   ```bash
   hugo server
   ```

Visit `http://localhost:1313` to view the documentation.

## Structure

```
docs/
├── content/          # Documentation content
│   ├── _index.md    # Home page
│   └── docs/        # Documentation pages
├── hugo.toml        # Hugo configuration
├── public/          # Built site (generated)
└── themes/          # Hugo themes
```

## Deployment

Documentation is automatically deployed to GitHub Pages via GitHub Actions when changes are pushed to the main branch.
