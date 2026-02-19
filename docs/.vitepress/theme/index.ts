import DefaultTheme from 'vitepress/theme'
import { h } from 'vue'
import './custom.css'
import NavLinks from './NavLinks.vue'

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => h(NavLinks),
    })
  },
}
