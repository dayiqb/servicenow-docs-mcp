// @ts-check
/**
 * The now-sdk commands the panel knows, each with what it touches.
 *
 * This file is the single place that says whether a command only reads,
 * changes local files, contacts an instance or changes an instance, and which
 * confirmation it therefore needs. It was written from `now-sdk <command>
 * --help` (SDK 4.14.0) and from reading the SDK's own source for `auth`.
 * Options are not listed here: they come from the installed SDK's `--help`
 * at run time (see help.js), so they always match the installed version.
 *
 * No Node imports: the Claude Code panel, the command line and the HTML panel
 * all load this module.
 */

/**
 * @typedef {'nothing' | 'local' | 'instance'} Changes
 * What a command changes: nothing, files or configuration on this computer,
 * or records on a ServiceNow instance.
 */

/**
 * @typedef {'none' | 'review' | 'named' | 'terminal' | 'blocked'} Confirmation
 * - none: runs right away, it only reads local state.
 * - review: the panel shows the exact command and what it touches; one press runs it.
 * - named: as review, and the person types the name of the target first.
 * - terminal: the panel never runs it; it hands the command to the person's terminal.
 * - blocked: the panel never runs it and never offers it.
 */

/**
 * @typedef {object} CommandEntry
 * @property {string} id            Stable id, e.g. "auth-list".
 * @property {string[]} argv        Arguments after `now-sdk` that select the command.
 * @property {string} label         Verb phrase shown on the button, sentence case.
 * @property {string} summary       One line on what it does.
 * @property {'Setup' | 'Instances' | 'Project' | 'Metadata' | 'Installation' | 'Instance data' | 'CI/CD'} group
 * @property {boolean} contactsInstance  True when it sends a request to an instance.
 * @property {Changes} changes
 * @property {Confirmation} confirmation
 * @property {boolean} [needsProject]    True when it needs a folder with now.config.json.
 * @property {string} [namedTarget]      What the person types for a `named` confirmation.
 * @property {string} [note]             A fact the review step must show.
 * @property {boolean} [builtInFirstVersion]  True when the first version runs it.
 */

/** @type {readonly CommandEntry[]} */
export const COMMANDS = Object.freeze([
  {
    id: 'version',
    argv: ['--version'],
    label: 'Show version',
    summary: 'The version of the installed SDK.',
    group: 'Setup',
    contactsInstance: false,
    changes: 'nothing',
    confirmation: 'none',
    builtInFirstVersion: true,
  },
  {
    id: 'explain',
    argv: ['explain'],
    label: 'Read documentation',
    summary: "The SDK's own documentation for a Fluent topic.",
    group: 'Setup',
    contactsInstance: false,
    changes: 'nothing',
    confirmation: 'none',
    builtInFirstVersion: true,
  },
  {
    id: 'auth-list',
    argv: ['auth', '--list'],
    label: 'List instances',
    summary: 'The instances the SDK has credentials for: alias, address, sign-in type and default.',
    group: 'Instances',
    contactsInstance: false,
    changes: 'nothing',
    confirmation: 'none',
    note: 'The SDK opens its encrypted credential store to read the list. On macOS the keychain may ask for access. No password or token is printed.',
    builtInFirstVersion: true,
  },
  {
    id: 'auth-add',
    argv: ['auth', '--add'],
    label: 'Add instance',
    summary: 'Sign in to an instance and store the credentials under an alias.',
    group: 'Instances',
    contactsInstance: true,
    changes: 'local',
    confirmation: 'terminal',
    note: 'The SDK asks for the password or the browser code in a hidden terminal prompt. The panel builds the command and shows the outcome; it never sees the secret.',
  },
  {
    id: 'auth-use',
    argv: ['auth', '--use'],
    label: 'Set default instance',
    summary: 'Make an alias the default for commands that do not name one.',
    group: 'Instances',
    contactsInstance: false,
    changes: 'local',
    confirmation: 'review',
  },
  {
    id: 'auth-delete',
    argv: ['auth', '--delete'],
    label: 'Remove instance',
    summary: 'Delete the stored credentials for an alias from this computer.',
    group: 'Instances',
    contactsInstance: false,
    changes: 'local',
    confirmation: 'named',
    namedTarget: 'alias',
    note: 'The instance itself is not changed. To use it again you sign in again.',
  },
  {
    id: 'auth-print',
    argv: ['auth', '--print'],
    label: 'Print token',
    summary: 'Prints a live authentication token.',
    group: 'Instances',
    contactsInstance: true,
    changes: 'nothing',
    confirmation: 'blocked',
    note: 'A token must never pass through the panel, the chat or a log.',
  },
  {
    id: 'init',
    argv: ['init'],
    label: 'Create application',
    summary: 'Create a new application, apply a template, or convert an existing application.',
    group: 'Project',
    contactsInstance: false,
    changes: 'local',
    confirmation: 'review',
    note: 'With --from and a sys_id it downloads the application from the instance first.',
  },
  {
    id: 'build',
    argv: ['build'],
    label: 'Build',
    summary: 'Compile sources into app files and generate an installable package.',
    group: 'Project',
    contactsInstance: false,
    changes: 'local',
    confirmation: 'review',
    needsProject: true,
  },
  {
    id: 'clean',
    argv: ['clean'],
    label: 'Clean',
    summary: 'Delete the build output directory.',
    group: 'Project',
    contactsInstance: false,
    changes: 'local',
    confirmation: 'review',
    needsProject: true,
  },
  {
    id: 'pack',
    argv: ['pack'],
    label: 'Pack',
    summary: 'Zip the built app into an installable artifact.',
    group: 'Project',
    contactsInstance: false,
    changes: 'local',
    confirmation: 'review',
    needsProject: true,
  },
  {
    id: 'download',
    argv: ['download'],
    label: 'Download metadata',
    summary: 'Download application metadata from the instance into a folder.',
    group: 'Metadata',
    contactsInstance: true,
    changes: 'local',
    confirmation: 'review',
    needsProject: true,
  },
  {
    id: 'dependencies',
    argv: ['dependencies'],
    label: 'Download dependencies',
    summary: 'Download the dependencies in now.config.json and TypeScript type definitions.',
    group: 'Metadata',
    contactsInstance: true,
    changes: 'local',
    confirmation: 'review',
    needsProject: true,
  },
  {
    id: 'transform',
    argv: ['transform'],
    label: 'Transform',
    summary: 'Convert XML records from the instance or a local path into Fluent source code.',
    group: 'Metadata',
    contactsInstance: true,
    changes: 'local',
    confirmation: 'review',
    needsProject: true,
    note: 'With --from and a local path it does not contact the instance.',
  },
  {
    id: 'install',
    argv: ['install'],
    label: 'Install',
    summary: 'Install or update the application on the instance.',
    group: 'Installation',
    contactsInstance: true,
    changes: 'instance',
    confirmation: 'named',
    namedTarget: 'alias',
    needsProject: true,
    note: 'With --reinstall, metadata created on the instance that is not in the local project is lost.',
  },
  {
    id: 'install-info',
    argv: ['install', '--info'],
    label: 'Show last install',
    summary: 'Information from the instance about the most recent install of this app.',
    group: 'Installation',
    contactsInstance: true,
    changes: 'nothing',
    confirmation: 'review',
    needsProject: true,
  },
  {
    id: 'query',
    argv: ['query'],
    label: 'Query',
    summary: 'Read records from a table on the instance.',
    group: 'Instance data',
    contactsInstance: true,
    changes: 'nothing',
    confirmation: 'review',
  },
  {
    id: 'exec',
    argv: ['exec'],
    label: 'Run script',
    summary: 'Execute a script on the instance.',
    group: 'Instance data',
    contactsInstance: true,
    changes: 'instance',
    confirmation: 'named',
    namedTarget: 'alias',
    note: 'A script can change or delete any record its user can. The SDK records it in Script Execution History.',
  },
  {
    id: 'cicd-test',
    argv: ['cicd', 'test'],
    label: 'Run test',
    summary: 'Run a single automated test on the instance.',
    group: 'CI/CD',
    contactsInstance: true,
    changes: 'instance',
    confirmation: 'named',
    namedTarget: 'alias',
  },
  {
    id: 'cicd-testsuite',
    argv: ['cicd', 'testsuite'],
    label: 'Run test suite',
    summary: 'Run an automated test suite on the instance.',
    group: 'CI/CD',
    contactsInstance: true,
    changes: 'instance',
    confirmation: 'named',
    namedTarget: 'alias',
  },
  {
    id: 'cicd-install',
    argv: ['cicd', 'install'],
    label: 'Install from repository',
    summary: 'Install an application from the application repository onto the instance.',
    group: 'CI/CD',
    contactsInstance: true,
    changes: 'instance',
    confirmation: 'named',
    namedTarget: 'alias',
  },
  {
    id: 'cicd-publish',
    argv: ['cicd', 'publish'],
    label: 'Publish to repository',
    summary: 'Publish an application to the application repository.',
    group: 'CI/CD',
    contactsInstance: true,
    changes: 'instance',
    confirmation: 'named',
    namedTarget: 'alias',
  },
  {
    id: 'cicd-rollback',
    argv: ['cicd', 'rollback'],
    label: 'Roll back',
    summary: 'Roll back an installed application to a previous version.',
    group: 'CI/CD',
    contactsInstance: true,
    changes: 'instance',
    confirmation: 'named',
    namedTarget: 'alias',
  },
]);

/**
 * The four effects, in the order the panel lists them. `mark` is one
 * character so the Claude Code panel, which draws text, can show the same
 * sign as the HTML panel: a square is this computer, a circle is the
 * instance; hollow reads, filled changes.
 */
/**
 * The groups of the commands a panel lists, in the order shown. A command is
 * in exactly one, by what it works on: the project's files on this computer,
 * application metadata brought from an instance into the project, the
 * application's installation on an instance, records and scripts on an
 * instance, and the CI/CD pipeline.
 */
export const COMMAND_GROUPS = Object.freeze(['Project', 'Metadata', 'Installation', 'Instance data', 'CI/CD']);

export const EFFECTS = Object.freeze({
  'reads-local': { mark: '□', label: 'Reads local' },
  'changes-local': { mark: '■', label: 'Changes local' },
  'reads-instance': { mark: '○', label: 'Reads instance' },
  'changes-instance': { mark: '●', label: 'Changes instance' },
});

/**
 * @typedef {keyof typeof EFFECTS} EffectId
 */

/**
 * The effects of a command, most serious last. A command that downloads from
 * an instance into the project both reads the instance and changes local
 * files, so it has two.
 *
 * @param {Pick<CommandEntry, 'contactsInstance' | 'changes'>} entry
 * @returns {EffectId[]}
 */
export function effectsOf(entry) {
  if (entry.changes === 'instance') return ['changes-instance'];
  /** @type {EffectId[]} */
  const effects = [];
  if (entry.contactsInstance) effects.push('reads-instance');
  if (entry.changes === 'local') effects.push('changes-local');
  if (effects.length === 0) effects.push('reads-local');
  return effects;
}

/**
 * The entry whose `argv` is the longest prefix-match of the given arguments.
 * Flags of an entry (`--list`, `--info`) may stand anywhere after the
 * sub-command words.
 *
 * @param {readonly string[]} argv arguments after `now-sdk`
 * @returns {CommandEntry | undefined}
 */
export function findCommand(argv) {
  /** @type {CommandEntry | undefined} */
  let best;
  for (const entry of COMMANDS) {
    const words = entry.argv.filter((part) => !part.startsWith('-'));
    const flags = entry.argv.filter((part) => part.startsWith('-'));
    const wordsMatch = words.every((word, index) => argv[index] === word);
    const flagsMatch = flags.every((flag) =>
      argv.some((arg) => arg === flag || arg.startsWith(`${flag}=`)),
    );
    if (!wordsMatch || !flagsMatch) continue;
    if (words.length === 0 && argv[0] !== flags[0]) continue;
    if (!best || entry.argv.length > best.argv.length) best = entry;
  }
  return best;
}

/** @param {string} id */
export function commandById(id) {
  return COMMANDS.find((entry) => entry.id === id);
}
