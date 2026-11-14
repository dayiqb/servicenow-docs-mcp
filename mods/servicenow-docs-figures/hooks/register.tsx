import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Book, Figure, Source } from '../types'

const PLUGIN = 'servicenow-docs-figures'
const PANE = 'docs-figures'
const TITLE = 'ServiceNow Docs'
const TOOL = `mcp__${PLUGIN}__show_figure`
const KEPT = 12
// The surface takes a drawing of at most 131072 characters; the styling is added to Claude's.
const LONGEST = 100_000

// Change the tag when a figure's fields change: it declines what an earlier
// version stored, which outlives a reload.
const book = atom({ plugin: 'servicenow-docs-figures', key: 'book' } as const, { figures: [], at: 0 }, { shape: 'book-1' })

const ARROW =
  '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">' +
  '<path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></marker></defs>'

// [name, light fill, light line, light text, dark fill, dark line, dark text]
const RAMPS = [
  ['gray', '#f1efe8', '#888780', '#2c2c2a', '#3a3a37', '#a3a199', '#f1efe8'],
  ['teal', '#e1f5ee', '#0f6e56', '#085041', '#085041', '#5dcaa5', '#e1f5ee'],
  ['amber', '#faeeda', '#854f0b', '#633806', '#633806', '#ef9f27', '#faeeda'],
  ['blue', '#e6f1fb', '#185fa5', '#0c447c', '#0c447c', '#85b7eb', '#e6f1fb'],
  ['green', '#eaf3de', '#3b6d11', '#27500a', '#27500a', '#97c459', '#eaf3de'],
  ['red', '#fcebeb', '#a32d2d', '#791f1f', '#791f1f', '#f09595', '#fcebeb'],
  ['purple', '#eeedfe', '#534ab7', '#3c3489', '#3c3489', '#afa9ec', '#eeedfe'],
] as const

const ramp = (name: string, fill: string, line: string, ink: string): string =>
  `.c-${name} rect,.c-${name} circle,.c-${name} ellipse,.c-${name} polygon{fill:${fill};stroke:${line}}` +
  `.c-${name} text{fill:${ink}}.c-${name} .ts{fill:${line}}`

// A drawing is shown as an image, apart from the page: it brings its own colours. Every text
// sits on a fill of its own or is a mid grey, so it can be read on a light and on a dark pane.
const STYLE =
  '<style>' +
  'text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;font-size:14px;fill:#73726c}' +
  '.ts{font-size:12px}.th{font-weight:500}' +
  'rect,circle,ellipse,polygon{stroke-width:1}' +
  '.box{fill:#f1efe8;stroke:#b4b2a9}.node text{fill:#2c2c2a}.node .ts{fill:#5f5e5a}' +
  '.arr{fill:none;stroke:#888780;stroke-width:1.5;marker-end:url(#arrow)}' +
  '.leader{fill:none;stroke:#888780;stroke-width:1;stroke-dasharray:3 3}' +
  RAMPS.map(([name, fill, line, ink]) => ramp(name, fill, line, ink)).join('') +
  '@media (prefers-color-scheme: dark){' +
  'text{fill:#a3a199}.box{fill:#2c2c2a;stroke:#73726c}.node text{fill:#f1efe8}.node .ts{fill:#b4b2a9}' +
  RAMPS.map(([name, , , , fill, line, ink]) => ramp(name, fill, line, ink)).join('') +
  '}</style>'

const DESCRIPTION = `Show a figure in the ServiceNow Docs pane beside the chat, to explain a ServiceNow concept the answer is about: a lifecycle and its states, how records or tables relate, what happens over time, how two values give a third.

Use it when a picture explains what the text cannot say as briefly. At most one figure per answer, and keep the answer itself short: the figure adds to it, it does not repeat it. Take everything in the figure from documentation you have read with the docs tools, in the docs' own terms, and list those pages in \`sources\`.

svg: one <svg viewBox="0 0 680 H"> (always 680 wide, H as tall as needed; a narrow figure is centred in it). No width or height, no <style>, no script: the pane adds the styling for light and dark. It is drawn as an image, so it must be well-formed XML: close every element and write & as &amp;.
- A thing or a state: <g class="node"><rect class="box" x= y= width= height= rx="8"/><text class="th" x= y= text-anchor="middle" dominant-baseline="central">Name</text><text class="ts" ...>Short note</text></g>. Coloured, not neutral: <g class="node c-teal"> with a plain <rect> inside. Colours: c-teal, c-amber, c-blue, c-green, c-red, c-purple, c-gray. At most two, and only where colour means something.
- Text: class "th" is 14px medium, "t" 14px, "ts" 12px and quiet. A 14px letter is about 8px wide and a 12px letter about 6.5px: keep 12px between text and the edge of its box. Text outside a node is grey: use it for the names of arrows and one closing line.
- An arrow: <line class="arr" x1= y1= x2= y2=/> or <path class="arr" d="M... L..."/>. The arrowhead is added. End it 8px before the box it points at, and never run it through a box or a label; go round with a bend.
- Boxes at least 44px high (56 with two lines of text) and 60px apart. Read left to right or top to bottom.
- No empty band above or below: the first shape starts about 8px from the top, and H ends about 8px under the last one. The pane has its own margins.`

const INPUT = {
  type: 'object',
  properties: {
    title: { type: 'string', description: 'What the figure shows, in a few words.' },
    svg: { type: 'string', description: 'The drawing: one <svg viewBox="0 0 680 H">…</svg>.' },
    alt: {
      type: 'string',
      description: 'What the figure says, in one or two sentences, for someone who cannot see it.',
    },
    caption: { type: 'string', description: 'Optional: one line under the figure.' },
    sources: {
      type: 'array',
      description: 'The docs pages the figure is taken from: title and the url the docs tools gave.',
      items: {
        type: 'object',
        properties: { title: { type: 'string' }, url: { type: 'string' } },
        required: ['title', 'url'],
      },
    },
  },
  required: ['title', 'svg', 'alt'],
}

const text = (value: unknown): string => (typeof value === 'string' ? value.trim() : '')

/** Claude's drawing with its size said in the markup and the pane's styling in it; or why not. */
function dress(raw: string): { svg: string } | { why: string } {
  const root = /^<svg\b[^>]*>/i.exec(raw)
  if (!root || !/<\/svg>$/i.test(raw)) return { why: 'svg must be one <svg ...>...</svg> element and nothing else.' }
  if (raw.length > LONGEST) return { why: `svg is ${raw.length} characters; the longest that can be shown is ${LONGEST}.` }
  if (/<script\b|<foreignObject\b|\son\w+\s*=/i.test(raw))
    return { why: 'svg can hold no script, no event handler and no foreignObject: only shapes, lines and text.' }
  const box = /\bviewBox\s*=\s*"\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)\s*"/i.exec(root[0])
  const [width, height] = [Number(box?.[1]), Number(box?.[2])]
  if (!(width > 0 && height > 0)) return { why: 'svg needs a viewBox: <svg viewBox="0 0 680 H">.' }
  // The pane draws it as an image: a document of its own, which needs the svg namespace on
  // its root (without it nothing is drawn) and takes its size from the markup.
  const named = /\sxmlns\s*=/.test(root[0]) ? '' : ' xmlns="http://www.w3.org/2000/svg"'
  const opening = root[0]
    .replace(/\s(?:width|height)\s*=\s*"[^"]*"/gi, '')
    .replace(/^<svg\b/i, `<svg${named} width="${width}" height="${height}"`)
  const body = raw.slice(root[0].length)

  return { svg: opening + (/\bid\s*=\s*"arrow"/.test(body) ? '' : ARROW) + STYLE + body }
}

function sourcesOf(value: unknown): Source[] | { why: string } {
  if (value === undefined || value === null) return []
  if (!Array.isArray(value)) return { why: 'sources must be a list of { title, url }.' }
  const sources: Source[] = []
  for (const one of value) {
    const source = { title: text((one as Source | null)?.title), url: text((one as Source | null)?.url) }
    if (source.title === '' || !source.url.startsWith('https://'))
      return { why: 'every source needs a title and the https url the docs tools gave for the page.' }
    sources.push(source)
  }

  return sources
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'docs-figures',
      description: 'Open the pane with the figures Claude drew from the ServiceNow docs',
    })
    // In the tool list from the start: Claude should reach for it without searching for it.
    await $.tool.register({ name: 'show_figure', description: DESCRIPTION, inputSchema: INPUT, isDeferred: false })

    return next(e)
  })

  on('command.run', { command: 'docs-figures' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })

    return { text: 'ServiceNow Docs pane opened.' }
  })

  // No matcher on the tool's name: the generated names only know a tool once it is registered.
  on('tool.call', async ($, e, next) => {
    if ((e.tool as string) !== TOOL) return next(e)
    const input = e as unknown as Record<string, unknown>
    const refuse = (why: string) => ({ result: `Not shown: ${why}`, isError: true as const })
    const [title, alt] = [text(input.title), text(input.alt)]
    if (title === '') return refuse('title is empty.')
    if (alt === '') return refuse('alt is empty: say in a sentence or two what the figure shows.')
    const dressed = dress(text(input.svg))
    if ('why' in dressed) return refuse(dressed.why)
    const sources = sourcesOf(input.sources)
    if ('why' in sources) return refuse(sources.why)

    const figure: Figure = { title, svg: dressed.svg, alt, caption: text(input.caption), sources }
    await update($, book, ({ figures }): Book => {
      const kept = [...figures, figure].slice(-KEPT)

      return { figures: kept, at: kept.length - 1 }
    })
    // The person asked to be shown something: the pane comes forward each time.
    const opened = await $.ui.open({ id: PANE, title: TITLE })

    return {
      result: opened.isPlaced
        ? `'${title}' is shown in the ServiceNow Docs pane beside the chat. Do not repeat it in the answer.`
        : // The pane stays open with the figure, and is drawn when a surface that places panes
          // attaches. Until then the person sees nothing of it.
          `'${title}' is in the ServiceNow Docs pane, which is not drawn yet (${opened.reason}). ` +
          'It appears when the pane can be drawn. Say in words what it shows as well.',
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Link } = $.ui.resolve(e)
    const { figures, at } = await read($, book)
    const figure = figures[Math.min(Math.max(at, 0), figures.length - 1)]
    if (!figure) {
      return (
        <Text dimColor>
          No figure yet. When a picture explains a ServiceNow concept better than
          text, Claude draws it here.
        </Text>
      )
    }
    const index = figures.indexOf(figure)
    // A terminal draws no vector figure and nothing in its place: there the pane says it.
    let drawing
    if (e.surface === 'terminal') drawing = <Text>{figure.alt}</Text>
    else {
      const { Svg } = $.ui.resolve(e)
      drawing = <Svg source={figure.svg} alt={figure.alt} />
    }
    const turn = (to: number) => () => update($, book, (held): Book => ({ ...held, at: to }))

    return (
      <Box flexDirection="column" gap={1}>
        <Text weight="semibold">{figure.title}</Text>
        {drawing}
        {figure.caption !== '' && <Text dimColor>{figure.caption}</Text>}
        {figure.sources.length > 0 && (
          <Box flexDirection="column">
            {figure.sources.map(source => (
              <Link href={source.url} label={source.title} />
            ))}
          </Box>
        )}
        {figures.length > 1 && (
          <Box flexDirection="row" gap={2}>
            {index > 0 && <Button key="previous" label="Previous" onPress={turn(index - 1)} />}
            <Text dimColor>
              {index + 1} of {figures.length}
            </Text>
            {index < figures.length - 1 && <Button key="next" label="Next" onPress={turn(index + 1)} />}
          </Box>
        )}
      </Box>
    )
  })
}
