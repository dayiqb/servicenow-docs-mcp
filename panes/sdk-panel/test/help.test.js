import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { ownOptions, parseHelp, stripAnsi } from '../core/help.js';

const fixture = (name) => readFileSync(new URL(`./fixtures/help-${name}.txt`, import.meta.url), 'utf8');

test('root help: the banner is dropped and every command is listed', () => {
  const help = parseHelp(fixture('root'));
  assert.equal(help.usage, '');
  assert.match(help.description, /^Source-driven applications/);
  assert.deepEqual(
    help.commands.map((command) => command.name),
    ['auth', 'init', 'download', 'build', 'install', 'dependencies', 'transform', 'clean', 'pack', 'explain', 'query', 'exec', 'cicd'],
  );
  const init = help.commands.find((command) => command.name === 'init');
  assert.deepEqual(init?.aliases, ['create']);
  assert.match(init?.summary ?? '', /^Initialize a new ServiceNow custom application.*directory structure\.$/);
  const download = help.commands.find((command) => command.name === 'download');
  assert.equal(download?.usage, 'now-sdk download <directory>');
  assert.equal(download?.summary, 'Download application metadata from instance.');
  assert.deepEqual(
    help.groups.flatMap((group) => group.options).map((option) => option.name),
    ['debug', 'help', 'version'],
  );
});

test('auth help: options keep their groups', () => {
  const help = parseHelp(fixture('auth'));
  assert.equal(help.usage, 'now-sdk auth');
  assert.match(help.description, /^Configure authentication to instance \(encrypted;.*SN_SDK_CREDENTIALS_DIR\)$/);
  assert.deepEqual(
    help.groups.map((group) => group.title),
    ['Add', 'Delete', 'List', 'Use', 'Print', 'Options'],
  );
  const add = help.groups[0].options;
  assert.deepEqual(add.map((option) => option.name), ['add', 'type', 'alias']);
  assert.deepEqual(add[1].choices, ['basic', 'oauth']);
  assert.equal(add[1].type, 'string');
  assert.equal(add[0].description, 'Instance name or url to store authentication credentials for');
  const format = help.groups[4].options[1];
  assert.deepEqual(format.choices, ['headers', 'bearer', 'env']);
  assert.equal(format.defaultValue, 'headers');
  assert.match(help.examples, /now-sdk auth --list/);
  assert.deepEqual(ownOptions(help).map((option) => option.name), ['add', 'type', 'alias', 'delete', 'list', 'use', 'print', 'format']);
});

test('query help: parameters, short flags, required and defaults', () => {
  const help = parseHelp(fixture('query'));
  assert.deepEqual(help.parameters, [
    { name: 'table', description: 'ServiceNow table name (e.g. incident, sys_user)', isRequired: true, type: 'string' },
  ]);
  const options = Object.fromEntries(ownOptions(help).map((option) => [option.name, option]));
  assert.deepEqual(options.query.flags, ['-q', '--query']);
  assert.equal(options.query.isRequired, true);
  assert.equal(options.query.description, 'Encoded query string (sysparm_query), e.g. "active=true^priority<=2"');
  assert.equal(options.limit.type, 'number');
  assert.equal(options.limit.defaultValue, '100');
  assert.deepEqual(options['display-value'].choices, ['true', 'false', 'all']);
  assert.equal(options['display-value'].defaultValue, 'false');
  assert.equal(options['no-count'].type, 'boolean');
  assert.match(options.select.description, /records\[0\]\.sys_id/);
  assert.equal(options.auth.flags[0], '-a');
  assert.equal(options.debug, undefined);
});

test('install help: a default path broken across lines is joined', () => {
  const help = parseHelp(fixture('install'));
  const source = ownOptions(help).find((option) => option.name === 'source');
  assert.equal(source?.defaultValue, '/work/projects/my-app/.claude/worktrees/sdk-panel-22ceb0');
  assert.equal(source?.type, 'string');
  const reinstall = ownOptions(help).find((option) => option.name === 'reinstall');
  assert.match(reinstall?.description ?? '', /Warning: Metadata created on-instance that is not present locally will be lost$/);
  assert.equal(reinstall?.defaultValue, 'false');
});

test('init help: a choices list broken across lines is whole', () => {
  const help = parseHelp(fixture('init'));
  const template = ownOptions(help).find((option) => option.name === 'template');
  assert.deepEqual(template?.choices, [
    'base',
    'javascript.basic',
    'javascript.react',
    'typescript.basic',
    'typescript.react',
    'typescript.vue',
    'javascript.aiux',
    'javascript.aiux-extension',
  ]);
});

test('cicd help: sub-commands with two words', () => {
  const help = parseHelp(fixture('cicd'));
  assert.deepEqual(
    help.commands.map((command) => command.name),
    ['cicd test', 'cicd testsuite', 'cicd install', 'cicd publish', 'cicd rollback'],
  );
  assert.equal(help.commands[2].summary, 'Install an application from the application repository onto the instance');
});

test('explain help: one parameter, own options without the global ones', () => {
  const help = parseHelp(fixture('explain'));
  assert.equal(help.parameters[0].name, 'topic');
  assert.deepEqual(ownOptions(help).map((option) => option.name), ['list', 'format', 'peek']);
});

test('empty or unrelated text gives an empty result, not an error', () => {
  assert.deepEqual(parseHelp(''), { usage: '', description: '', commands: [], parameters: [], groups: [], examples: '' });
  assert.equal(parseHelp('command not found: now-sdk').commands.length, 0);
});

test('stripAnsi removes color codes', () => {
  assert.equal(stripAnsi('\u001b[36m*[dev]\u001b[39m'), '*[dev]');
});
