import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'servicenow-docs-sources',
  component: 'Pane',
  requestId: 'docs-sources',
  props: {
    title: 'Docs sources',
    isFocused: false,
    bodyColumns: 40,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

/**
 * Calls one of the docs server's tools, under a name a session could connect it with. `$` is
 * loosely typed here on purpose: the generated tool-name types only know the tools of the
 * session that laid them, and the docs server is not always one of those.
 */
const docs = ($: any, name: 'search' | 'read' | 'compare', args: object): Promise<unknown> =>
  $.tool.call({ tool: `mcp__servicenow-docs__snow_docs_${name}`, ...args })

const SEARCH = {
  structuredContent: {
    ok: true,
    hits: [
      {
        id: 'australia:markdown/itsm/prio.md::Define priority lookup rules > Procedure',
        release: 'australia',
        page_title: 'Define priority lookup rules',
        heading_path: 'Define priority lookup rules > Procedure',
        url: 'https://www.servicenow.com/docs/r/itsm/prio.html',
      },
    ],
  },
}
const READ = {
  structuredContent: {
    ok: true,
    id: 'australia:markdown/itsm/prio.md::Define priority lookup rules > Procedure',
    title: 'Define priority lookup rules',
    heading_path: 'Define priority lookup rules > Procedure',
    url: 'https://www.servicenow.com/docs/r/itsm/prio.html',
  },
}

test('a search hit is listed, and reading it marks it as read', async ($, on) => {
  let answer: unknown = SEARCH
  on('command.register', () => ({ value: { command: 'docs-sources' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: answer }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await docs($, 'search', { query: 'priority' })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /Define priority/ }))?.text).toBe('Define priority lookup rules')
  expect((await ui.find({ type: 'Text', text: /found/ }))?.text).toBe('1 found, 0 read')
  await ui.unmount()

  answer = READ
  await docs($, 'read', { id: 'x' })
  const terminal = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await terminal.find({ type: 'Text', text: /found/ }))?.text).toBe('1 found, 1 read')
  expect((await terminal.find({ type: 'Text', text: /^Procedure$/ }))?.text).toBe('Procedure')
  await terminal.unmount()
})

test('other tools and failed calls add nothing', async ($, on) => {
  on('command.register', () => ({ value: { command: 'docs-sources' } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: { structuredContent: { ok: false, message: 'not ready' } } }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await docs($, 'search', { query: 'x' })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text' }))?.text).toMatch(/No passages yet/)
  await ui.unmount()
})

const COMPARE = {
  ok: true,
  release_notes: [
    {
      id: 'brazil:markdown/delta-australia-brazil/incident-rn.md::Incident release notes > New',
      release: 'brazil',
      page_title: 'Incident release notes',
      heading_path: 'Incident release notes > New',
      url: 'https://www.servicenow.com/docs/r/release-notes/incident-rn.html',
    },
  ],
  more_release_notes: [
    { id: 'brazil:markdown/delta-australia-brazil/workspace-rn.md::', application: 'Incident Workspace' },
  ],
  changed_pages: [
    {
      page: 'markdown/itsm/prio.md',
      page_title: 'Define priority lookup rules',
      australia_url: 'https://www.servicenow.com/docs/r/australia/itsm/prio.html',
      brazil_url: 'https://www.servicenow.com/docs/r/itsm/prio.html',
      sections: [
        {
          heading_path: 'Define priority lookup rules > Procedure',
          change: 'changed',
          australia_id: 'australia:markdown/itsm/prio.md::Define priority lookup rules > Procedure',
          brazil_id: 'brazil:markdown/itsm/prio.md::Define priority lookup rules > Procedure',
        },
        {
          heading_path: 'Define priority lookup rules > Old way',
          change: 'removed',
          australia_id: 'australia:markdown/itsm/prio.md::Define priority lookup rules > Old way',
          brazil_id: '',
        },
      ],
    },
  ],
}

async function started($: any, on: any, answer: () => unknown) {
  on('command.register', () => ({ value: { command: 'docs-sources' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_: unknown, e: { cwd: string }) => ({ cwd: e.cwd }))
  on('tool.call', () => answer() as never)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
}

test('a comparison lists release notes, pages found by name and changed sections', async ($, on) => {
  await started($, on, () => ({ result: { structuredContent: COMPARE } }))
  await docs($, 'compare', { query: 'priority' })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /found/ }))?.text).toBe('4 found, 0 read')
  expect((await ui.find({ type: 'Text', text: /^Incident Workspace/ }))?.text).toBe(
    'Incident Workspace release notes',
  )
  expect((await ui.find({ type: 'Text', text: /^Old way$/ }))?.text).toBe('Old way')
  const links = await ui.findAll({ type: 'Link' })
  // the removed section is only in the australia docs, so it opens the australia page
  expect(links.map(link => link.props.href)).toContain(
    'https://www.servicenow.com/docs/r/australia/itsm/prio.html',
  )
  await ui.unmount()
})

test('a result recorded as JSON text is read like a structured one', async ($, on) => {
  let answer: unknown = { result: JSON.stringify(SEARCH.structuredContent) }
  await started($, on, () => answer)
  await docs($, 'search', { query: 'priority' })
  let ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /found/ }))?.text).toBe('1 found, 0 read')
  await ui.unmount()

  answer = { result: { content: [{ type: 'text', text: JSON.stringify(READ.structuredContent) }] } }
  await docs($, 'read', { id: 'x' })
  ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /found/ }))?.text).toBe('1 found, 1 read')
  await ui.unmount()
})

test('when the recorded result has no JSON, the text the model read is used', async ($, on) => {
  await started($, on, () => ({
    result: { somethingElse: true },
    text: JSON.stringify(SEARCH.structuredContent),
  }))
  await docs($, 'search', { query: 'priority' })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /found/ }))?.text).toBe('1 found, 0 read')
  await ui.unmount()
})

test('an errored call adds nothing', async ($, on) => {
  await started($, on, () => ({
    isError: true,
    result: JSON.stringify(SEARCH.structuredContent),
    text: 'the tool failed',
  }))
  await docs($, 'search', { query: 'priority' })
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text' }))?.text).toMatch(/No passages yet/)
  await ui.unmount()
})
