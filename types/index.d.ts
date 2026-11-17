/**
 * What the plugin keeps for the session, for its two panes. A value outlives a reload of the
 * hooks module, so change the shape tag where its atom is made when a field changes.
 *
 * The contract is one file: it reaches nowhere else.
 */

// ---- the figures pane (panes/figures) ---------------------------------------------------------

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
  /** The same figure drawn for a narrow pane, when Claude gave one. */
  narrow?: string
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

// ---- the ServiceNow SDK panel (panes/sdk-panel) --------------------------------------------------
// Taken from the panel's own repository by scripts/import_sdk_panel.py: edit it there.
// <sdk-panel>
/**
 * The values the pane keeps for the session. Both outlive a reload of the
 * hooks module, so change the shape tag in hooks/register.tsx when a field
 * changes.
 */

/** `probe` is not a tab: `/sdk-panel probe` opens it to show what the surface draws. */
export type PanelScreen = 'setup' | 'instances' | 'commands' | 'explain' | 'aiux' | 'probe'

/** What the person has chosen and typed. */
export type PanelView = {
  screen: PanelScreen
  /** The command whose detail is open; '' shows the list. */
  commandId: string
  /** The topic whose text is open; '' shows the search. */
  topicName: string
  topicQuery: string
  /** '' for every kind, or api, guide, other. */
  topicKind: string
  /** The page of the topic list shown, from 0. */
  topicPage: number
  /** Whether the whole output of the last run is shown, or its last lines. */
  isShowingAllOutput: boolean
  commandQuery: string
  /** The effects the command list is narrowed to; empty shows all. */
  effects: string[]
  /** The alias commands run against. */
  alias: string
  /** Typed values, by command id, then by "param:name" or "opt:name". */
  values: Record<string, Record<string, string>>
  isShowingMore: boolean
  isAdding: boolean
  add: { host: string; alias: string; signIn: string }
  /** The id of the documentation passage that is open, if one is. */
  docsOpen?: string
}

export type PanelInstance = { alias: string; host: string; signIn: string; isDefault: boolean }

export type PanelTopic = { name: string; kind: string; title: string; keywords: string[] }

export type PanelField = {
  name: string
  description: string
  type?: string
  isRequired: boolean
  choices?: string[]
  defaultValue?: string
  flags?: string[]
}

export type PanelProject = { folder: string; path: string; isAiux: boolean; isFluent: boolean; isAbove?: boolean }

export type PanelCheck = { id: string; label: string; status: string; value?: string; fix?: string; detail?: string }

/** What was read from the SDK and the project folder. */
export type PanelData = {
  isLoading: boolean
  /** The folder the panel works in: the project in use, or the session's folder while there is none. */
  cwd: string
  /** The session's folder, which may be a workspace holding several projects. */
  workspace?: string
  /** The projects in the session's folder or up to two levels under it. */
  projects?: PanelProject[]
  /** none: no project found; one: the only one; chosen: picked before; pick: several, none picked yet. */
  projectChoice?: 'none' | 'one' | 'chosen' | 'pick'
  nodeVersion: string | null
  sdkVersion: string | null
  sdkError: string | null
  /** The SDK's usage telemetry for what the pane starts; on unless turned off. */
  telemetry: boolean
  topics: PanelTopic[]
  topicText: Record<string, string>
  instances: PanelInstance[] | null
  instancesError: string | null
  helps: Record<string, { parameters: PanelField[]; options: PanelField[]; subcommands: string[] }>
  aiux: {
    isAiux: boolean
    name: string
    srcDir: string
    pattern: string
    /** The application's version, and the AIUX package it depends on with the version asked for. */
    version?: string
    framework?: string
    /** The AIUX package's name, its installed version, and the package manager the project uses. */
    frameworkName?: string
    frameworkInstalled?: string
    manager?: 'npm' | 'pnpm'
    scope: string
    checks: PanelCheck[]
    pages: string[]
    widgets: string[]
    components: string[]
    scripts: string[]
  } | null
  run: { commandId: string; line: string; output: string; exitCode: number | null; isRunning: boolean } | null
  /** The ServiceNow Docs extension as found: kind is folder, path, old or none. */
  docs: { kind: string; folder?: string; version?: string } | null
  /** Where a checkout of the docs extension is, when the person has said so. */
  docsFolder: string
  /** By topic name: the passages found, or a line of text while searching or on failure. */
  docsHits: Record<string, PanelHit[] | string>
  /** By passage id: the section as read from the documentation, or a line of text while reading or on failure. */
  docsText?: Record<string, string>
  /** By tool name: the version found on this computer, or '' when the tool is not on the PATH. */
  versions?: Record<string, string>
  /** By the name Versions shows: the newest published version, a line of text on failure, or absent when not checked. */
  latest?: Record<string, string>
  isCheckingUpdates?: boolean
}

export type PanelHit = { id: string; title: string; heading: string; snippet: string; url: string }
// </sdk-panel>

declare module 'claude-code' {
  interface PluginState {
    'servicenow-docs': { book: Shaped<Book>; view: Shaped<PanelView>; data: Shaped<PanelData> }
  }
}
