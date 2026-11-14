import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { classify } from '../core/guard.js';
import {
  addInstanceArgv,
  diffInstances,
  isValidAlias,
  normalizeHost,
  parseAuthList,
  removeInstanceArgv,
  useInstanceArgv,
} from '../core/instances.js';

const listed = readFileSync(new URL('./fixtures/auth-list.txt', import.meta.url), 'utf8');

test('the list is read: alias, address, sign-in type, default', () => {
  assert.deepEqual(parseAuthList(listed), [
    { alias: 'dev', host: 'https://dev12345.service-now.com', signIn: 'oauth', isDefault: true },
    { alias: 'test', host: 'https://acmetest.service-now.com', signIn: 'basic', isDefault: false },
    { alias: 'prod', host: 'https://acme.service-now.com', signIn: 'oauth', isDefault: false },
  ]);
});

test('the user name is never kept', () => {
  assert.ok(!JSON.stringify(parseAuthList(listed)).includes('sample.user'));
});

test('color codes and Windows line ends do not matter', () => {
  const colored = '\u001b[36m*[dev]\u001b[39m\r\n      host = https://dev12345.service-now.com\r\n      type = basic\r\n      \u001b[1m\u001b[32mdefault = Yes\u001b[39m\u001b[22m\r\n';
  assert.deepEqual(parseAuthList(colored), [
    { alias: 'dev', host: 'https://dev12345.service-now.com', signIn: 'basic', isDefault: true },
  ]);
});

test('an address stored with a trailing slash is shown without it', () => {
  const listed = '[demo]\n      host = https://demo.service-now.com/\n      type = basic\n      default = No\n';
  assert.equal(parseAuthList(listed)[0].host, 'https://demo.service-now.com');
});

test('no credentials, an error text or nothing at all give an empty list', () => {
  assert.deepEqual(parseAuthList('[INFO] No credentials found\n'), []);
  assert.deepEqual(parseAuthList('Stored credentials at /x could not be read.'), []);
  assert.deepEqual(parseAuthList(''), []);
});

test('an address is normalized the way the SDK does it', () => {
  assert.deepEqual(normalizeHost('dev12345'), { host: 'https://dev12345.service-now.com' });
  assert.deepEqual(normalizeHost(' DEV12345.service-now.com '), { host: 'https://dev12345.service-now.com' });
  assert.deepEqual(normalizeHost('https://sn.example.com/login'), { host: 'https://sn.example.com' });
  assert.ok('error' in normalizeHost(''));
  assert.ok('error' in normalizeHost('http://dev12345.service-now.com'));
  assert.ok('error' in normalizeHost('https://admin:secret@dev12345.service-now.com'));
  assert.ok('error' in normalizeHost('dev 12345'));
  assert.ok('error' in normalizeHost('--print'));
});

test('aliases', () => {
  assert.equal(isValidAlias('dev'), true);
  assert.equal(isValidAlias('acme-test_2'), true);
  assert.equal(isValidAlias('all'), false);
  assert.equal(isValidAlias('--list'), false);
  assert.equal(isValidAlias('a b'), false);
  assert.equal(isValidAlias(''), false);
});

test('the sign-in command never carries a user name or a password', () => {
  const built = addInstanceArgv({ host: 'dev12345', signIn: 'oauth', alias: 'dev' });
  assert.deepEqual(built, {
    argv: ['auth', '--add', 'https://dev12345.service-now.com', '--type', 'oauth', '--alias', 'dev'],
  });
  assert.equal(classify(/** @type {{argv: string[]}} */ (built).argv).confirmation, 'terminal');
  assert.ok('error' in addInstanceArgv({ host: 'dev12345', signIn: 'oauth', alias: 'all' }));
  assert.ok('error' in addInstanceArgv({ host: '', signIn: 'oauth', alias: 'dev' }));
  assert.ok('error' in addInstanceArgv({ host: 'dev12345', signIn: /** @type {any} */ ('token'), alias: 'dev' }));
});

test('use and remove work on listed aliases only', () => {
  const known = parseAuthList(listed);
  assert.deepEqual(useInstanceArgv('test', known), { argv: ['auth', '--use', 'test'] });
  assert.ok('error' in useInstanceArgv('nope', known));
  assert.deepEqual(removeInstanceArgv('test', known), { argv: ['auth', '--delete', 'test'] });
  assert.ok('error' in removeInstanceArgv('all', known));
  assert.ok('error' in removeInstanceArgv('nope', known));
});

test('the outcome of a sign-in is read from two lists', () => {
  const before = parseAuthList(listed);
  const after = [
    ...before.filter((instance) => instance.alias !== 'test').map((instance) => ({ ...instance, isDefault: false })),
    { alias: 'uat', host: 'https://acmeuat.service-now.com', signIn: /** @type {const} */ ('oauth'), isDefault: true },
  ];
  assert.deepEqual(diffInstances(before, after), { added: ['uat'], removed: ['test'], defaultAlias: 'uat' });
  assert.deepEqual(diffInstances(before, before), { added: [], removed: [], defaultAlias: 'dev' });
});
