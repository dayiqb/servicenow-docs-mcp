// @ts-check
/**
 * Working with the ServiceNow Docs extension (servicenow-docs-mcp): which
 * version has a command line, and the command that runs a lookup.
 *
 * The docs extension is optional. From 0.1.7 it has `snow-docs-mcp <command>`,
 * which prints one JSON object. An older version ignores the arguments and
 * starts its MCP server, which never returns, so the version is checked
 * before any call and every call has a time limit.
 *
 * No Node imports.
 */

import { compareVersions } from './setup.js';

export const MINIMUM_DOCS_VERSION = '0.1.7';

/** The lookups the panel uses. All of them only read. */
export const DOCS_LOOKUPS = Object.freeze(['search', 'read', 'api', 'browse', 'compare', 'status']);

/**
 * The version in a pyproject.toml, or undefined.
 *
 * @param {string} text
 */
export function versionFromPyproject(text) {
  return /^version\s*=\s*"([^"]+)"/m.exec(text)?.[1];
}

/** @param {string | undefined} version */
export function isDocsVersionOk(version) {
  return typeof version === 'string' && compareVersions(version, MINIMUM_DOCS_VERSION) >= 0;
}

/**
 * The program and arguments for one lookup.
 *
 * @param {{ kind: 'folder', folder: string } | { kind: 'path' }} found
 * @param {string} lookup one of DOCS_LOOKUPS
 * @param {readonly string[]} args
 * @returns {{ program: string, argv: string[] }}
 */
export function docsCommand(found, lookup, args) {
  if (!DOCS_LOOKUPS.includes(lookup)) throw new Error(`The panel does not use the docs command "${lookup}".`);
  if (args.some((arg) => typeof arg !== 'string' || /[\0\n\r]/.test(arg))) {
    throw new Error('An argument holds a line break or a null character.');
  }
  if (found.kind === 'path') return { program: 'snow-docs-mcp', argv: [lookup, ...args] };
  return {
    program: 'uv',
    argv: ['run', '--frozen', '--quiet', '--directory', found.folder, 'snow-docs-mcp', lookup, ...args],
  };
}

/**
 * The words to search the platform documentation with for an SDK topic: the
 * topic as it is spoken ("business rule" for businessrule-api) and
 * "ServiceNow Fluent", which is how the documentation titles its pages on
 * the SDK's APIs. Tried against the docs: this finds the API page and the
 * tutorial for a topic, where the topic's keywords alone found unrelated
 * pages that share a word.
 *
 * @param {{ title: string, keywords: readonly string[] }} topic
 */
export function docsQueryForTopic(topic) {
  const plain = topic.title.replaceAll('-', '').toLowerCase();
  const spoken =
    topic.keywords.find((keyword) => keyword.includes(' ') && keyword.replaceAll(' ', '').toLowerCase() === plain) ??
    topic.title.replaceAll('-', ' ');
  return `${spoken} ServiceNow Fluent`;
}

/**
 * The passages of a `search` result, as the panels show them.
 *
 * @param {unknown} result what `snow-docs-mcp search` printed, parsed
 * @returns {{ id: string, title: string, heading: string, snippet: string, url: string }[]}
 */
export function docsHits(result) {
  const hits = result && typeof result === 'object' && Array.isArray(/** @type {any} */ (result).hits) ? /** @type {any} */ (result).hits : [];
  return hits
    .filter((/** @type {any} */ hit) => hit && typeof hit.id === 'string')
    .map((/** @type {any} */ hit) => ({
      id: hit.id,
      title: String(hit.page_title ?? ''),
      heading: String(hit.heading_path ?? ''),
      snippet: String(hit.snippet ?? ''),
      url: typeof hit.url === 'string' && hit.url.startsWith('https://') ? hit.url : '',
    }));
}

/**
 * A search hit's snippet as a line or two to read: without the heading it
 * repeats, without a word cut in half at its start, without markup, and cut
 * at the end of a sentence where there is one.
 *
 * @param {{ title?: string, heading?: string, snippet?: string }} hit
 * @param {number} [limit]
 */
export function docsSummary(hit, limit = 220) {
  let text = String(hit.snippet ?? '');
  for (const lead of [hit.heading, hit.title]) {
    if (lead && text.startsWith(lead)) {
      text = text.slice(lead.length).replace(/^[:\s]+/, '');
      break;
    }
  }
  text = text
    .replace(/<[^>]*>/g, ' ')
    .replace(/\\([^A-Za-z0-9\s])/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
  // A snippet can start in the middle of a sentence: begin at the next one.
  if (/^[a-z]/.test(text)) {
    const next = text.indexOf('. ');
    if (next !== -1 && next < 60) text = text.slice(next + 2);
  }
  text = text.replace(/\s*(\.\.\.|…)$/, '');
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const sentence = cut.lastIndexOf('. ');
  if (sentence >= 80) return cut.slice(0, sentence + 1);
  return `${cut.slice(0, cut.lastIndexOf(' '))}…`;
}

/**
 * The last part of a heading path ("Page > Section" gives "Section"), or ''
 * when it is the page itself.
 *
 * @param {{ title?: string, heading?: string }} hit
 */
export function docsSection(hit) {
  const parts = String(hit.heading ?? '').split(' > ');
  const last = parts[parts.length - 1] ?? '';
  return last && last !== hit.title ? last : '';
}
