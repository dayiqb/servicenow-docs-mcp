import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'servicenow-docs',
  component: 'Pane',
  requestId: 'sdk-panel',
  props: {
    title: 'ServiceNow SDK',
    isFocused: false,
    bodyColumns: 70,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

test('the pane opens on Setup and moves between screens, on terminal and desktop', { options: { sdk_panel: true } }, async $ => {
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })

    // Nothing has been read yet: the SDK is not known, so the checks say so, with Refresh beside their title.
    expect((await ui.find({ type: 'Text', text: /^Checks, \d to fix$/ }))?.text).toMatch(/^Checks, \d to fix$/)
    expect(await ui.find({ key: 'refresh' })).toBeTruthy()

    await ui.press({ key: 'tab-commands' })
    expect(await ui.find({ key: 'command-search' })).toBeTruthy()
    expect(await ui.find({ key: 'cmd-install' })).toBeTruthy()

    await ui.press({ key: 'tab-explain' })
    expect(await ui.find({ key: 'topic-search' })).toBeTruthy()

    await ui.press({ key: 'tab-setup' })
    await ui.unmount()
  }
})

test('a command opens its detail with the command line and no run without a confirmation', { options: { sdk_panel: true } }, async ($, on) => {
  let started = 0
  on('process.spawn', async function* () {
    started += 1
    return { value: { code: 0, signal: null } }
  })
  // The help of the command is asked for when it opens; answer with none.
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: 'no help', isStdoutTruncated: false, isStderrTruncated: false } }))

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.press({ key: 'tab-commands' })
  await ui.press({ key: 'cmd-build' })
  expect((await ui.find({ type: 'Text', text: /^Build$/ }))?.text).toBe('Build')
  expect(await ui.find({ key: 'run' })).toBeTruthy()
  expect(started).toBe(0)
  await ui.press({ key: 'back-commands' })
  await ui.press({ key: 'tab-setup' })
  await ui.unmount()
})

test('in a wide pane the list stays beside the detail; in a narrow one the detail takes its place', { options: { sdk_panel: true } }, async ($, on) => {
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: 'no help', isStdoutTruncated: false, isStderrTruncated: false } }))

  const wide = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 120 }, surface: 'desktop' })
  await wide.press({ key: 'tab-commands' })
  await wide.press({ key: 'cmd-query' })
  expect(await wide.find({ key: 'run' })).toBeTruthy()
  expect(await wide.find({ key: 'cmd-install' })).toBeTruthy()
  expect(await wide.find({ key: 'back-commands' })).toBeFalsy()
  await wide.unmount()

  const narrow = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await narrow.find({ key: 'run' })).toBeTruthy()
  expect(await narrow.find({ key: 'cmd-install' })).toBeFalsy()
  await narrow.press({ key: 'back-commands' })
  expect(await narrow.find({ key: 'cmd-install' })).toBeTruthy()
  await narrow.press({ key: 'tab-setup' })
  await narrow.unmount()
})

test('the effect filter narrows the command list', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.press({ key: 'tab-commands' })
  expect(await ui.find({ key: 'cmd-build' })).toBeTruthy()
  await ui.select({ key: 'effect-filter', value: 'changes-instance' })
  expect(await ui.find({ key: 'cmd-build' })).toBeFalsy()
  expect(await ui.find({ key: 'cmd-install' })).toBeTruthy()
  await ui.select({ key: 'effect-filter', value: 'all' })
  expect(await ui.find({ key: 'cmd-build' })).toBeTruthy()
  await ui.press({ key: 'tab-setup' })
  await ui.unmount()
})

test('a command has one sign: where it goes, or a warning for Install and Run script', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.press({ key: 'tab-commands' })
  // A desktop draws the sign as a picture; what it says is its alt text.
  const sign = async (id: string) => ((await ui.find({ key: `sign-${id}` })) as any)?.children?.[0]?.props?.alt
  expect(await sign('build')).toBe('Stays on this computer')
  expect(await sign('download')).toBe('Contacts an instance')
  expect(await sign('query')).toBe('Contacts an instance')
  expect(await sign('cicd-publish')).toBe('Contacts an instance')
  expect(await sign('install')).toBe('Warning: changes an instance')
  expect(await sign('exec')).toBe('Danger: runs a script on an instance')
  // The picture keeps its size however long the text beside it is.
  expect(((await ui.find({ key: 'sign-build' })) as any)?.props?.flexShrink).toBe(0)
  await ui.press({ key: 'tab-setup' })
  await ui.unmount()

  // A terminal draws no pictures: the sign is a character.
  const terminal = await $.ui.mount({ ...PANE, surface: 'terminal' })
  await terminal.press({ key: 'tab-commands' })
  expect((await terminal.find({ key: 'sign-build' }))?.text).toBe('\u25A1')
  expect((await terminal.find({ key: 'sign-query' }))?.text).toBe('\u25CB')
  expect(((await terminal.find({ key: 'sign-exec' })) as any)?.children?.[0]?.props?.color).toBe('error')
  expect(((await terminal.find({ key: 'sign-install' })) as any)?.children?.[0]?.props?.color).toBe('warning')
  await terminal.press({ key: 'tab-setup' })
  await terminal.unmount()
})

test('search and filter are one line with no label and no button, and the screens have no track', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.press({ key: 'tab-commands' })
  const field = (await ui.find({ key: 'command-search' })) as any
  // One line, so it is as tall as the filter beside it; no submit label is what leaves the button out.
  expect(field?.props?.rows).toBeUndefined()
  expect(field?.props?.submitLabel).toBeUndefined()
  expect(await ui.find({ key: 'effect-filter' })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: 'Find' })).toBeFalsy()
  // Nothing in the pane has a background: the screens stand without a track.
  const tree = JSON.stringify(await ui.find({ type: 'Box' }))
  expect(tree).toContain('tab-commands')
  // Nothing on the list has a background: only a command's note, in its detail, is tinted.
  expect(tree).not.toContain('backgroundColor')
  await ui.press({ key: 'tab-setup' })
  await ui.unmount()
})

test('in a narrow pane a command row has no words at its end, so nothing runs past the frame', { options: { sdk_panel: true } }, async $ => {
  const wide = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await wide.press({ key: 'tab-commands' })
  expect(await wide.find({ type: 'Text', text: 'cicd install' })).toBeTruthy()
  await wide.press({ key: 'tab-setup' })
  await wide.unmount()

  const narrow = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 36 }, surface: 'desktop' })
  await narrow.select({ key: 'screens-more', value: 'commands' })
  expect(await narrow.find({ key: 'cmd-cicd-install' })).toBeTruthy()
  expect(await narrow.find({ type: 'Text', text: 'cicd install' })).toBeFalsy()
  await narrow.press({ key: 'tab-setup' })
  await narrow.unmount()
})

test('the commands are in five groups, each command in one', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  await ui.press({ key: 'tab-commands' })
  for (const group of ['Project', 'Metadata', 'Installation', 'Instance data', 'CI/CD']) {
    expect((await ui.find({ type: 'Text', text: group }))?.text).toBe(group)
  }
  await ui.press({ key: 'tab-setup' })
  await ui.unmount()
})

test('in a middling pane the first three are tabs and the rest are under More', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 53 }, surface: 'desktop' })
  for (const screen of ['setup', 'instances', 'commands']) expect(await ui.find({ key: `tab-${screen}` })).toBeTruthy()
  expect(await ui.find({ key: 'tab-aiux' })).toBeFalsy()
  expect(await ui.find({ key: 'screens-more' })).toBeTruthy()

  await ui.select({ key: 'screens-more', value: 'aiux' })
  expect((await ui.find({ type: 'Text', text: /No AIUX project/ }))?.text).toBe('No AIUX project here')
  await ui.press({ key: 'tab-setup' })
  await ui.unmount()
})

test('a narrow pane shows the tabs that fit, down to one, beside the menu for the rest', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 36 }, surface: 'desktop' })
  expect(await ui.find({ key: 'tab-setup' })).toBeTruthy()
  expect(await ui.find({ key: 'tab-instances' })).toBeFalsy()
  expect(await ui.find({ key: 'screens-more' })).toBeTruthy()
  expect(await ui.find({ key: 'screen' })).toBeFalsy()
  await ui.unmount()
})

test('in a pane too narrow for one tab and a menu, one picker holds every screen', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 24 }, surface: 'desktop' })
  expect(await ui.find({ key: 'screen' })).toBeTruthy()
  expect(await ui.find({ key: 'tab-setup' })).toBeFalsy()
  expect(await ui.find({ key: 'screens-more' })).toBeFalsy()
  await ui.select({ key: 'screen', value: 'explain' })
  expect(await ui.find({ key: 'topic-search' })).toBeTruthy()
  await ui.select({ key: 'screen', value: 'setup' })
  await ui.unmount()
})

test('in a pane wide enough, all five are tabs and there is no More', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  for (const screen of ['setup', 'instances', 'commands', 'explain', 'aiux']) {
    expect(await ui.find({ key: `tab-${screen}` })).toBeTruthy()
  }
  expect(await ui.find({ key: 'screens-more' })).toBeFalsy()
  await ui.unmount()
})

test('a version row says a newer version is out and offers Update, only when one is', { options: { sdk_panel: true } }, async ($, on) => {
  const stored = {
    isLoading: false,
    cwd: '/',
    nodeVersion: 'v26.8.1',
    sdkVersion: '4.14.0',
    sdkError: null,
    telemetry: true,
    topics: [],
    topicText: {},
    instances: [],
    instancesError: null,
    helps: {},
    aiux: null,
    run: null,
    docs: null,
    docsFolder: '',
    docsHits: {},
    latest: undefined as Record<string, string> | undefined,
  }
  on('state.get', (_, e, next) => (e.key === 'data' ? { value: { value: { shape: 'data-2', value: stored }, version: 1 } } : next(e)))
  const marks = async (latest: Record<string, string> | undefined) => {
    stored.latest = latest
    const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
    const found = {
      out: Boolean(await ui.find({ type: 'Text', text: '4.15.0 is out' })),
      update: Boolean(await ui.find({ key: 'update-sdk' })),
    }
    // One list: the tools without a check are in it, and there is no second section.
    expect(Boolean(await ui.find({ type: 'Text', text: 'Panel' }))).toBe(true)
    expect(Boolean(await ui.find({ type: 'Text', text: 'Versions' }))).toBe(false)
    expect(Boolean(await ui.find({ key: 'check-updates' }))).toBe(true)
    expect(Boolean(await ui.find({ key: 'refresh' }))).toBe(true)
    await ui.unmount()
    return found
  }

  // Not asked yet, and asked with nothing newer: nothing is out and nothing to press.
  // (The mark itself is not looked for: a check in Checks can carry the same one.)
  expect(await marks(undefined)).toEqual({ out: false, update: false })
  expect(await marks({ 'ServiceNow SDK': '4.14.0' })).toEqual({ out: false, update: false })
  // A newer SDK is out: the row says so and has Update.
  expect(await marks({ 'ServiceNow SDK': '4.15.0' })).toEqual({ out: true, update: true })
})

test('in a folder that holds several projects, AIUX and Commands ask which one, and init is offered only where there is none', { options: { sdk_panel: true } }, async ($, on) => {
  const projects = [
    { folder: '/ws/sg-resource-booking', path: 'sg-resource-booking', isAiux: false, isFluent: true },
    { folder: '/ws/skygard-avs-aiux', path: 'skygard-avs-aiux', isAiux: true, isFluent: true },
  ]
  const stored = {
    isLoading: false,
    cwd: '/ws',
    workspace: '/ws',
    projects,
    projectChoice: 'pick',
    nodeVersion: 'v26.8.1',
    sdkVersion: '4.14.0',
    sdkError: null,
    telemetry: true,
    topics: [],
    topicText: {},
    instances: [],
    instancesError: null,
    // The help of Build is already read, so opening it writes nothing to this fixed state.
    helps: { build: { parameters: [], options: [], subcommands: [] } },
    aiux: null,
    run: null,
    docs: null,
    docsFolder: '',
    docsHits: {},
  } as Record<string, unknown>
  on('state.get', (_, e, next) => (e.key === 'data' ? { value: { value: { shape: 'data-2', value: stored }, version: 1 } } : next(e)))
  const screen = async (name: string) => {
    const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
    if (name === 'aiux') await ui.press({ key: 'tab-aiux' })
    if (name === 'build') {
      await ui.press({ key: 'tab-commands' })
      await ui.press({ key: 'cmd-build' })
    }
    const found = {
      picker: Boolean(await ui.find({ key: 'project' })),
      init: Boolean(await ui.find({ key: 'copy-aiux-init' })),
    }
    await ui.unmount()
    return found
  }

  // Several and none picked: Setup, AIUX and a command that needs a project ask; nothing offers init.
  expect(await screen('setup')).toEqual({ picker: true, init: false })
  expect(await screen('aiux')).toEqual({ picker: true, init: false })
  expect(await screen('build')).toEqual({ picker: true, init: false })

  // A project that is not an AIUX app is picked: AIUX says so and still lets you pick, without init.
  Object.assign(stored, { cwd: '/ws/sg-resource-booking', projectChoice: 'chosen' })
  expect(await screen('aiux')).toEqual({ picker: true, init: false })

  // No project in the folder or under it: init is offered and there is nothing to pick.
  Object.assign(stored, { cwd: '/ws', projects: [], projectChoice: 'none' })
  expect(await screen('aiux')).toEqual({ picker: false, init: true })
})

test('a long topic name is cut to fit a narrow list', { options: { sdk_panel: true } }, async ($, on) => {
  const long = 'building-ai-agents-advanced-guide'
  // What an earlier load stored: two topics, one with a long name.
  const stored = {
    isLoading: false,
    cwd: '/',
    nodeVersion: 'v26.8.1',
    sdkVersion: '4.14.0',
    sdkError: null,
    telemetry: true,
    topics: [
      { name: long, kind: 'guide', title: 'building-ai-agents-advanced', keywords: [] },
      { name: 'table-api', kind: 'api', title: 'table', keywords: [] },
    ],
    topicText: {},
    instances: [],
    instancesError: null,
    helps: {},
    aiux: null,
    run: null,
    docs: null,
    docsFolder: '',
    docsHits: {},
  }
  on('state.get', (_, e, next) => (e.key === 'data' ? { value: { value: { shape: 'data-2', value: stored }, version: 1 } } : next(e)))

  const ui = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 40 }, surface: 'desktop' })
  await ui.select({ key: 'screens-more', value: 'explain' })
  const row = await ui.find({ key: `topic-${long}` })
  expect(row?.text?.endsWith('…')).toBe(true)
  expect((row?.text ?? '').length).toBeLessThan(long.length)
  expect((await ui.find({ key: 'topic-table-api' }))?.text).toBe('table-api')
  await ui.press({ key: 'tab-setup' })
  await ui.unmount()
})

test('what a docs lookup found is under the topic\'s actions, in a wide pane and a narrow one', { options: { sdk_panel: true } }, async ($, on) => {
  const stored = {
    isLoading: false,
    cwd: '/',
    nodeVersion: 'v26.8.1',
    sdkVersion: '4.14.0',
    sdkError: null,
    telemetry: true,
    topics: [{ name: 'table-api', kind: 'api', title: 'table', keywords: [] }],
    topicText: { 'table-api': 'A table.' },
    instances: [],
    instancesError: null,
    helps: {},
    aiux: null,
    run: null,
    docs: { kind: 'folder', folder: '/docs', version: '2.0.0' },
    docsFolder: '',
    docsHits: { 'table-api': [{ id: 'australia:a.md::B', title: 'Define a table', heading: 'Define a table > Procedure', snippet: 'Define a table > Procedure A table holds records.', url: '' }] },
  }
  on('state.get', (_, e, next) => (e.key === 'data' ? { value: { value: { shape: 'data-2', value: stored }, version: 1 } } : next(e)))

  const wide = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 120 }, surface: 'desktop' })
  await wide.press({ key: 'tab-explain' })
  await wide.press({ key: 'topic-table-api' })
  expect(await wide.find({ key: 'docs' })).toBeTruthy()
  expect(await wide.find({ key: 'docs-column' })).toBeFalsy()
  // A passage is a closed row; opened, it shows its summary and can be read whole.
  expect((await wide.find({ key: 'hit-0' }))?.text).toBe('\u23F5  Define a table')
  expect(await wide.find({ key: 'read-0' })).toBeFalsy()
  await wide.press({ key: 'hit-0' })
  expect(await wide.find({ type: 'Text', text: 'A table holds records.' })).toBeTruthy()
  expect(await wide.find({ key: 'read-0' })).toBeTruthy()
  await wide.press({ key: 'hit-0' })
  expect(await wide.find({ key: 'read-0' })).toBeFalsy()
  await wide.press({ key: 'tab-setup' })
  await wide.unmount()

  const narrow = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 40 }, surface: 'desktop' })
  await narrow.select({ key: 'screens-more', value: 'explain' })
  expect(await narrow.find({ key: 'docs-column' })).toBeFalsy()
  expect((await narrow.find({ key: 'hit-0' }))?.text).toBe('\u23F5  Define a table')
  // The way back says where it goes, and all of it can be pressed.
  expect((await narrow.find({ key: 'back-topics' }))?.text).toBe('\u2039  Back to topics')
  await narrow.press({ key: 'back-topics' })
  await narrow.press({ key: 'tab-setup' })
  await narrow.unmount()
})

test('in a wide pane the screens are a rail, and every one is a tab', { options: { sdk_panel: true } }, async $ => {
  const ui = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns: 120 }, surface: 'desktop' })
  for (const screen of ['setup', 'instances', 'commands', 'explain', 'aiux']) {
    expect(await ui.find({ key: `tab-${screen}` })).toBeTruthy()
  }
  expect(await ui.find({ key: 'screens-more' })).toBeFalsy()
  await ui.press({ key: 'tab-instances' })
  expect((await ui.find({ type: 'Text', text: /^Instances$/ }))?.text).toBe('Instances')
  await ui.press({ key: 'tab-setup' })
  await ui.unmount()
})

test('the probe draws on a desktop and in a terminal', { options: { sdk_panel: true } }, async ($, on) => {
  // What an earlier session left: the probe as the screen that is open.
  on('state.get', (_, e, next) => (e.key === 'view' ? { value: { value: { shape: 'view-3', value: { screen: 'probe' } }, version: 1 } } : next(e)))
  for (const surface of ['desktop', 'terminal'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: 'What this surface draws' }))?.text).toBe('What this surface draws')
    expect(await ui.find({ key: 'probe-rows-4' })).toBeTruthy()
    await ui.unmount()
  }
})
