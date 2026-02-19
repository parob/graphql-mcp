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
      { text: 'Guides', link: '/how-it-works' },
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
            { text: 'Schema Design', link: '/schema-design' },
            { text: 'Configuration', link: '/configuration' },
            { text: 'Remote GraphQL', link: '/remote-graphql' },
            { text: 'MCP Inspector', link: '/mcp-inspector' },
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
