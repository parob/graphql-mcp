---
title: GraphQL MCP Documentation
---

# GraphQL MCP Documentation

This directory contains the Hugo-based documentation site for GraphQL MCP.

## Building Locally

Install Hugo (extended version):

```bash
# macOS
brew install hugo

# Linux
sudo snap install hugo

# Or download from https://github.com/gohugoio/hugo/releases
```

Install the Hugo Book theme:

```bash
cd docs
git clone --depth 1 https://github.com/alex-shpak/hugo-book.git themes/hugo-book
```

Run the development server:

```bash
cd docs
hugo server
```

The documentation will be available at `http://localhost:1313`.

## Building for Production

```bash
cd docs
hugo --gc --minify
```

The built site will be in `docs/public`.

## Deployment

The documentation is automatically deployed to GitHub Pages when changes are pushed to the `main` branch. See `.github/workflows/pages.yml` for the deployment configuration.
