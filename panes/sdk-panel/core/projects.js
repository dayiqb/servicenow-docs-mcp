// @ts-check
/**
 * Finds the ServiceNow projects in a folder. A session's folder is often a
 * workspace that holds several projects rather than one, so when the folder is
 * not a project itself, its subfolders are looked in, two levels down.
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
 */

/** How many levels under the folder are looked in. */
export const PROJECT_DEPTH = 2;

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
