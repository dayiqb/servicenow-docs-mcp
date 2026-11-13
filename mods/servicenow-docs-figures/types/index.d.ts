export type Source = {
  /** The page's title, as the docs tools gave it. */
  title: string
  /** The page on servicenow.com. */
  url: string
}

export type Figure = {
  title: string
  /** The drawing as Claude wrote it, with the pane's styling added. */
  svg: string
  /** What the drawing says, for a reader or a surface that cannot show it. */
  alt: string
  caption: string
  sources: Source[]
}

export type Book = {
  /** The figures of the session, oldest first. */
  figures: Figure[]
  /** Which one the pane shows. */
  at: number
}

declare module 'claude-code' {
  interface PluginState {
    'servicenow-docs-figures': { book: Shaped<Book> }
  }
}
