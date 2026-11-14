// @ts-check
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { isPackageName, isUpdateAvailable, latestCommand, updateCommand } from '../core/updates.js';

test('an update is there when the newest version is later than the one installed', () => {
  assert.equal(isUpdateAvailable('4.15.0', '4.14.0'), true);
  assert.equal(isUpdateAvailable('4.14.0', '4.14.0'), false);
  assert.equal(isUpdateAvailable('4.13.9', '4.14.0'), false);
  assert.equal(isUpdateAvailable('', '4.14.0'), false);
  assert.equal(isUpdateAvailable('4.15.0', undefined), false);
  assert.equal(isUpdateAvailable('not a version', '4.14.0'), false);
});

test('the commands that ask for and install the newest version', () => {
  assert.deepEqual(latestCommand('@servicenow/sdk'), { program: 'npm', argv: ['view', '@servicenow/sdk', 'version'] });
  assert.deepEqual(updateCommand({ kind: 'sdk' }), { program: 'npm', argv: ['install', '--global', '@servicenow/sdk@latest'] });
  assert.deepEqual(updateCommand({ kind: 'project', name: '@servicenow/aiux', manager: 'pnpm' }), {
    program: 'pnpm',
    argv: ['update', '@servicenow/aiux', '--latest'],
  });
  assert.deepEqual(updateCommand({ kind: 'project', name: '@servicenow/aiux', manager: 'npm' }), {
    program: 'npm',
    argv: ['install', '@servicenow/aiux@latest'],
  });
});

test('a name that is not a package name is refused, so a file cannot slip in an option', () => {
  for (const name of ['--global', '../x', '@servicenow/aiux --registry=http://x', '', 'A b']) {
    assert.equal(isPackageName(name), false);
    assert.throws(() => latestCommand(name));
    assert.throws(() => updateCommand({ kind: 'project', name, manager: 'npm' }));
  }
});
