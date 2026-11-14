import { expect, test } from 'claude-code/testing'

/** Stands for the engine, and keeps the names of the commands the plugin sets up. */
function commands(on: any): string[] {
  const names: string[] = []
  on('command.register', (_: unknown, e: any) => {
    names.push(e.name)

    return { value: { command: e.name } }
  })
  on('tool.register', () => ({ value: { tool: 'mcp__servicenow-docs__show_figure' } }))
  on('session.start', (_: unknown, e: any) => ({ cwd: e.cwd }))

  return names
}

const SDK_PANE = {
  plugin: 'servicenow-docs',
  component: 'Pane',
  requestId: 'sdk-panel',
  surface: 'desktop',
  props: {
    title: 'ServiceNow SDK',
    isFocused: false,
    bodyColumns: 70,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

test('as installed, both panes are set up', async ($, on) => {
  const names = commands(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  expect([...names].sort()).toEqual(['docs-figures', 'sdk-panel'])

  const ui = await $.ui.mount(SDK_PANE)
  expect(await ui.find({ key: 'tab-commands' })).toBeTruthy()
  await ui.unmount()
})

test('with the setting off, the SDK panel is not there', { options: { sdk_panel: false } }, async ($, on) => {
  // It can run SDK commands; the rest of the plugin only reads. Off leaves a plugin that only reads.
  const names = commands(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  expect(names).toEqual(['docs-figures'])

  const ui = await $.ui.mount(SDK_PANE)
  expect(await ui.find({ key: 'tab-commands' })).toBe(undefined)
  await ui.unmount()
})
