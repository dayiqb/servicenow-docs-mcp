// @ts-check
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { expandHome, extensionFolders, homeFolder } from '../core/extensions.js';

test('on macOS the extensions are under Application Support, tried first', () => {
  const folders = extensionFolders({ HOME: '/Users/ada' });
  assert.equal(folders[0], '/Users/ada/Library/Application Support/Claude/Claude Extensions');
  assert.ok(folders.includes('/Users/ada/.config/Claude/Claude Extensions'));
});

test('on Windows they are under APPDATA, or Roaming in the home folder when it is unset', () => {
  assert.ok(
    extensionFolders({ USERPROFILE: 'C:\\Users\\ada', APPDATA: 'C:\\Users\\ada\\AppData\\Roaming' }).includes(
      'C:\\Users\\ada\\AppData\\Roaming/Claude/Claude Extensions',
    ),
  );
  assert.ok(extensionFolders({ USERPROFILE: 'C:\\Users\\ada' }).includes('C:\\Users\\ada/AppData/Roaming/Claude/Claude Extensions'));
});

test('on Linux XDG_CONFIG_HOME wins over ~/.config', () => {
  const folders = extensionFolders({ HOME: '/home/ada', XDG_CONFIG_HOME: '/cfg' });
  assert.ok(folders.includes('/cfg/Claude/Claude Extensions'));
  assert.ok(!folders.includes('/home/ada/.config/Claude/Claude Extensions'));
});

test('with nothing known there is nowhere to look', () => {
  assert.deepEqual(extensionFolders({}), []);
  assert.equal(homeFolder({}), '');
});

test('a leading ~ is the home folder, with either slash', () => {
  assert.equal(expandHome(' ~/docs ', '/Users/ada'), '/Users/ada/docs');
  assert.equal(expandHome('~\\docs', 'C:\\Users\\ada'), 'C:\\Users\\ada\\docs');
  assert.equal(expandHome('~docs', '/Users/ada'), '~docs');
  assert.equal(expandHome('~/docs', ''), '~/docs');
});
