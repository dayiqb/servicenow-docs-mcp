import assert from 'node:assert/strict';
import { test } from 'node:test';
import { detectAiux, joinPath } from '../core/aiux.js';
import { SECRET, memoryFiles, sampleProject } from './fixtures/sample-project.js';

test('an AIUX project: configuration, pattern, pages, widgets, components, scripts', async () => {
  const project = await detectAiux(memoryFiles(sampleProject), '/app');
  assert.equal(project.isAiux, true);
  assert.equal(project.isFluent, true);
  assert.deepEqual(project.config, {
    name: 'Field Service Desk',
    basename: 'field-service-desk',
    landing: '/home',
    srcDir: 'src/lux',
    projectId: 'x_acme_fsd',
  });
  assert.equal(project.srcDir, 'src/lux');
  assert.deepEqual(project.fluent, { scope: 'x_acme_fsd', scopeId: 'a1b2c3d4e5f60718293a4b5c6d7e8f90' });
  assert.equal(project.pattern, 'production');
  assert.deepEqual(
    project.pages.map((page) => [page.route, page.isDynamic]),
    [
      ['/home', false],
      ['/list/[table]', true],
      ['/record/[table]/[id]', true],
    ],
  );
  assert.equal(project.pages[0].file, '/app/src/lux/pages/home/page.js');
  assert.deepEqual(project.widgets, [
    { name: 'open-work-orders', file: '/app/src/lux/widgets/open-work-orders/index.js', hasServerScript: true },
    { name: 'technician-map', file: '/app/src/lux/widgets/technician-map/index.js', hasServerScript: false },
  ]);
  assert.deepEqual(project.components, ['status-chip', 'work-order-card']);
  assert.deepEqual(
    project.scripts.map((script) => script.name),
    ['dev', 'build', 'deploy', 'deploy:full'],
  );
});

test('the sign-in value in aiux.json is reported, never returned', async () => {
  const project = await detectAiux(memoryFiles(sampleProject), '/app');
  assert.equal(project.hasDevelopmentToken, true);
  assert.ok(!JSON.stringify(project).includes(SECRET));
  assert.ok(!JSON.stringify(project).includes('c2FtcGxl'));
  const token = project.checks.find((check) => check.id === 'development-token');
  assert.equal(token?.status, 'problem');
});

test('a healthy project passes every structure check but the stored sign-in value', async () => {
  const project = await detectAiux(memoryFiles(sampleProject), '/app');
  const failing = project.checks.filter((check) => check.status !== 'ok').map((check) => check.id);
  assert.deepEqual(failing, ['development-token']);
});

test('structure problems are named', async () => {
  const tree = { ...sampleProject };
  tree['/app/package.json'] = JSON.stringify({ aiux: { basename: 'other-name' } });
  tree['/app/aiux.json'] = JSON.stringify({ name: 'X', basename: 'field-service-desk', landing: '/dashboard', srcDir: 'src/lux' });
  delete tree['/app/now.config.json'];
  delete tree['/app/src/lux/theme.js'];
  const project = await detectAiux(memoryFiles(tree), '/app');
  const status = Object.fromEntries(project.checks.map((check) => [check.id, check.status]));
  assert.equal(status.basename, 'problem');
  assert.equal(status['now-config'], 'missing');
  assert.equal(status.theme, 'missing');
  assert.equal(status.landing, 'problem');
  assert.equal(status['development-token'], 'ok');
  assert.match(project.checks.find((check) => check.id === 'basename')?.detail ?? '', /other-name/);
});

test('the simple pattern, and a project without srcDir', async () => {
  const project = await detectAiux(
    memoryFiles({
      '/p/aiux.json': JSON.stringify({ name: 'P', basename: 'p', landing: 'home' }),
      '/p/pages/layout.js': '',
      '/p/pages/home/page.ts': '',
    }),
    '/p',
  );
  assert.equal(project.pattern, 'simple');
  assert.equal(project.srcDir, '');
  assert.deepEqual(project.pages.map((page) => page.route), ['/home']);
  assert.equal(project.checks.find((check) => check.id === 'landing')?.status, 'ok');
});

test('a Fluent project that is not AIUX, and an empty folder', async () => {
  const fluent = await detectAiux(memoryFiles({ '/f/now.config.json': '{"scope":"x_a"}', '/f/package.json': '{"scripts":{"build":"now-sdk build"}}' }), '/f');
  assert.equal(fluent.isAiux, false);
  assert.equal(fluent.isFluent, true);
  assert.deepEqual(fluent.scripts, [{ name: 'build', command: 'now-sdk build' }]);
  assert.deepEqual(fluent.checks, []);

  const empty = await detectAiux(memoryFiles({}), '/nowhere');
  assert.equal(empty.isAiux, false);
  assert.equal(empty.isFluent, false);
  assert.deepEqual(empty.pages, []);
});

test('a broken aiux.json is reported, not thrown', async () => {
  const project = await detectAiux(memoryFiles({ '/b/aiux.json': '{ not json' }), '/b');
  assert.equal(project.isAiux, true);
  assert.equal(project.checks.find((check) => check.id === 'aiux-json')?.status, 'problem');
});

test('srcDir cannot point outside the project', async () => {
  const project = await detectAiux(
    memoryFiles({ '/q/aiux.json': JSON.stringify({ srcDir: '../../etc' }), '/q/etc/pages/x/page.js': '' }),
    '/q',
  );
  assert.equal(project.srcDir, 'etc');
  assert.deepEqual(project.pages.map((page) => page.file), ['/q/etc/pages/x/page.js']);
});

test('joinPath', () => {
  assert.equal(joinPath('/app', '', 'pages'), '/app/pages');
  assert.equal(joinPath('/app/', '/src/lux/', 'pages'), '/app/src/lux/pages');
});

test('the application version and the AIUX package it depends on are read from package.json', async () => {
  const project = await detectAiux(memoryFiles(sampleProject), '/app');
  assert.equal(project.version, '1.4.0');
  // The package named @servicenow/aiux wins over others that start with it.
  assert.deepEqual(project.framework, { name: '@servicenow/aiux', version: '^2.1.0' });
  // With the package installed, the version that runs is read from node_modules.
  const installed = await detectAiux(
    memoryFiles({ ...sampleProject, '/app/node_modules/@servicenow/aiux/package.json': JSON.stringify({ version: '2.1.3' }) }),
    '/app',
  );
  assert.deepEqual(installed.framework, { name: '@servicenow/aiux', version: '^2.1.0', installed: '2.1.3' });
  const bare = await detectAiux(memoryFiles({ '/app/aiux.json': '{}', '/app/package.json': '{}' }), '/app');
  assert.equal(bare.version, '');
  assert.equal(bare.framework, undefined);
});
