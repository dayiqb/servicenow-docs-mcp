// @ts-check
/**
 * The instances the SDK has credentials for, and the command lines that add,
 * remove and select one.
 *
 * `now-sdk auth --list` prints, per credential (SDK 4.14.0 source,
 * `prettyPrintCredentials`):
 *
 *     *[dev]
 *           host = https://dev12345.service-now.com
 *           type = basic
 *           username = admin
 *           default = Yes
 *
 * The star marks the default. `username` is printed for basic sign-in only.
 * The panel does not keep it: an alias, an address, a sign-in type and a
 * default flag are all it needs.
 *
 * No Node imports.
 */

import { stripAnsi } from './help.js';

/**
 * @typedef {object} Instance
 * @property {string} alias
 * @property {string} host        The address, e.g. "https://dev12345.service-now.com".
 * @property {'basic' | 'oauth' | 'unknown'} signIn
 * @property {boolean} isDefault
 */

const ALIAS_LINE = /^(\*?)\[(.+)\]\s*$/;
const PAIR_LINE = /^\s+(\w+)\s*=\s*(.*?)\s*$/;
const ALIAS = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const INSTANCE_NAME = /^[a-z0-9][a-z0-9-]{0,62}$/;

/**
 * @param {string} text what `auth --list` printed
 * @returns {Instance[]}
 */
export function parseAuthList(text) {
  /** @type {Instance[]} */
  const instances = [];
  /** @type {Instance | undefined} */
  let current;
  for (const line of stripAnsi(text).replaceAll('\r', '').split('\n')) {
    const alias = ALIAS_LINE.exec(line.trim());
    if (alias && !line.includes('=')) {
      current = { alias: alias[2], host: '', signIn: 'unknown', isDefault: alias[1] === '*' };
      instances.push(current);
      continue;
    }
    const pair = PAIR_LINE.exec(line);
    if (!pair || !current) continue;
    const [, key, value] = pair;
    if (key === 'host') current.host = value.replace(/\/+$/, '');
    else if (key === 'type') current.signIn = value === 'basic' || value === 'oauth' ? value : 'unknown';
    else if (key === 'default') current.isDefault = current.isDefault || /^yes$/i.test(value);
    // `username` and anything else is left out on purpose.
  }
  return instances.filter((instance) => instance.host !== '');
}

/**
 * The address the SDK will use for what the person typed: a full https
 * address as it is, a bare instance name as
 * `https://<name>.service-now.com` (the SDK's own rule).
 *
 * @param {string} input
 * @returns {{ host: string } | { error: string }}
 */
export function normalizeHost(input) {
  const value = input.trim();
  if (value === '') return { error: 'Enter an instance name or address.' };
  if (/^https?:\/\//i.test(value)) {
    let url;
    try {
      url = new URL(value);
    } catch {
      return { error: 'The address is not a valid URL.' };
    }
    if (url.protocol !== 'https:') return { error: 'The address must start with https://' };
    if (url.username || url.password) return { error: 'Leave the user name and password out of the address.' };
    return { host: url.origin };
  }
  const name = value.toLowerCase().replace(/\.service-now\.com$/, '');
  if (!INSTANCE_NAME.test(name)) {
    return { error: 'An instance name holds letters, digits and dashes, for example dev12345.' };
  }
  return { host: `https://${name}.service-now.com` };
}

/** @param {string} alias */
export function isValidAlias(alias) {
  return ALIAS.test(alias) && alias !== 'all';
}

/**
 * The command the person runs in their own terminal to sign in. It never
 * carries a user name or a password: the SDK asks for those itself.
 *
 * @param {{ host: string, signIn: 'basic' | 'oauth', alias: string }} request
 * @returns {{ argv: string[] } | { error: string }}
 */
export function addInstanceArgv(request) {
  const host = normalizeHost(request.host);
  if ('error' in host) return host;
  if (request.signIn !== 'basic' && request.signIn !== 'oauth') {
    return { error: 'Choose a sign-in type.' };
  }
  if (!isValidAlias(request.alias)) {
    return { error: 'An alias holds letters, digits, dots, dashes and underscores, and is not "all".' };
  }
  return { argv: ['auth', '--add', host.host, '--type', request.signIn, '--alias', request.alias] };
}

/**
 * @param {string} alias
 * @param {readonly Instance[]} known the instances from the last list
 * @returns {{ argv: string[] } | { error: string }}
 */
export function useInstanceArgv(alias, known) {
  if (!known.some((instance) => instance.alias === alias)) {
    return { error: `No instance has the alias ${alias}.` };
  }
  return { argv: ['auth', '--use', alias] };
}

/**
 * `auth --delete all` resets the whole credential store. The panel removes
 * one alias at a time, so "all" is refused here.
 *
 * @param {string} alias
 * @param {readonly Instance[]} known
 * @returns {{ argv: string[] } | { error: string }}
 */
export function removeInstanceArgv(alias, known) {
  if (alias === 'all') return { error: 'Remove one instance at a time.' };
  if (!known.some((instance) => instance.alias === alias)) {
    return { error: `No instance has the alias ${alias}.` };
  }
  return { argv: ['auth', '--delete', alias] };
}

/**
 * What changed between two lists, for the line the panel shows after the
 * person comes back from the terminal.
 *
 * @param {readonly Instance[]} before
 * @param {readonly Instance[]} after
 */
export function diffInstances(before, after) {
  const was = new Set(before.map((instance) => instance.alias));
  const is = new Set(after.map((instance) => instance.alias));
  return {
    added: after.filter((instance) => !was.has(instance.alias)).map((instance) => instance.alias),
    removed: before.filter((instance) => !is.has(instance.alias)).map((instance) => instance.alias),
    defaultAlias: after.find((instance) => instance.isDefault)?.alias,
  };
}
