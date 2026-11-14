import assert from 'node:assert/strict';
import { test } from 'node:test';
import { COMMANDS, EFFECTS, effectsOf, findCommand } from '../core/catalog.js';
import { BLOCKED_FLAGS, classify, isReadOnly, panelEnv, toCommandLine, valueOf } from '../core/guard.js';

test('every command has a unique id, a label and a consistent confirmation', () => {
  const ids = new Set();
  for (const entry of COMMANDS) {
    assert.ok(!ids.has(entry.id), `duplicate id ${entry.id}`);
    ids.add(entry.id);
    assert.match(entry.label, /^[A-Z][a-z]/, `${entry.id}: label is sentence case`);
    assert.ok(!entry.label.endsWith('.'), `${entry.id}: label has no trailing period`);
    if (entry.changes === 'instance') {
      assert.equal(entry.confirmation, 'named', `${entry.id}: changing an instance needs the name typed`);
      assert.equal(entry.contactsInstance, true);
    }
    if (entry.confirmation === 'none') {
      assert.equal(entry.changes, 'nothing', `${entry.id}: only a command that changes nothing runs unasked`);
      assert.equal(entry.contactsInstance, false, `${entry.id}: a command that contacts an instance asks first`);
    }
    if (entry.confirmation === 'named') assert.ok(entry.namedTarget, `${entry.id}: says what to type`);
    for (const effect of effectsOf(entry)) assert.ok(effect in EFFECTS);
  }
});

test('only version, explain and the instance list run without a confirmation', () => {
  const unasked = COMMANDS.filter((entry) => entry.confirmation === 'none').map((entry) => entry.id);
  assert.deepEqual(unasked.sort(), ['auth-list', 'explain', 'version']);
});

test('effects: a download both reads the instance and changes local files', () => {
  assert.deepEqual(effectsOf(findCommand(['download', 'out'])), ['reads-instance', 'changes-local']);
  assert.deepEqual(effectsOf(findCommand(['build'])), ['changes-local']);
  assert.deepEqual(effectsOf(findCommand(['query', 'incident'])), ['reads-instance']);
  assert.deepEqual(effectsOf(findCommand(['install'])), ['changes-instance']);
  assert.deepEqual(effectsOf(findCommand(['explain', 'table-api'])), ['reads-local']);
});

test('findCommand takes the most specific entry', () => {
  assert.equal(findCommand(['auth', '--list'])?.id, 'auth-list');
  assert.equal(findCommand(['auth', '--delete', 'dev'])?.id, 'auth-delete');
  assert.equal(findCommand(['install', '--info'])?.id, 'install-info');
  assert.equal(findCommand(['install', '--auth', 'dev'])?.id, 'install');
  assert.equal(findCommand(['cicd', 'rollback'])?.id, 'cicd-rollback');
  assert.equal(findCommand(['auth']), undefined);
  assert.equal(findCommand(['nonsense']), undefined);
  assert.equal(findCommand(['build', '--version'])?.id, 'build');
});

test('read-only command lines', () => {
  for (const argv of [
    ['--version'],
    ['--help'],
    ['auth', '--help'],
    ['cicd', 'test', '--help'],
    ['auth', '--list'],
    ['explain', '--list', '--format', 'raw'],
    ['explain', 'table-api', '--peek', '--format', 'raw'],
    ['explain', 'business', '--list'],
  ]) {
    assert.equal(isReadOnly(argv), true, argv.join(' '));
  }
});

test('nothing that changes or contacts anything is read-only', () => {
  for (const argv of [
    ['auth', '--add', 'dev12345', '--type', 'oauth', '--alias', 'dev'],
    ['auth', '--use', 'dev'],
    ['auth', '--delete', 'dev'],
    ['auth', '--delete', 'all'],
    ['query', 'incident', '-q', 'active=true'],
    ['build'],
    ['clean'],
    ['install'],
    ['install', '--info'],
    ['exec', 'gs.info(1)'],
    ['cicd', 'publish'],
    ['init', '--template', 'javascript.aiux'],
    ['auth', '--list', '--add', 'x'],
    ['--version', 'install'],
    ['unknown-command'],
    [],
  ]) {
    assert.equal(isReadOnly(argv), false, argv.join(' '));
  }
});

test('a "--help" that could be a value does not make a command read-only', () => {
  assert.equal(classify(['exec', '--', '--help']).confirmation, 'blocked');
  assert.equal(classify(['query', 'incident', '-q', '--help']).confirmation, 'blocked');
  assert.equal(classify(['install', '--auth', 'dev', '--help']).confirmation, 'blocked');
});

test('flags that move or print a secret are refused on every command', () => {
  for (const flag of Object.keys(BLOCKED_FLAGS)) {
    const verdict = classify(['auth', '--add', 'dev12345', flag]);
    assert.equal(verdict.confirmation, 'blocked', flag);
    assert.ok(verdict.reason?.startsWith(flag));
  }
  assert.equal(classify(['auth', '--print']).confirmation, 'blocked');
  assert.equal(classify(['auth', '--print=dev', '--format', 'bearer']).confirmation, 'blocked');
  assert.equal(classify(['explain', 'table-api', '--debug']).confirmation, 'blocked');
});

test('confirmation levels', () => {
  assert.equal(classify(['auth', '--add', 'dev12345']).confirmation, 'terminal');
  assert.equal(classify(['auth', '--use', 'dev']).confirmation, 'review');
  assert.equal(classify(['auth', '--delete', 'dev']).confirmation, 'named');
  assert.equal(classify(['auth', '--delete']).confirmation, 'blocked');
  assert.equal(classify(['build']).confirmation, 'review');
  assert.equal(classify(['query', 'incident', '-q', 'active=true']).confirmation, 'review');
  assert.equal(classify(['install', '--reinstall']).confirmation, 'named');
  assert.equal(classify(['install', '--reinstall']).namedTarget, 'alias');
  assert.equal(classify(['exec', '--file', 'x.js']).confirmation, 'named');
});

test('malformed command lines are refused', () => {
  assert.equal(classify(/** @type {any} */ ('build')).confirmation, 'blocked');
  assert.equal(classify(/** @type {any} */ (['build', 1])).confirmation, 'blocked');
  assert.equal(classify(['explain', 'a\nb']).confirmation, 'blocked');
  assert.equal(classify(['explain', 'table-api', '--output', 'x']).confirmation, 'blocked');
});

test('valueOf reads both flag forms', () => {
  assert.equal(valueOf(['auth', '--delete', 'dev'], '--delete'), 'dev');
  assert.equal(valueOf(['auth', '--delete=dev'], '--delete'), 'dev');
  assert.equal(valueOf(['auth', '--delete', '--list'], '--delete'), undefined);
  assert.equal(valueOf(['auth'], '--delete'), undefined);
});

test('toCommandLine quotes what a shell would split', () => {
  assert.equal(toCommandLine(['auth', '--list']), 'now-sdk auth --list');
  assert.equal(
    toCommandLine(['query', 'incident', '-q', 'active=true^priority<=2']),
    "now-sdk query incident -q 'active=true^priority<=2'",
  );
  assert.equal(toCommandLine(['exec', "gs.info('x')"]), "now-sdk exec 'gs.info('\\''x'\\'')'");
});

test('the SDK telemetry is on unless the setting turns it off', () => {
  assert.equal(panelEnv().NO_TELEMETRY, undefined);
  assert.equal(panelEnv({ telemetry: true }).NO_TELEMETRY, undefined);
  assert.equal(panelEnv({ telemetry: false }).NO_TELEMETRY, '1');
  assert.equal(panelEnv().NO_COLOR, '1');
});
