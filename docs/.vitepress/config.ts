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
    ['meta', { name: 'theme-color', content: '#3B82F6' }],
    ['link', { rel: 'icon', type: 'image/png', href: '/favicon.png' }],
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
            { text: 'Python Libraries', link: '/python-libraries' },
            { text: 'Remote APIs', link: '/existing-apis' },
            { text: 'Configuration', link: '/configuration' },
          ]
        },
        {
          text: 'Reference',
          items: [
            { text: 'API Reference', link: '/api-reference' },
            { text: 'Release History', link: '/api-reference#release-history' },
          ]
        },
      ],
    },
    search: {
      provider: 'local'
    },
  }
})
