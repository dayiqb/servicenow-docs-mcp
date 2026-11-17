// @ts-check
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { chooseProject, findProjects } from '../core/projects.js';
import { memoryFiles } from './fixtures/sample-project.js';

/** A workspace like the one the AIUX tab got wrong: projects one level down, copies in agent worktrees. */
const workspace = memoryFiles({
  '/ws/CLAUDE.md': '# notes',
  '/ws/scripts/build.py': '',
  '/ws/sg-resource-booking/now.config.json': '{}',
  '/ws/skygard-avs-aiux/now.config.json': '{}',
  '/ws/skygard-avs-aiux/aiux.json': '{}',
  '/ws/skygard-avs-aiux/.claude/worktrees/agent-a7/aiux.json': '{}',
  '/ws/skygard-avs-aiux/node_modules/x/now.config.json': '{}',
  '/ws/skygard-order-to-cash/now.config.json': '{}',
  '/ws/clients/acme/now.config.json': '{}',
  '/ws/clients/acme/deeper/still/now.config.json': '{}',
  '/ws/.git/now.config.json': '{}',
  '/ws/node_modules/pkg/aiux.json': '{}',
  '/ws/.hidden/aiux.json': '{}',
});

test('a folder that is a project is the one project, and nothing under it is looked at', async () => {
  const files = memoryFiles({ '/app/aiux.json': '{}', '/app/now.config.json': '{}', '/app/sub/now.config.json': '{}' });
  assert.deepEqual(await findProjects(files, '/app'), [{ folder: '/app', path: '', isAiux: true, isFluent: true }]);
});

test('in a workspace the projects one and two levels down are found, in name order', async () => {
  assert.deepEqual(await findProjects(workspace, '/ws'), [
    { folder: '/ws/clients/acme', path: 'clients/acme', isAiux: false, isFluent: true },
    { folder: '/ws/sg-resource-booking', path: 'sg-resource-booking', isAiux: false, isFluent: true },
    { folder: '/ws/skygard-avs-aiux', path: 'skygard-avs-aiux', isAiux: true, isFluent: true },
    { folder: '/ws/skygard-order-to-cash', path: 'skygard-order-to-cash', isAiux: false, isFluent: true },
  ]);
});

test('node_modules and folders whose name starts with a dot are passed over, so agent worktrees are not projects', async () => {
  const folders = (await findProjects(workspace, '/ws')).map((project) => project.folder);
  assert.ok(!folders.some((folder) => /node_modules|\/\.|deeper/.test(folder)));
});

test('a folder inside a project, even under a dot folder, is in that project', async () => {
  assert.deepEqual(await findProjects(workspace, '/ws/skygard-avs-aiux/.superpowers/sdd/plan'), [
    { folder: '/ws/skygard-avs-aiux', path: '', isAiux: true, isFluent: true, isAbove: true },
  ]);
  // The nearest project above wins over one further up.
  const nested = memoryFiles({ '/a/now.config.json': '{}', '/a/b/aiux.json': '{}', '/a/b/c/d/x.txt': '' });
  assert.equal((await findProjects(nested, '/a/b/c/d'))[0]?.folder, '/a/b');
  // On Windows too.
  const windows = memoryFiles({ 'C:\\Users\\ada\\app/aiux.json': '{}' });
  assert.equal((await findProjects(windows, 'C:\\Users\\ada\\app\\src'))[0]?.folder, 'C:\\Users\\ada\\app');
});

test('the look upward is bounded: four levels, not the home folder, not past a repository root', async () => {
  // Five levels up is too far.
  const far = memoryFiles({ '/p/aiux.json': '{}', '/p/a/b/c/d/e/x.txt': '' });
  assert.deepEqual(await findProjects(far, '/p/a/b/c/d/e'), []);
  assert.equal((await findProjects(far, '/p/a/b/c/d'))[0]?.folder, '/p');
  // A project in the home folder, or above it, is not one the session works on.
  const home = memoryFiles({ '/Users/ada/now.config.json': '{}', '/Users/ada/notes/x.txt': '' });
  assert.deepEqual(await findProjects(home, '/Users/ada/notes', { home: '/Users/ada' }), []);
  // A repository's root ends the look: a project above it is another one.
  const repo = memoryFiles({ '/w/now.config.json': '{}', '/w/repo/.git/HEAD': '', '/w/repo/docs/x.txt': '' });
  assert.deepEqual(await findProjects(repo, '/w/repo/docs'), []);
});

test('a project above and others under are all found, so the person picks', async () => {
  const both = memoryFiles({ '/app/aiux.json': '{}', '/app/work/one/now.config.json': '{}', '/app/work/two/now.config.json': '{}' });
  const projects = await findProjects(both, '/app/work');
  assert.deepEqual(
    projects.map((project) => [project.folder, Boolean(project.isAbove)]),
    [
      ['/app', true],
      ['/app/work/one', false],
      ['/app/work/two', false],
    ],
  );
  assert.deepEqual(chooseProject(projects, ''), { kind: 'pick' });
});

test('a folder with no project anywhere near gives none', async () => {
  assert.deepEqual(await findProjects(memoryFiles({ '/empty/readme.md': '' }), '/empty'), []);
  assert.deepEqual(await findProjects(memoryFiles({}), '/missing'), []);
});

test('one project is used; several wait for a pick, which is kept', () => {
  const one = { folder: '/ws/a', path: 'a', isAiux: true, isFluent: true };
  const two = { folder: '/ws/b', path: 'b', isAiux: false, isFluent: true };
  assert.deepEqual(chooseProject([], ''), { kind: 'none' });
  assert.deepEqual(chooseProject([one], ''), { kind: 'one', project: one });
  assert.deepEqual(chooseProject([one, two], ''), { kind: 'pick' });
  assert.deepEqual(chooseProject([one, two], '/ws/b'), { kind: 'chosen', project: two });
  // A pick of a folder that is no longer a project is forgotten.
  assert.deepEqual(chooseProject([one, two], '/ws/gone'), { kind: 'pick' });
});
