import assert from 'node:assert/strict';
import { test } from 'node:test';
import { compareVersions, evaluateSetup } from '../core/setup.js';

const good = {
  nodeVersion: 'v26.8.1',
  sdkVersion: '4.14.0',
  topicCount: 265,
  instances: [{ alias: 'dev', host: 'https://dev12345.service-now.com', signIn: /** @type {const} */ ('oauth'), isDefault: true }],
  docs: { kind: 'folder', version: '0.1.7' },
};
const statusOf = (result, id) => result.checks.find((check) => check.id === id)?.status;

test('a complete setup is ok', () => {
  const result = evaluateSetup(good);
  assert.equal(result.status, 'ok');
  assert.deepEqual(result.checks.map((check) => check.id), ['node', 'sdk', 'explain', 'instances', 'docs']);
  assert.equal(result.checks[3].value, '1, default dev');
  assert.equal(result.checks[2].value, '265 topics');
});

test('a missing or old SDK is a problem with a fix', () => {
  const missing = evaluateSetup({ ...good, sdkVersion: null, topicCount: null });
  assert.equal(missing.status, 'problem');
  assert.match(missing.checks[1].fix ?? '', /npm install -g @servicenow\/sdk@latest/);
  assert.equal(statusOf(evaluateSetup({ ...good, sdkVersion: '4.5.9' }), 'sdk'), 'problem');
  assert.equal(statusOf(evaluateSetup({ ...good, sdkVersion: '4.7.0' }), 'sdk'), 'attention');
  assert.equal(statusOf(evaluateSetup({ ...good, sdkVersion: '4.8.0' }), 'sdk'), 'ok');
});

test('Node below 20 is a problem', () => {
  assert.equal(statusOf(evaluateSetup({ ...good, nodeVersion: 'v18.19.0' }), 'node'), 'problem');
  assert.equal(statusOf(evaluateSetup({ ...good, nodeVersion: null }), 'node'), 'problem');
  assert.equal(statusOf(evaluateSetup({ ...good, nodeVersion: 'v20.0.0' }), 'node'), 'ok');
});

test('instances: not read, none, no default', () => {
  const unread = evaluateSetup({ ...good, instances: null, instancesError: 'Not read.' });
  assert.equal(statusOf(unread, 'instances'), 'unknown');
  assert.equal(unread.status, 'unknown');
  assert.equal(statusOf(evaluateSetup({ ...good, instances: [] }), 'instances'), 'attention');
  const noDefault = evaluateSetup({ ...good, instances: [{ ...good.instances[0], isDefault: false }] });
  assert.equal(statusOf(noDefault, 'instances'), 'attention');
  assert.equal(noDefault.checks[3].fix, 'Set a default instance.');
});

test('the docs extension is optional, and an old one is named', () => {
  assert.equal(statusOf(evaluateSetup({ ...good, docs: { kind: 'none' } }), 'docs'), 'attention');
  const old = evaluateSetup({ ...good, docs: { kind: 'old', version: '0.1.6' } });
  assert.equal(old.checks.find((check) => check.id === 'docs')?.value, '0.1.6, too old');
  assert.equal(statusOf(evaluateSetup({ ...good, docs: { kind: 'path' } }), 'docs'), 'ok');
  assert.equal(evaluateSetup({ ...good, docs: null }).checks.some((check) => check.id === 'docs'), false);
});

test('compareVersions', () => {
  assert.ok(compareVersions('4.14.0', '4.6.0') > 0);
  assert.ok(compareVersions('v20.0.0', '20') === 0);
  assert.ok(compareVersions('4.6.0-beta.1', '4.6.0') === 0);
  assert.ok(compareVersions('3.9', '4.0.0') < 0);
});
