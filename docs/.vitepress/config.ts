import { defineConfig } from 'vitepress'
import path from 'node:path'

export default defineConfig({
  title: 'GraphQL MCP',
  description: 'Instantly expose any GraphQL API as MCP tools for AI agents and LLMs.',
  srcDir: 'public',
  cleanUrls: true,
  lastUpdated: true,
  vite: {
    publicDir: path.resolve(__dirname, 'public'),
  },
  head: [
    ['meta', { name: 'theme-color', content: '#3B82F6' }]
  ],
  themeConfig: {
    nav: [
      { text: 'Getting Started', link: '/getting-started' },
      { text: 'Guides', link: '/python-libraries' },
      { text: 'Reference', link: '/api-reference' },
    ],
    sidebar: {
      '/': [
        {
          text: 'Getting Started',
          items: [
            { text: 'Quick Start', link: '/getting-started' },
          ]
        },
        {
          text: 'Guides',
          items: [
            { text: 'How It Works', link: '/how-it-works' },
            { text: 'Python Libraries', link: '/python-libraries' },
            { text: 'Existing APIs', link: '/existing-apis' },
            { text: 'Customization', link: '/customization' },
            { text: 'Deployment', link: '/deployment' },
            { text: 'Testing', link: '/testing' },
          ]
        },
        {
          text: 'Reference',
          items: [
            { text: 'API Reference', link: '/api-reference' },
            { text: 'Examples', link: '/examples' },
          ]
        },
      ],
    },
    search: {
      provider: 'local'
    },
  }
})
