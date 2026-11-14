import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { explainArgv, kindLabel, parsePeek, parseTopicList, searchTopics } from '../core/explain.js';

const topics = parseTopicList(readFileSync(new URL('./fixtures/explain-list.txt', import.meta.url), 'utf8'));
const names = (list) => list.map((topic) => topic.name);

test('the list is read without its comment lines', () => {
  assert.equal(topics.length, 23);
  assert.deepEqual(topics[0], {
    name: 'acl-api',
    kind: 'api',
    title: 'acl',
    keywords: ['Acl', 'acl', 'access control', 'security', 'permission', 'sys_security_acl'],
  });
  assert.ok(topics.every((topic) => !topic.name.startsWith('#')));
});

test('kinds come from the name', () => {
  const byName = Object.fromEntries(topics.map((topic) => [topic.name, topic]));
  assert.equal(byName['table-guide'].kind, 'guide');
  assert.equal(byName['table-guide'].title, 'table');
  assert.equal(byName['keys-file'].kind, 'other');
  assert.equal(byName['keys-file'].title, 'keys-file');
  assert.equal(kindLabel('api'), 'API');
  assert.equal(kindLabel('other'), 'Reference');
});

test('a topic without keywords is still a topic', () => {
  assert.deepEqual(parseTopicList('plain-topic\n'), [{ name: 'plain-topic', kind: 'other', title: 'plain-topic', keywords: [] }]);
  assert.deepEqual(parseTopicList(''), []);
});

test('an empty query lists everything in order', () => {
  assert.deepEqual(names(searchTopics(topics, '  ')), names(topics));
});

test('a name hit outranks a keyword hit', () => {
  const found = names(searchTopics(topics, 'table'));
  assert.deepEqual(found.slice(0, 2), ['table-api', 'table-guide']);
  assert.ok(found.length > 2, 'topics that only mention tables in keywords follow');
});

test('every word must match, in any case', () => {
  const found = searchTopics(topics, 'FLOW trigger');
  assert.ok(names(found).includes('wfa-trigger-guide'));
  for (const topic of found) {
    const text = [topic.name, ...topic.keywords].join(' ').toLowerCase();
    assert.ok(text.includes('flow') && text.includes('trigger'), topic.name);
  }
  assert.ok(found.length < topics.length);
  assert.deepEqual(searchTopics(topics, 'table zzzz'), []);
});

test('keywords are searched: a table name finds its API', () => {
  assert.equal(names(searchTopics(topics, 'sys_security_acl'))[0], 'acl-api');
});

test('the kind filter narrows the pool', () => {
  const guides = searchTopics(topics, '', { kind: 'guide' });
  assert.ok(guides.length > 0);
  assert.ok(guides.every((topic) => topic.kind === 'guide'));
  assert.deepEqual(names(searchTopics(topics, 'table', { kind: 'guide' })).slice(0, 1), ['table-guide']);
});

test('peek output is a name and a summary', () => {
  assert.deepEqual(parsePeek('table-api: Defines a database table (`sys_db_object`): typed columns.\n'), {
    name: 'table-api',
    summary: 'Defines a database table (`sys_db_object`): typed columns.',
  });
  assert.equal(parsePeek(''), undefined);
  assert.equal(parsePeek('No topic found for: zzz'), undefined);
});

test('explainArgv builds a read-only line and refuses odd topic names', () => {
  assert.deepEqual(explainArgv('table-api'), ['explain', 'table-api', '--format', 'raw']);
  assert.deepEqual(explainArgv('table-api', { peek: true }), ['explain', 'table-api', '--peek', '--format', 'raw']);
  assert.throws(() => explainArgv('--print'));
  assert.throws(() => explainArgv('a b'));
  assert.throws(() => explainArgv(''));
});
