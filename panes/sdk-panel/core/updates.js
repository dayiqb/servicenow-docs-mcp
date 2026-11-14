// @ts-check
/**
 * Updates: what can be checked against the npm registry, the command that
 * asks it for the newest version, and the command that installs it.
 *
 * Asking the registry sends a package's name and nothing else. Installing
 * changes this computer (the SDK, installed for every project) or the
 * project's own files (the AIUX package).
 */

import { compareVersions } from './setup.js';

/** The package the ServiceNow SDK is published as. */
export const SDK_PACKAGE = '@servicenow/sdk';

/**
 * A package name as npm allows it, so a name read from a file cannot carry an
 * option or a path.
 *
 * @param {unknown} name
 */
export function isPackageName(name) {
  return typeof name === 'string' && /^(@[a-z0-9][a-z0-9._-]*\/)?[a-z0-9][a-z0-9._-]*$/.test(name);
}

/**
 * The command that prints the newest published version of a package.
 *
 * @param {string} name
 * @returns {{ program: string, argv: string[] }}
 */
export function latestCommand(name) {
  if (!isPackageName(name)) throw new Error(`"${name}" is not a package name.`);
  return { program: 'npm', argv: ['view', name, 'version'] };
}

/**
 * True when the newest version is later than the one installed.
 *
 * @param {string | undefined} latest
 * @param {string | undefined} installed
 */
export function isUpdateAvailable(latest, installed) {
  const version = /\d+(\.\d+)*/;
  return Boolean(latest && installed && version.test(latest) && version.test(installed) && compareVersions(latest, installed) > 0);
}

/**
 * The command that installs the newest version.
 *
 * @param {{ kind: 'sdk' } | { kind: 'project', name: string, manager: 'npm' | 'pnpm' }} what
 * @returns {{ program: string, argv: string[] }}
 */
export function updateCommand(what) {
  if (what.kind === 'sdk') return { program: 'npm', argv: ['install', '--global', `${SDK_PACKAGE}@latest`] };
  if (!isPackageName(what.name)) throw new Error(`"${what.name}" is not a package name.`);
  return what.manager === 'pnpm'
    ? { program: 'pnpm', argv: ['update', what.name, '--latest'] }
    : { program: 'npm', argv: ['install', `${what.name}@latest`] };
}
