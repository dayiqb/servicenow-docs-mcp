// @ts-check
/**
 * Finds out whether a folder is an AIUX project and what it holds: its
 * configuration, pages, widgets, npm scripts and a few structure checks.
 *
 * It reads files through a small interface (`ProjectFiles`) so the same code
 * runs from the command line (Node), from the Claude Code panel (`$.fs`) and
 * in tests (an object in memory). It only reads.
 *
 * `aiux.json` can hold `development.token`, a Basic sign-in value. This
 * module never returns it: it reports that one is present and nothing more.
 *
 * The layout comes from the `aiux-build` skill: `aiux.json`, `package.json`
 * and `now.config.json` at the project root; pages as
 * `<srcDir>/pages/<route>/page.js`; widgets as `<srcDir>/widgets/<name>/index.js`.
 *
 * No Node imports.
 */

/**
 * @typedef {object} ProjectFiles
 * @property {(path: string) => Promise<string | null>} readText
 *   The file's text, or null when there is no such file.
 * @property {(path: string) => Promise<{ name: string, isDirectory: boolean }[] | null>} listDirectory
 *   The folder's entries, or null when there is no such folder.
 */

/**
 * @typedef {'ok' | 'problem' | 'missing'} CheckStatus
 */

/**
 * @typedef {object} Check
 * @property {string} id
 * @property {string} label
 * @property {CheckStatus} status
 * @property {string} [detail]
 */

/**
 * @typedef {object} AiuxProject
 * @property {boolean} isAiux
 * @property {boolean} isFluent          True when now.config.json is present.
 * @property {string} root
 * @property {{ name?: string, basename?: string, landing?: string, srcDir?: string, projectId?: string }} config
 * @property {string} srcDir             Relative to the root; "" when unset.
 * @property {boolean} hasDevelopmentToken
 * @property {{ scope?: string, scopeId?: string }} fluent
 * @property {'simple' | 'production' | undefined} pattern
 * @property {string} version            The application's own version in package.json; "" when unset.
 * @property {{ name: string, version: string, installed?: string } | undefined} framework  The AIUX package the project depends on: the version package.json asks for, and the one installed in node_modules when it is there.
 * @property {{ route: string, file: string, isDynamic: boolean }[]} pages
 * @property {{ name: string, file: string, hasServerScript: boolean }[]} widgets
 * @property {string[]} components
 * @property {{ name: string, command: string }[]} scripts
 * @property {Check[]} checks
 */

/**
 * The AIUX package a project depends on: the one named @servicenow/aiux if
 * there is one, else the first whose name starts with it, looked for in the
 * dependencies and then the development dependencies.
 *
 * @param {Record<string, unknown>} packageJson
 * @returns {{ name: string, version: string, installed?: string } | undefined}
 */
function aiuxDependency(packageJson) {
  /** @type {[string, string][]} */
  const found = [];
  for (const key of ['dependencies', 'devDependencies']) {
    const group = packageJson[key];
    if (!isRecord(group)) continue;
    for (const [name, version] of Object.entries(group)) {
      if (name.startsWith('@servicenow/aiux') && typeof version === 'string') found.push([name, version]);
    }
  }
  const best = found.find(([name]) => name === '@servicenow/aiux') ?? found[0];
  return best ? { name: best[0], version: best[1] } : undefined;
}

const PAGE_FILES = new Set(['page.js', 'page.ts']);
const SCRIPT_NAMES = ['dev', 'build', 'deploy', 'deploy:full'];
const MAX_DEPTH = 8;
const MAX_ENTRIES = 2000;

/**
 * @param {ProjectFiles} files
 * @param {string} root the folder to look at
 * @returns {Promise<AiuxProject>}
 */
export async function detectAiux(files, root) {
  const aiuxJson = await readJson(files, joinPath(root, 'aiux.json'));
  const packageJson = await readJson(files, joinPath(root, 'package.json'));
  const nowConfig = await readJson(files, joinPath(root, 'now.config.json'));

  const aiux = aiuxJson.value;
  const config = pick(aiux, ['name', 'basename', 'landing', 'srcDir', 'projectId']);
  const srcDir = typeof config.srcDir === 'string' ? trimSlashes(config.srcDir) : '';
  const source = joinPath(root, srcDir);

  /** @type {AiuxProject} */
  const project = {
    isAiux: aiuxJson.exists,
    isFluent: nowConfig.exists,
    root,
    config,
    srcDir,
    hasDevelopmentToken: Boolean(isRecord(aiux) && isRecord(aiux.development) && aiux.development.token),
    fluent: pick(nowConfig.value, ['scope', 'scopeId']),
    pattern: undefined,
    version: '',
    framework: undefined,
    pages: [],
    widgets: [],
    components: [],
    scripts: [],
    checks: [],
  };

  if (isRecord(packageJson.value)) {
    if (typeof packageJson.value.version === 'string') project.version = packageJson.value.version;
    project.framework = aiuxDependency(packageJson.value);
    if (project.framework) {
      // What is installed, which is what runs: the package's own package.json in node_modules.
      const installed = await readJson(files, joinPath(root, 'node_modules', project.framework.name, 'package.json'));
      if (isRecord(installed.value) && typeof installed.value.version === 'string') project.framework.installed = installed.value.version;
    }
  }
  if (isRecord(packageJson.value) && isRecord(packageJson.value.scripts)) {
    const scripts = packageJson.value.scripts;
    for (const name of SCRIPT_NAMES) {
      const command = scripts[name];
      if (typeof command === 'string') project.scripts.push({ name, command });
    }
  }
  if (!project.isAiux) return project;

  const hasLayout = (await files.readText(joinPath(source, 'pages', 'layout.js'))) !== null;
  const hasApplication = (await files.readText(joinPath(source, 'application.js'))) !== null;
  const hasTheme = (await files.readText(joinPath(source, 'theme.js'))) !== null;
  project.pattern = hasApplication ? 'production' : hasLayout ? 'simple' : undefined;

  project.pages = await findPages(files, source);
  project.widgets = await findWidgets(files, source);
  project.components = await findComponents(files, source);

  const packageBasename =
    isRecord(packageJson.value) && isRecord(packageJson.value.aiux) ? packageJson.value.aiux.basename : undefined;
  const landingRoute = typeof config.landing === 'string' ? trimSlashes(config.landing) : undefined;

  project.checks = [
    check('aiux-json', 'aiux.json is valid JSON', aiuxJson.isValid ? 'ok' : 'problem'),
    check(
      'package-json',
      'package.json is present',
      packageJson.exists ? (packageJson.isValid ? 'ok' : 'problem') : 'missing',
    ),
    check(
      'basename',
      'package.json aiux.basename matches aiux.json basename',
      !packageJson.exists || packageBasename === undefined
        ? 'missing'
        : packageBasename === config.basename
          ? 'ok'
          : 'problem',
      packageBasename !== undefined && packageBasename !== config.basename
        ? `package.json has "${String(packageBasename)}", aiux.json has "${String(config.basename)}".`
        : undefined,
    ),
    check('now-config', 'now.config.json is present', nowConfig.exists ? 'ok' : 'missing'),
    check(
      'entry',
      'pages/layout.js or application.js is present',
      project.pattern ? 'ok' : 'missing',
      project.pattern ? `${project.pattern} pattern` : undefined,
    ),
    check('theme', 'theme.js is present', hasTheme ? 'ok' : 'missing'),
    check(
      'landing',
      'The landing page exists',
      landingRoute === undefined
        ? 'missing'
        : project.pages.some((page) => page.route === `/${landingRoute}`)
          ? 'ok'
          : 'problem',
      landingRoute === undefined ? 'aiux.json has no landing.' : `landing is /${landingRoute}`,
    ),
    check(
      'development-token',
      project.hasDevelopmentToken ? 'aiux.json holds a sign-in value' : 'No sign-in value is stored in aiux.json',
      project.hasDevelopmentToken ? 'problem' : 'ok',
      project.hasDevelopmentToken
        ? 'aiux.json has development.token. Keep the file out of version control.'
        : undefined,
    ),
  ];
  return project;
}

/**
 * @param {ProjectFiles} files
 * @param {string} source
 */
async function findPages(files, source) {
  /** @type {AiuxProject['pages']} */
  const pages = [];
  const pagesRoot = joinPath(source, 'pages');
  await walk(files, pagesRoot, (folder, entry) => {
    if (entry.isDirectory || !PAGE_FILES.has(entry.name)) return;
    const route = folder.slice(pagesRoot.length).replace(/^\/+/, '');
    if (route.split('/').some((part) => part === '_variants' || part === 'components')) return;
    pages.push({
      route: `/${route}`,
      file: joinPath(folder, entry.name),
      isDynamic: /\[[^\]]+\]/.test(route),
    });
  });
  pages.sort((a, b) => a.route.localeCompare(b.route));
  return pages;
}

/**
 * @param {ProjectFiles} files
 * @param {string} source
 */
async function findWidgets(files, source) {
  /** @type {AiuxProject['widgets']} */
  const widgets = [];
  const widgetsRoot = joinPath(source, 'widgets');
  const folders = (await files.listDirectory(widgetsRoot)) ?? [];
  for (const folder of folders) {
    if (!folder.isDirectory) continue;
    const entries = (await files.listDirectory(joinPath(widgetsRoot, folder.name))) ?? [];
    const index = entries.find((entry) => entry.name === 'index.js' || entry.name === 'index.ts');
    if (!index) continue;
    widgets.push({
      name: folder.name,
      file: joinPath(widgetsRoot, folder.name, index.name),
      hasServerScript: entries.some((entry) => /^server(-script)?\.(js|ts)$/.test(entry.name)),
    });
  }
  widgets.sort((a, b) => a.name.localeCompare(b.name));
  return widgets;
}

/**
 * @param {ProjectFiles} files
 * @param {string} source
 */
async function findComponents(files, source) {
  const entries = (await files.listDirectory(joinPath(source, 'components'))) ?? [];
  return entries
    .map((entry) => (entry.isDirectory ? entry.name : entry.name.replace(/\.(js|ts)$/, '')))
    .filter((name) => !name.startsWith('.'))
    .sort((a, b) => a.localeCompare(b));
}

/**
 * Calls `visit` for every entry under `folder`, depth first, within limits
 * that keep a mistaken root (a home folder) from being walked whole.
 *
 * @param {ProjectFiles} files
 * @param {string} folder
 * @param {(folder: string, entry: { name: string, isDirectory: boolean }) => void} visit
 */
async function walk(files, folder, visit) {
  let seen = 0;
  /** @param {string} current @param {number} depth */
  const step = async (current, depth) => {
    if (depth > MAX_DEPTH || seen > MAX_ENTRIES) return;
    const entries = await files.listDirectory(current);
    if (!entries) return;
    for (const entry of entries) {
      seen += 1;
      if (seen > MAX_ENTRIES) return;
      if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue;
      visit(current, entry);
      if (entry.isDirectory) await step(joinPath(current, entry.name), depth + 1);
    }
  };
  await step(folder, 0);
}

/**
 * @param {ProjectFiles} files
 * @param {string} path
 * @returns {Promise<{ exists: boolean, isValid: boolean, value: unknown }>}
 */
async function readJson(files, path) {
  const text = await files.readText(path);
  if (text === null) return { exists: false, isValid: false, value: undefined };
  try {
    return { exists: true, isValid: true, value: JSON.parse(text) };
  } catch {
    return { exists: true, isValid: false, value: undefined };
  }
}

/**
 * The named keys of `value` that hold text, and nothing else of it.
 *
 * @template {string} K
 * @param {unknown} value
 * @param {readonly K[]} keys
 * @returns {{ [key in K]?: string }}
 */
function pick(value, keys) {
  /** @type {{ [key in K]?: string }} */
  const picked = {};
  if (!isRecord(value)) return picked;
  for (const key of keys) {
    const one = value[key];
    if (typeof one === 'string') picked[key] = one;
  }
  return picked;
}

/** @param {unknown} value @returns {value is Record<string, unknown>} */
function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * @param {string} id
 * @param {string} label
 * @param {CheckStatus} status
 * @param {string} [detail]
 * @returns {Check}
 */
function check(id, label, status, detail) {
  return detail ? { id, label, status, detail } : { id, label, status };
}

/** @param {string} path */
function trimSlashes(path) {
  return path.replace(/^[./]+/, '').replace(/\/+$/, '');
}

/**
 * Joins path parts with "/", skipping empty ones.
 *
 * @param {...string} parts
 */
export function joinPath(...parts) {
  return parts
    .filter((part) => part !== '')
    .map((part, index) => (index === 0 ? part.replace(/\/+$/, '') : part.replace(/^\/+|\/+$/g, '')))
    .join('/');
}
