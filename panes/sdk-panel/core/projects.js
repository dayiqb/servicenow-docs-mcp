// @ts-check
/**
 * Finds the ServiceNow projects for a folder. The folder itself first; then the
 * folders above it, since a session can work in a folder inside a project; then,
 * as a session's folder is often a workspace that holds several projects, the
 * folders under it, two levels down.
 *
 * A project has `now.config.json` (a Fluent application) or `aiux.json` (an
 * AIUX application) at its root. Nothing under a project is looked in, nor
 * node_modules or a folder whose name starts with a dot (.git, .claude and the
 * agent worktrees in it).
 */
import { joinPath } from './aiux.js';

/**
 * @typedef {object} Project
 * @property {string} folder   Absolute.
 * @property {string} path     Relative to the folder looked in; '' for that folder itself.
 * @property {boolean} isAiux
 * @property {boolean} isFluent
 * @property {boolean} [isAbove] True when the folder looked in is inside this project.
 */

/** How many levels under the folder are looked in. */
export const PROJECT_DEPTH = 2;

/**
 * The folder a folder is in, or '' at the top. Takes "/" and "\\".
 *
 * @param {string} folder
 */
export function parentOf(folder) {
  const trimmed = folder.replace(/[\\/]+$/, '');
  const cut = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
  if (cut < 0) return '';
  const parent = trimmed.slice(0, cut);
  // "/Users" has "/" above it; "C:\\Users" has "C:\\".
  if (parent === '') return trimmed === '/' ? '' : '/';
  if (/^[A-Za-z]:$/.test(parent)) return `${parent}\\`;
  return parent;
}

/** @param {string} name */
function isPassedOver(name) {
  return name.startsWith('.') || name === 'node_modules';
}

/**
 * @param {import('./aiux.js').ProjectFiles} files
 * @param {string} folder
 * @param {string} path
 * @returns {Promise<Project | null>}
 */
async function projectAt(files, folder, path) {
  const [aiux, fluent] = await Promise.all([
    files.readText(joinPath(folder, 'aiux.json')),
    files.readText(joinPath(folder, 'now.config.json')),
  ]);
  if (aiux === null && fluent === null) return null;
  return { folder, path, isAiux: aiux !== null, isFluent: fluent !== null };
}

/**
 * @param {import('./aiux.js').ProjectFiles} files
 * @param {string} root
 * @param {number} [depth]
 * @returns {Promise<Project[]>}
 */
export async function findProjects(files, root, depth = PROJECT_DEPTH) {
  const self = await projectAt(files, root, '');
  if (self) return [self];
  // A session can work in a folder inside a project (its notes, a plan folder,
  // a dot folder): the nearest project above is the one it works on.
  for (let folder = parentOf(root); folder; folder = parentOf(folder)) {
    const above = await projectAt(files, folder, '');
    if (above) return [{ ...above, isAbove: true }];
  }
  /** @type {Project[]} */
  const found = [];
  /** @param {string} folder @param {string} path @param {number} level */
  const look = async (folder, path, level) => {
    const entries = (await files.listDirectory(folder)) ?? [];
    const folders = entries.filter((entry) => entry.isDirectory && !isPassedOver(entry.name));
    await Promise.all(
      folders.map(async (entry) => {
        const child = joinPath(folder, entry.name);
        const childPath = path ? `${path}/${entry.name}` : entry.name;
        const project = await projectAt(files, child, childPath);
        if (project) found.push(project);
        else if (level < depth) await look(child, childPath, level + 1);
      }),
    );
  };
  await look(root, '', 1);
  return found.sort((left, right) => left.path.localeCompare(right.path));
}

/**
 * Which project the panel works in: the only one, or the one picked before.
 * With several and no pick that still holds, the person picks.
 *
 * @param {Project[]} projects
 * @param {string} remembered the folder picked before, or ''
 * @returns {{ kind: 'none' } | { kind: 'pick' } | { kind: 'one' | 'chosen', project: Project }}
 */
export function chooseProject(projects, remembered) {
  if (projects.length === 0) return { kind: 'none' };
  if (projects.length === 1 && projects[0]) return { kind: 'one', project: projects[0] };
  const picked = projects.find((project) => project.folder === remembered);
  return picked ? { kind: 'chosen', project: picked } : { kind: 'pick' };
}
