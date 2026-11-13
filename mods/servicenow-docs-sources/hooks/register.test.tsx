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
  await $.tool.call({ tool: 'mcp__servicenow-docs__snow_docs_search', query: 'priority' })

  let ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /Define priority/ }))?.text).toBe('Define priority lookup rules')
  expect((await ui.find({ type: 'Text', text: /found/ }))?.text).toBe('1 found, 0 read')
  await ui.unmount()

  answer = READ
  await $.tool.call({ tool: 'mcp__servicenow-docs__snow_docs_read', id: 'x' })
  ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /found/ }))?.text).toBe('1 found, 1 read')
  expect((await ui.find({ type: 'Text', text: /^Procedure$/ }))?.text).toBe('Procedure')
  await ui.unmount()
})

test('other tools and failed calls add nothing', async ($, on) => {
  on('command.register', () => ({ value: { command: 'docs-sources' } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('tool.call', () => ({ result: { structuredContent: { ok: false, message: 'not ready' } } }))

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  await $.tool.call({ tool: 'mcp__servicenow-docs__snow_docs_search', query: 'x' })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text' }))?.text).toMatch(/No passages yet/)
  await ui.unmount()
})
