// @ts-check
/**
 * Where Claude Desktop keeps its extensions, per operating system. The docs
 * extension is looked for there.
 *
 * Only the macOS folder has been seen on a real computer. The Windows and
 * Linux ones follow where Claude Desktop keeps its data on those systems.
 */

/** The folder's own name, the same on every system. */
export const EXTENSIONS_FOLDER = 'Claude/Claude Extensions';

/**
 * @typedef {object} FolderEnvironment
 * @property {string} [HOME]
 * @property {string} [USERPROFILE]     The home folder on Windows.
 * @property {string} [APPDATA]         Windows; `<home>\AppData\Roaming` when unset.
 * @property {string} [XDG_CONFIG_HOME] Linux; `~/.config` when unset.
 */

/**
 * The home folder: HOME where it is set, else the Windows one.
 *
 * @param {FolderEnvironment} env
 */
export function homeFolder(env) {
  return (env.HOME || env.USERPROFILE || '').trim();
}

/**
 * The folders to look in, most likely first. The system is not asked for: every
 * folder the environment can name is tried, and one that is not there is skipped.
 *
 * Folders are joined with "/": Windows takes it in a path, also after one
 * written with "\".
 *
 * @param {FolderEnvironment} env
 * @returns {string[]}
 */
export function extensionFolders(env) {
  const home = homeFolder(env);
  const windowsHome = (env.USERPROFILE || '').trim();
  const roaming = (env.APPDATA || '').trim() || (windowsHome ? `${windowsHome}/AppData/Roaming` : '');
  const config = (env.XDG_CONFIG_HOME || '').trim() || (home ? `${home}/.config` : '');
  const folders = [
    home ? `${home}/Library/Application Support/${EXTENSIONS_FOLDER}` : '',
    roaming ? `${roaming}/${EXTENSIONS_FOLDER}` : '',
    config ? `${config}/${EXTENSIONS_FOLDER}` : '',
  ];
  return [...new Set(folders.filter(Boolean))];
}

/**
 * A folder a person typed, with a leading `~` as the home folder.
 *
 * @param {string} folder
 * @param {string} home
 */
export function expandHome(folder, home) {
  const trimmed = folder.trim();
  return home ? trimmed.replace(/^~(?=[/\\]|$)/, home) : trimmed;
}
