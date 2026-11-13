export type Passage = {
  /** The passage's id, as the docs tools return it. */
  id: string
  title: string
  section: string
  release: string
  url: string
  /** True once Claude read the section, not only found it in a search. */
  isRead: boolean
}

declare module 'claude-code' {
  interface PluginState {
    'servicenow-docs-sources': { passages: Shaped<Passage[]> }
  }
}
