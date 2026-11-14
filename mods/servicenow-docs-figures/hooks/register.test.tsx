import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'servicenow-docs-figures',
  component: 'Pane',
  requestId: 'docs-figures',
  props: {
    title: 'ServiceNow Docs',
    isFocused: false,
    bodyColumns: 80,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

const TOOL = 'mcp__servicenow-docs-figures__show_figure'
const SVG =
  '<svg width="100%" viewBox="0 0 680 120"><g class="node c-teal"><rect x="260" y="30" width="160" height="56" rx="8"/>' +
  '<text class="th" x="340" y="58" text-anchor="middle">Running</text></g>' +
  '<line class="arr" x1="100" y1="58" x2="250" y2="58"/></svg>'
const SLA = {
  title: 'How an SLA runs',
  svg: SVG,
  alt: 'An SLA is attached, runs, can pause, and completes.',
  caption: 'Marked Breached when the duration runs out.',
  sources: [
    {
      title: 'Create an SLA definition',
      url: 'https://www.servicenow.com/docs/r/australia/it-service-management/service-level-management/t_CreateAnSLADefinition.html',
    },
  ],
}

/** `$` is loosely typed: the generated tool-name types do not know this mod's own tool. */
const show = ($: any, figure: object): Promise<any> => $.tool.call({ tool: TOOL, ...figure })

function engine(on: any, isPlaced = true) {
  // Nothing sits beneath the plugin: each hook here stands for the engine.
  on('command.register', () => ({ value: { command: 'docs-figures' } }))
  on('tool.register', () => ({ value: { tool: TOOL } }))
  on('ui.open', () => ({ value: isPlaced ? { isPlaced } : { isPlaced, reason: 'no-surface: none attached' } }))
  on('session.start', (_: unknown, e: any) => ({ cwd: e.cwd }))
}

test('a figure Claude shows is drawn in the pane, with what it says and where it is from', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })

  const answer = await show($, SLA)
  expect(answer.isError).toBe(undefined)
  expect(String(answer.result)).toMatch(/shown/i)

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /How an SLA/ }))?.text).toBe('How an SLA runs')
  const drawing = await ui.find({ type: 'Svg' })
  expect(drawing?.props.alt).toBe(SLA.alt)
  expect((await ui.find({ type: 'Text', text: /Breached/ }))?.text).toBe(SLA.caption)
  const link = await ui.find({ type: 'Link' })
  expect(link?.props.href).toBe(SLA.sources[0]!.url)
  expect(link?.props.label).toBe('Create an SLA definition')
  // one figure: nothing to page through
  expect(await ui.find({ type: 'Button' })).toBe(undefined)
  await ui.unmount()
})

test('the pane dresses the figure: its own size, the styling for light and dark, the arrowhead', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await show($, SLA)

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  const source = String((await ui.find({ type: 'Svg' }))?.props.source)
  expect(source).toMatch(/^<svg [^>]*width="680" height="120"/)
  expect(source).not.toMatch(/width="100%"/)
  expect(source).toMatch(/<marker id="arrow"/)
  expect(source).toMatch(/<style>[^<]*\.c-teal[^<]*prefers-color-scheme: dark/)
  expect(source).toMatch(/class="node c-teal"/) // what Claude drew is kept as it was
  await ui.unmount()
})

test('the figure is a whole document, because the pane draws it as an image', async ($, on) => {
  // An image needs the svg namespace on its root; without it nothing is drawn at all.
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  const named = SVG.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ')

  for (const svg of [SVG, named]) {
    await show($, { ...SLA, svg })
    const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
    const source = String((await ui.find({ type: 'Svg' }))?.props.source)
    expect(source.match(/xmlns="http:\/\/www\.w3\.org\/2000\/svg"/g)?.length).toBe(1)
    await ui.unmount()
  }
})

const NARROW =
  '<svg viewBox="0 0 340 80"><g class="node c-teal"><rect x="90" y="8" width="160" height="56" rx="8"/>' +
  '<text class="th" x="170" y="36" text-anchor="middle">Running</text></g></svg>'

/** How wide the drawing is that a pane of that many columns shows. */
async function widthAt($: any, bodyColumns: number): Promise<string | undefined> {
  const ui = await $.ui.mount({ ...PANE, props: { ...PANE.props, bodyColumns }, surface: 'desktop' })
  const source = String((await ui.find({ type: 'Svg' }))?.props.source)
  await ui.unmount()

  return /^<svg [^>]*width="(\d+)"/.exec(source)?.[1]
}

test('a wide pane shows the wide drawing and a narrow pane the narrow one', async ($, on) => {
  // A drawing is an image: in a narrow pane the wide one would shrink, text and all. So Claude
  // draws the figure twice, and the pane takes the one that fits, at each width it is given.
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  expect((await show($, { ...SLA, svg_narrow: NARROW })).isError).toBe(undefined)

  expect(await widthAt($, 110)).toBe('680')
  expect(await widthAt($, 48)).toBe('340')
})

test('a figure drawn once is shown at every width', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await show($, SLA)

  expect(await widthAt($, 110)).toBe('680')
  expect(await widthAt($, 48)).toBe('680')
})

test('a narrow drawing that is not a drawing is refused, and says which one', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })

  const answer = await show($, { ...SLA, svg_narrow: 'graph TD; a-->b' })
  expect(answer.isError).toBe(true)
  expect(String(answer.result)).toMatch(/svg_narrow/)
})

test('what is not a drawing is refused, and the pane stays as it was', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })

  for (const svg of ['flowchart TD; a-->b', '<svg><rect/></svg>', '<svg viewBox="0 0 680 80"><script>x</script></svg>']) {
    const answer = await show($, { ...SLA, svg })
    expect(answer.isError).toBe(true)
  }
  expect((await show($, { ...SLA, alt: ' ' })).isError).toBe(true)
  expect((await show($, { ...SLA, sources: [{ title: 'x', url: 'http://example.com/a' }] })).isError).toBe(true)

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Svg' })).toBe(undefined)
  expect((await ui.find({ type: 'Text' }))?.text).toMatch(/No figure yet/)
  await ui.unmount()
})

test('the newest figure is shown, and the earlier ones can be paged back to', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await show($, SLA)
  await show($, { ...SLA, title: 'Incident states', sources: [] })

  let ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /Incident/ }))?.text).toBe('Incident states')
  expect((await ui.find({ type: 'Text', text: / of / }))?.text).toBe('2 of 2')
  expect(await ui.find({ type: 'Link' })).toBe(undefined)
  expect(await ui.find({ type: 'Button', key: 'next' })).toBe(undefined)
  await ui.press({ key: 'previous' })
  await ui.unmount()

  ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /How an SLA/ }))?.text).toBe('How an SLA runs')
  expect((await ui.find({ type: 'Text', text: / of / }))?.text).toBe('1 of 2')
  expect(await ui.find({ type: 'Button', key: 'previous' })).toBe(undefined)
  await ui.unmount()
})

test('a figure shown again under the same title takes the place of the old one', async ($, on) => {
  // Claude draws a figure again to make it better. Kept as two pages, the old drawing and the
  // new one look like two variants to page between.
  engine(on)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await show($, SLA)
  await show($, { ...SLA, title: 'Incident states', sources: [] })
  await show($, { ...SLA, svg_narrow: NARROW, caption: 'Drawn again.' })

  let ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /How an SLA/ }))?.text).toBe('How an SLA runs')
  expect((await ui.find({ type: 'Text', text: /again/ }))?.text).toBe('Drawn again.')
  expect((await ui.find({ type: 'Text', text: / of / }))?.text).toBe('2 of 2')
  await ui.press({ key: 'previous' })
  await ui.unmount()

  ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /Incident/ }))?.text).toBe('Incident states')
  expect((await ui.find({ type: 'Text', text: / of / }))?.text).toBe('1 of 2')
  await ui.unmount()
})

test('two figures with one title that an earlier version kept are shown as one, the newest', async ($, on) => {
  const kept = (caption: string) => ({ title: SLA.title, svg: SVG, alt: SLA.alt, caption, sources: [] })
  const stored = { shape: 'book-1', value: { figures: [kept('First drawing.'), kept('Second drawing.')], at: 0 } }
  on('state.get', () => ({ value: { value: stored, version: 1 } }))

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /drawing/ }))?.text).toBe('Second drawing.')
  expect(await ui.find({ type: 'Text', text: / of / })).toBe(undefined)
  expect(await ui.find({ type: 'Button' })).toBe(undefined)
  await ui.unmount()
})

test('a surface that draws no vector figure says what the figure says', async ($, on) => {
  engine(on)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await show($, SLA)

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect(await ui.find({ type: 'Svg' })).toBe(undefined)
  expect((await ui.find({ type: 'Text', text: /attached/ }))?.text).toBe(SLA.alt)
  await ui.unmount()
})

test('where no pane is drawn yet, Claude is told why, and the figure waits in the pane', async ($, on) => {
  engine(on, false)
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })

  const answer = await show($, SLA)
  expect(answer.isError).toBe(undefined)
  expect(String(answer.result)).toMatch(/not drawn yet/)
  expect(String(answer.result)).toMatch(/no-surface: none attached/)

  // the pane stays open with the figure, for the surface that attaches later
  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Svg' }))?.props.alt).toBe(SLA.alt)
  await ui.unmount()
})

test('searching the docs draws nothing', async ($, on) => {
  engine(on)
  on('tool.call', () => ({ result: { structuredContent: { ok: true, hits: [{ id: 'a::b', page_title: 'A' }] } } }))
  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  await ($ as any).tool.call({ tool: 'mcp__servicenow-docs__snow_docs_search', query: 'sla' })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text' }))?.text).toMatch(/No figure yet/)
  await ui.unmount()
})

test('a value an earlier version stored is declined', async ($, on) => {
  on('state.get', () => ({ value: { value: [{ title: 'old' }], version: 1 } }))

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text' }))?.text).toMatch(/No figure yet/)
  await ui.unmount()
})
