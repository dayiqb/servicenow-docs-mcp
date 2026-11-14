// @ts-check
/**
 * The SDK's own documentation (`now-sdk explain`): the topic list as data and
 * a search over it.
 *
 * `now-sdk explain --list --format raw` prints one topic per line:
 *
 *     # Available topics:
 *     acl-api [Acl, acl, access control, security]
 *     # Use `now-sdk explain <name>` with a topic name to expand.
 *
 * No Node imports.
 */

/**
 * @typedef {'api' | 'guide' | 'other'} TopicKind
 */

/**
 * @typedef {object} Topic
 * @property {string} name        e.g. "table-api".
 * @property {TopicKind} kind
 * @property {string} title       The name without its kind suffix, e.g. "table".
 * @property {string[]} keywords
 */

const TOPIC_LINE = /^(\S+)(?:\s+\[(.*)\])?\s*$/;
const KIND_LABELS = Object.freeze({ api: 'API', guide: 'Guide', other: 'Reference' });

/**
 * @param {string} text what `explain --list --format raw` printed
 * @returns {Topic[]}
 */
export function parseTopicList(text) {
  /** @type {Topic[]} */
  const topics = [];
  for (const raw of text.replaceAll('\r', '').split('\n')) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const found = TOPIC_LINE.exec(line);
    if (!found) continue;
    const name = found[1];
    const kind = name.endsWith('-api') ? 'api' : name.endsWith('-guide') ? 'guide' : 'other';
    topics.push({
      name,
      kind,
      title: kind === 'other' ? name : name.slice(0, name.lastIndexOf('-')),
      keywords: (found[2] ?? '')
        .split(',')
        .map((keyword) => keyword.trim())
        .filter(Boolean),
    });
  }
  return topics;
}

/** @param {TopicKind} kind */
export function kindLabel(kind) {
  return KIND_LABELS[kind];
}

/**
 * Topics matching every word of the query, best first. A word matches a
 * topic's name or one of its keywords, ignoring case; a hit on the name
 * outranks a hit on a keyword, a whole-word hit outranks a part.
 *
 * An empty query returns every topic in its listed order.
 *
 * @param {readonly Topic[]} topics
 * @param {string} query
 * @param {{ kind?: TopicKind }} [filter]
 * @returns {Topic[]}
 */
export function searchTopics(topics, query, filter = {}) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const pool = filter.kind ? topics.filter((topic) => topic.kind === filter.kind) : topics;
  if (words.length === 0) return [...pool];

  /** @type {{ topic: Topic, score: number, order: number }[]} */
  const scored = [];
  pool.forEach((topic, order) => {
    let score = 0;
    for (const word of words) {
      const wordScore = scoreWord(topic, word);
      if (wordScore === 0) return;
      score += wordScore;
    }
    scored.push({ topic, score, order });
  });
  scored.sort((a, b) => b.score - a.score || a.order - b.order);
  return scored.map((entry) => entry.topic);
}

/**
 * @param {Topic} topic
 * @param {string} word lowercase
 */
function scoreWord(topic, word) {
  const name = topic.name.toLowerCase();
  const title = topic.title.toLowerCase();
  if (name === word || title === word) return 100;
  if (title.startsWith(word)) return 60;
  if (name.includes(word)) return 40;
  let best = 0;
  for (const keyword of topic.keywords) {
    const lower = keyword.toLowerCase();
    if (lower === word) best = Math.max(best, 30);
    else if (lower.split(/[\s._-]+/).includes(word)) best = Math.max(best, 20);
    else if (lower.includes(word)) best = Math.max(best, 10);
  }
  return best;
}

/**
 * `now-sdk explain <topic> --peek --format raw` prints "name: summary".
 *
 * @param {string} text
 * @returns {{ name: string, summary: string } | undefined}
 */
export function parsePeek(text) {
  const line = text
    .replaceAll('\r', '')
    .split('\n')
    .find((one) => one.trim() !== '');
  if (!line) return undefined;
  const cut = line.indexOf(': ');
  if (cut <= 0 || /\s/.test(line.slice(0, cut))) return undefined;
  return { name: line.slice(0, cut), summary: line.slice(cut + 2).trim() };
}

/**
 * The arguments for reading one topic, after `now-sdk`.
 *
 * @param {string} topic
 * @param {{ peek?: boolean }} [options]
 * @returns {string[]}
 */
export function explainArgv(topic, options = {}) {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(topic)) {
    throw new Error('A topic name holds letters, digits, dots, dashes and underscores.');
  }
  return ['explain', topic, ...(options.peek ? ['--peek'] : []), '--format', 'raw'];
}
