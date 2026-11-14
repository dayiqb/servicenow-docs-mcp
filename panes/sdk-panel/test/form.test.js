import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { commandById } from '../core/catalog.js';
import { composeArgv, formOptions, labelOf, missingRequired, takesInstance } from '../core/form.js';
import { classify } from '../core/guard.js';
import { ownOptions, parseHelp } from '../core/help.js';

/** A catalog entry with the options of its help fixture. */
function command(id, fixture = id) {
  const help = parseHelp(readFileSync(new URL(`./fixtures/help-${fixture}.txt`, import.meta.url), 'utf8'));
  return { ...commandById(id), help: { parameters: help.parameters, options: ownOptions(help) } };
}

test('a query: parameter, options, alias', () => {
  const query = command('query');
  const argv = composeArgv(query, { 'param:table': 'incident', 'opt:query': 'active=true', 'opt:limit': '5' }, 'dev');
  assert.deepEqual(argv, ['query', 'incident', '--query', 'active=true', '--limit', '5', '--auth', 'dev']);
  assert.equal(classify(argv).confirmation, 'review');
});

test('a value equal to the default is left out', () => {
  const argv = composeArgv(command('query'), { 'param:table': 'incident', 'opt:query': 'x', 'opt:limit': '100', 'opt:display-value': 'false' }, 'dev');
  assert.deepEqual(argv, ['query', 'incident', '--query', 'x', '--auth', 'dev']);
});

test('booleans: only a difference from the default is written, as --name or --no-name', () => {
  const install = command('install');
  assert.deepEqual(composeArgv(install, {}, 'dev'), ['install', '--auth', 'dev']);
  assert.deepEqual(composeArgv(install, { 'opt:reinstall': true }, 'dev'), ['install', '--reinstall', '--auth', 'dev']);
  assert.deepEqual(composeArgv(install, { 'opt:reinstall': 'true', 'opt:demoData': 'false' }, 'dev'), [
    'install',
    '--reinstall',
    '--no-demoData',
    '--auth',
    'dev',
  ]);
  assert.deepEqual(composeArgv(install, { 'opt:demoData': true, 'opt:reinstall': false }, 'dev'), ['install', '--auth', 'dev']);
});

test('the form leaves out --auth and the flag the command itself is', () => {
  const info = command('install-info', 'install');
  const names = formOptions(info).map((option) => option.name);
  assert.ok(!names.includes('auth'));
  assert.ok(!names.includes('info'));
  assert.deepEqual(composeArgv(info, {}, 'dev'), ['install', '--info', '--auth', 'dev']);
});

test('a command without --auth gets no alias', () => {
  const build = command('build');
  assert.equal(takesInstance(build), false);
  assert.deepEqual(composeArgv(build, {}, 'dev'), ['build']);
});

test('missing required values are named', () => {
  const query = command('query');
  assert.equal(missingRequired(query, {}), 'table');
  assert.equal(missingRequired(query, { 'param:table': 'incident' }), 'query');
  assert.equal(missingRequired(query, { 'param:table': 'incident', 'opt:query': 'x' }), undefined);
});

test('labels', () => {
  assert.equal(labelOf('display-value'), 'Display value');
  assert.equal(labelOf('demoData'), 'Demo data');
  assert.equal(labelOf('app-sys-id'), 'App sys id');
});
