// @ts-check
/**
 * Decides what the panel may do with a `now-sdk` command line.
 *
 * Every run goes through `classify`. The answer is the confirmation the
 * command needs, or a refusal with the reason. The rule of thumb: when the
 * panel cannot tell what a command line does, it does not run it.
 *
 * No Node imports.
 */

import { effectsOf, findCommand } from './catalog.js';

/**
 * Flags the panel never passes, whatever the command. Each one either moves a
 * secret through the panel or can make the SDK print one.
 */
export const BLOCKED_FLAGS = Object.freeze({
  '--print': 'It prints a live authentication token.',
  '--password-stdin': 'It moves a password through the panel.',
  '--passwordStdin': 'It moves a password through the panel.',
  '--password': 'It moves a password through the panel.',
  '--username': 'Sign-in happens in your terminal, not in the panel.',
  '--debug': 'Debug output can include request details. Run it in your terminal if you need it.',
  '-d': 'Debug output can include request details. Run it in your terminal if you need it.',
});

/** Flags `explain` takes; anything else on an explain line is refused. */
const EXPLAIN_FLAGS = new Set(['--list', '-l', '--peek', '-p', '--format', '--help', '-h']);

/**
 * @typedef {object} Verdict
 * @property {import('./catalog.js').Confirmation} confirmation
 * @property {import('./catalog.js').EffectId[]} effects
 * @property {string} [commandId]
 * @property {string} [reason]  Why it is blocked or handed to the terminal.
 * @property {string} [note]    A fact the review step must show.
 * @property {string} [namedTarget]
 */

/**
 * @param {readonly string[]} argv arguments after `now-sdk`
 * @returns {Verdict}
 */
export function classify(argv) {
  if (!Array.isArray(argv) || argv.some((arg) => typeof arg !== 'string')) {
    return blocked('The command line is not a list of text arguments.');
  }
  if (argv.some((arg) => /[\0\n\r]/.test(arg))) {
    return blocked('An argument holds a line break or a null character.');
  }
  for (const arg of argv) {
    const flag = arg.split('=')[0];
    if (Object.hasOwn(BLOCKED_FLAGS, flag)) {
      return blocked(`${flag}: ${BLOCKED_FLAGS[/** @type {keyof typeof BLOCKED_FLAGS} */ (flag)]}`);
    }
  }

  // Help never runs the command: yargs prints the usage and exits. Only the
  // plain form counts (`cicd test --help`): beside other flags or after `--`
  // a "--help" could be a value, and the command would run.
  if (argv.includes('--help') || argv.includes('-h')) {
    const isPlain = argv.every((arg) => arg === '--help' || arg === '-h' || /^[a-z][a-z-]*$/.test(arg));
    if (isPlain) return { confirmation: 'none', effects: ['reads-local'], commandId: 'help' };
    return blocked('Help is shown for a command name alone, without other arguments.');
  }

  const entry = findCommand(argv);
  if (!entry) {
    return blocked('The panel does not know this command, so it cannot say what it touches.');
  }

  if (entry.id === 'explain') {
    const unknown = argv.slice(1).find((arg) => arg.startsWith('-') && !EXPLAIN_FLAGS.has(arg.split('=')[0]));
    if (unknown) return blocked(`explain does not take ${unknown.split('=')[0]} in the panel.`);
  }
  if (entry.id === 'auth-list' && argv.length !== 2) {
    return blocked('auth --list takes no other argument.');
  }
  if (entry.id === 'version' && argv.length !== 1) {
    return blocked('--version takes no other argument.');
  }
  if (entry.id === 'auth-delete') {
    const alias = valueOf(argv, '--delete');
    if (!alias) return blocked('auth --delete needs an alias.');
  }

  /** @type {Verdict} */
  const verdict = {
    confirmation: entry.confirmation,
    effects: effectsOf(entry),
    commandId: entry.id,
  };
  if (entry.note) verdict.note = entry.note;
  if (entry.namedTarget) verdict.namedTarget = entry.namedTarget;
  if (entry.confirmation === 'blocked') verdict.reason = entry.note ?? 'The panel never runs this command.';
  if (entry.confirmation === 'terminal') {
    verdict.reason = 'Sign-in asks for a secret in a terminal prompt, so it runs in your terminal.';
  }
  return verdict;
}

/**
 * True for the command lines the panel runs without asking: they read local
 * state only. This is the allowlist the command line and the Claude Code
 * panel use before they start a process.
 *
 * @param {readonly string[]} argv
 */
export function isReadOnly(argv) {
  return classify(argv).confirmation === 'none';
}

/**
 * The value of `--flag value` or `--flag=value`, or undefined.
 *
 * @param {readonly string[]} argv
 * @param {string} flag
 */
export function valueOf(argv, flag) {
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === flag) {
      const next = argv[index + 1];
      return next !== undefined && !next.startsWith('-') ? next : undefined;
    }
    if (arg.startsWith(`${flag}=`)) return arg.slice(flag.length + 1) || undefined;
  }
  return undefined;
}

/**
 * The environment every panel-started `now-sdk` process gets on top of the
 * host's: no color codes in output it parses, and, when the person has
 * turned the SDK's usage telemetry off in the panel's settings,
 * `NO_TELEMETRY=1`. Telemetry is the SDK's own default, so it stays on
 * unless turned off.
 *
 * @param {{ telemetry?: boolean }} [settings]
 * @returns {Record<string, string>}
 */
export function panelEnv(settings = {}) {
  /** @type {Record<string, string>} */
  const env = { NO_COLOR: '1', FORCE_COLOR: '0' };
  if (settings.telemetry === false) env.NO_TELEMETRY = '1';
  return env;
}

/**
 * A command line as text for display and for the clipboard, quoted for a
 * POSIX shell.
 *
 * @param {readonly string[]} argv arguments after `now-sdk`
 */
export function toCommandLine(argv) {
  return ['now-sdk', ...argv].map(quote).join(' ');
}

/** @param {string} arg */
function quote(arg) {
  if (/^[A-Za-z0-9_./:=@%+,-]+$/.test(arg)) return arg;
  return `'${arg.replaceAll("'", "'\\''")}'`;
}

/** @param {string} reason @returns {Verdict} */
function blocked(reason) {
  return { confirmation: 'blocked', effects: [], reason };
}
