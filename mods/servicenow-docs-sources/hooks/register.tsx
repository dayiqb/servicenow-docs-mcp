import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Passage } from '../types'

const PANE = 'docs-sources'
const TITLE = 'Docs sources'
// The docs tools whose results name passages, whatever prefix the server has.
const DOCS_TOOL = /snow_docs_(search|read|compare)$/
const KEPT = 60

// Change the tag when a passage's fields change: it declines what an earlier
// version stored, which outlives a reload.
const passages = atom(
  { plugin: 'servicenow-docs-sources', key: 'passages' } as const,
  [],
  { shape: 'passages-1' },
)

type Json = Record<string, unknown>

const text = (value: unknown): string =>
  typeof value === 'string' ? value : ''

/** The tool's result as the JSON object the docs server returned. */
function payload(result: unknown): Json | undefined {
  const parse = (raw: string): Json | undefined => {
    try {
      const value: unknown = JSON.parse(raw)

      return value && typeof value === 'object' ? (value as Json) : undefined
    } catch {
      return undefined
    }
  }

  if (typeof result === 'string') return parse(result)
  if (!result || typeof result !== 'object') return undefined
  const record = result as Json
  const structured = record.structuredContent
  if (structured && typeof structured === 'object') return structured as Json
  if (Array.isArray(record.content)) {
    for (const block of record.content) {
      const found = parse(text((block as Json | null)?.text))
      if (found) return found
    }
  }

  return 'ok' in record ? record : undefined
}

/** The last part of a breadcrumb, without the page title in front. */
function section(headingPath: string, title: string): string {
  const crumbs = headingPath
    .split(' > ')
    .map(part => part.replace(/\\(.)/g, '$1'))
    .filter(Boolean)

  return (crumbs[0] === title ? crumbs.slice(1) : crumbs).join(' > ')
}

function fromHit(hit: Json, isRead: boolean): Passage | undefined {
  const id = text(hit.id)
  if (!id) return undefined
  const title = text(hit.page_title) || text(hit.title) || id

  return {
    id,
    title,
    section: section(text(hit.heading_path), title),
    release: text(hit.release) || id.split(':')[0] || '',
    url: text(hit.url),
    isRead,
  }
}

function found(tool: string, data: Json): Passage[] {
  if (data.ok !== true) return []
  if (tool.endsWith('read')) return [fromHit(data, true)].filter(Boolean) as Passage[]
  const hits = [data.hits, data.release_notes].flatMap(list =>
    Array.isArray(list) ? (list as Json[]) : [],
  )

  return hits.map(hit => fromHit(hit, false)).filter(Boolean) as Passage[]
}

/** Newest first, one row per passage; a read passage stays marked as read. */
function merge(list: Passage[], added: Passage[]): Passage[] {
  const next = [...list]
  for (const passage of added) {
    const at = next.findIndex(one => one.id === passage.id)
    const isRead = passage.isRead || (at >= 0 && next[at]!.isRead)
    if (at >= 0) next.splice(at, 1)
    next.unshift({ ...passage, isRead })
  }

  return next.slice(0, KEPT)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'docs-sources',
      description:
        'Show the ServiceNow docs passages Claude found and read in this session',
    })

    return next(e)
  })

  on('command.run', { command: 'docs-sources' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })

    return { text: 'Docs sources pane opened.' }
  })

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    if (!DOCS_TOOL.test(e.tool) || ran.deny !== undefined) return ran
    const data = payload(ran.result)
    const added = data ? found(e.tool, data) : []
    if (added.length > 0) {
      const before = await read($, passages)
      await update($, passages, list => merge(list, added))
      // The first passages of the session open the pane; after that it is the
      // person's to keep open or closed.
      if (before.length === 0) void $.ui.open({ id: PANE, title: TITLE })
    }

    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Link } = $.ui.resolve(e)
    const list = await read($, passages)
    const readCount = list.filter(one => one.isRead).length

    return (
      <Box flexDirection="column" gap={1}>
        {list.length === 0 && (
          <Text dimColor>
            No passages yet. They are listed here when Claude searches or reads
            the ServiceNow docs.
          </Text>
        )}
        {list.length > 0 && (
          <Text dimColor>
            {list.length} found, {readCount} read
          </Text>
        )}
        {list.map(passage => (
          <Box flexDirection="column">
            <Text weight="semibold">{passage.title}</Text>
            {passage.section !== '' && <Text dimColor>{passage.section}</Text>}
            <Text dimColor>
              {passage.release}
              {passage.isRead ? ', read' : ''}
            </Text>
            {passage.url !== '' && <Link href={passage.url} label="Open docs" />}
          </Box>
        ))}
      </Box>
    )
  })
}
