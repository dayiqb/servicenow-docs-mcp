/**
 * The ServiceNow SDK pane in Claude Code.
 *
 * `/sdk-panel` opens a pane with five screens: Setup, Instances, Commands,
 * Explain and AIUX. The pane is drawn with the host's own elements; what a
 * command touches and what may run is decided by the core (../core), the
 * same code the command line and the HTML panel use.
 *
 * Nothing that changes something runs without the host's own question
 * dialog. A command that changes an instance needs the alias typed there.
 * Signing in is never run from here: the pane shows the command to copy.
 */

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import { detectAiux, joinPath } from './core/aiux.js'
import { docsCommand, docsHits, docsQueryForTopic, isDocsVersionOk, versionFromPyproject, docsSection, docsSummary } from './core/docs.js'
import { COMMAND_GROUPS, COMMANDS, EFFECTS, effectsOf } from './core/catalog.js'
import { explainArgv, kindLabel, parseTopicList, searchTopics } from './core/explain.js'
import { composeArgv, formOptions, labelOf, missingRequired, takesInstance } from './core/form.js'
import { classify, panelEnv, toCommandLine } from './core/guard.js'
import { ownOptions, parseHelp } from './core/help.js'
import {
  addInstanceArgv,
  diffInstances,
  parseAuthList,
  removeInstanceArgv,
  useInstanceArgv,
} from './core/instances.js'
import { evaluateSetup } from './core/setup.js'
import { expandHome, extensionFolders, homeFolder } from './core/extensions.js'
import { chooseProject, findProjects } from './core/projects.js'
import { SDK_PACKAGE, isPackageName, isUpdateAvailable, latestCommand, updateCommand } from './core/updates.js'
import type { PanelData, PanelField, PanelHit, PanelProject, PanelScreen, PanelView } from '../../types'

type Engine = EngineInterface

const PANE = 'sdk-panel'
const TITLE = 'ServiceNow SDK'
const READ_TIMEOUT_MS = 30_000
const OUTPUT_LIMIT = 20_000

const SCREENS: readonly (readonly [PanelScreen, string])[] = [
  ['setup', 'Setup'],
  ['instances', 'Instances'],
  ['commands', 'Commands'],
  ['explain', 'Explain'],
  ['aiux', 'AIUX'],
]
/**
 * How wide the desktop app draws each tab's name, in points, and what a
 * button and a menu add around it. Measured from the owner's screenshots and
 * rounded up, so the pane can tell how many tabs fit on one line.
 */
const TAB_TEXT_PT: Record<string, number> = { setup: 42, instances: 74, commands: 87, explain: 56, aiux: 38, more: 38 }
const BUTTON_PAD_PT = 26
const SELECT_PAD_PT = 46
const TAB_GAP_PT = 6
/** 4 pt between tabs, in pane columns: 0.5 column measured about 4.4 pt. */
const TAB_GAP = 0.46
/**
 * Colors given as values, because the theme has no key for them. Each is a
 * mid tone or see-through, so it reads on a light and on a dark pane alike.
 */
/** A mark's slot, in pane columns of about 8 pt: 14 pt, which leaves 4 pt after a 10 pt mark. */
const MARK_SLOT = 1.75
/** From this many pane columns the screens are a rail down the left. */
const RAIL_COLUMNS = 108
/** A rail item's height in pane rows, and how far a plain name is nudged in, in columns. */
const RAIL_ROW = 2
const RAIL_INSET = 0.45
/**
 * A command has one sign. It says where the command goes: a
 * monitor stays on this computer, a cloud contacts an instance. Two commands
 * carry a warning in its place, on the owner's word: Install changes the
 * application on an instance, and Run script runs any script there. The CI/CD
 * commands change an instance too, but the pane only copies them.
 */
type Sign = 'local' | 'instance' | 'warning' | 'danger'
const SIGN_OF_COMMAND: Record<string, Sign> = { install: 'warning', exec: 'danger' }
function signOf(command: { id: string; contactsInstance: boolean }): Sign {
  return SIGN_OF_COMMAND[command.id] ?? (command.contactsInstance ? 'instance' : 'local')
}
const SIGN_WORD: Record<Sign, string> = {
  local: 'Stays on this computer',
  instance: 'Contacts an instance',
  warning: 'Warning: changes an instance',
  danger: 'Danger: runs a script on an instance',
}
/** Where a surface draws no pictures: the core's square and circle for the two places, and a shape of their own for the two warnings. */
const SIGN_CHARACTER: Record<Sign, string> = { local: '\u25A1', instance: '\u25CB', warning: '\u25CF', danger: '\u25CF' }
const SIGN_THEME_COLOR: Record<Sign, string> = { local: 'inactive', instance: 'inactive', warning: 'warning', danger: 'error' }
/**
 * The sign as a drawing: a 16 px mark with nothing around it (a circle
 * around each was tried and took too much room, on the owner's word). The
 * picture is 22 px tall with the mark in the middle, because a name beside
 * it has the middle of its capitals 11 px down (measured in the owner's
 * screenshot of 2026-11-14), so the two sit level. A picture cannot take a
 * theme color and a pane is not told whether the theme is light or dark, so
 * each color is a mid tone with at least 3:1 against both a white and a
 * near-black pane.
 */
// As tall as the capitals of the name beside it (the owner's measure: three
// quarters of the 16 px it was drawn at first). The shapes are drawn on a
// 16 px grid and scaled, with a wider line so it stays 1.5 px.
const SIGN_PX = 13
/** How far down in its picture a sign starts: measured in the owner's screenshot, the capitals of the name run from 3.8 to 14.3 px, and this puts a sign's middle on theirs. */
const SIGN_TOP_PX = 2.5
const SIGN_GRID = 16
const SIGN_ROW_PX = 22
const SIGN_COLOR: Record<Sign, string> = { local: '#7d8590', instance: '#7d8590', warning: '#f0a500', danger: '#e5484d' }
const SIGN_SHAPE: Record<Sign, string> = {
  // A monitor on its stand, a cloud, an exclamation mark in a triangle, and one in a circle.
  local: '<rect x="1.75" y="2.5" width="12.5" height="8.75" rx="1.5"/><path d="M5.5 14h5M8 11.25V14"/>',
  instance: '<path d="M4.6 12.75a3.1 3.1 0 0 1-.45-6.17 4.1 4.1 0 0 1 7.9.92 2.65 2.65 0 0 1-.3 5.25Z"/>',
  // A filled dot, the owner's pick of eight: a triangle with a mark in it runs together at this size.
  warning: '<circle cx="8" cy="8" r="4.5" fill="#f0a500" stroke="none"/>',
  // A filled dot as well, in red: the two warnings are a pair, told apart by color and by the words beside them.
  danger: '<circle cx="8" cy="8" r="4.5" fill="#e5484d" stroke="none"/>',
}
/** A row that opens has a small triangle in its name, pointing right when closed and down when open: a button holds only text, and this way all of it can be pressed. */
/** The yellow of the warning sign, see-through, behind a command's note and around it. */
const NOTE_TINT = 'rgba(240, 165, 0, 0.14)'
const NOTE_FRAME = 'rgba(240, 165, 0, 0.55)'
/** About how many characters of a title the Read section button takes the room of. */
const READ_BUTTON_CHARS = 16
/** How wide the sign of a row that opens is with the spaces after it, in pane columns. */
const HIT_SIGN_COLUMNS = 1.25
/** The thin chevron before a way back (the owner's pick over the heavy one), as a character in the button's name, so all of it can be pressed. */
const BACK_SIGN = '\u2039'
// The medium pair, chosen by the owner from nine drawn in the probe: a button
// draws its name at one size, so the size of the sign is the size of the character.
const CHEVRON_CLOSED = '\u23F5'
const CHEVRON_OPEN = '\u23F7'
function signPicture(sign: Sign): string {
  const y = SIGN_TOP_PX
  const scale = SIGN_PX / SIGN_GRID
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${SIGN_PX}" height="${SIGN_ROW_PX}" viewBox="0 0 ${SIGN_PX} ${SIGN_ROW_PX}"><g transform="translate(0 ${y}) scale(${scale})" fill="none" stroke="${SIGN_COLOR[sign]}" stroke-width="${1.5 / scale}" stroke-linecap="round" stroke-linejoin="round">${SIGN_SHAPE[sign]}</g></svg>`
}
/** Drawings for the probe: a monitor and a cloud, as a picture would show this computer and an instance. */
const PROBE_MONITOR =
  '<rect x="3" y="4" width="18" height="12" rx="2" fill="none" stroke="#8e96a1" stroke-width="2"/><path d="M8 20h8M12 16v4" fill="none" stroke="#8e96a1" stroke-width="2" stroke-linecap="round"/>'
const PROBE_CLOUD =
  '<path d="M7 18a4 4 0 0 1-.6-7.96A6 6 0 0 1 18 11a3.5 3.5 0 0 1 0 7z" fill="none" stroke="#8e96a1" stroke-width="2" stroke-linejoin="round"/>'
/** About how wide one character of a button's label is, in points. */
const NAME_CHAR_PT = 8
/** A pane column is about 8 pt on a desktop (114 columns in a pane about 930 pt wide). */
const COLUMN_PT = 8
const GROUPS: readonly string[] = COMMAND_GROUPS
const SIGN_IN: Record<string, string> = { oauth: 'OAuth', basic: 'Basic', unknown: 'Unknown' }
const STATUS_SIGN: Record<string, string> = { ok: '✓', attention: '!', problem: '✕', unknown: '–', missing: '–' }
const STATUS_COLOR: Record<string, string> = {
  ok: 'success',
  attention: 'warning',
  problem: 'error',
  unknown: 'inactive',
  missing: 'inactive',
}
const SCRIPT_LABELS: Record<string, string> = {
  dev: 'Start dev server',
  build: 'Build',
  deploy: 'Deploy',
  'deploy:full': 'Build and deploy',
}

// Change a tag when the fields of its value change: it declines what an
// earlier version stored, which outlives a reload.
const view = atom(
  { plugin: 'servicenow-docs', key: 'view' } as const,
  {
    screen: 'setup',
    commandId: '',
    topicName: '',
    topicQuery: '',
    topicKind: '',
    topicPage: 0,
    isShowingAllOutput: false,
    commandQuery: '',
    effects: [],
    alias: '',
    values: {},
    isShowingMore: false,
    isAdding: false,
    add: { host: '', alias: '', signIn: 'oauth' },
  } as PanelView,
  { shape: 'view-3' },
)
const data = atom(
  { plugin: 'servicenow-docs', key: 'data' } as const,
  {
    isLoading: false,
    cwd: '',
    nodeVersion: null,
    sdkVersion: null,
    sdkError: null,
    telemetry: true,
    topics: [],
    topicText: {},
    instances: null,
    instancesError: null,
    helps: {},
    aiux: null,
    run: null,
    docs: null,
    docsFolder: '',
    docsHits: {},
  } as PanelData,
  { shape: 'data-2' },
)

/** The commands the Commands screen lists. */
const LISTED = COMMANDS.filter(entry => GROUPS.includes(entry.group))

function firstLine(text: string): string {
  return (
    text
      .split('\n')
      .map(line => line.trim())
      .find(Boolean) ?? ''
  )
}

/** Runs now-sdk only for a command line the core calls read-only. */
async function sdkRead($: Engine, argv: string[]): Promise<{ ok: true; stdout: string } | { ok: false; error: string }> {
  if (classify(argv).confirmation !== 'none') return { ok: false, error: 'This command needs a confirmation.' }
  const { telemetry } = await read($, data)
  try {
    const done = await $.process.run(['now-sdk', ...argv], { env: panelEnv({ telemetry }), timeoutMs: READ_TIMEOUT_MS })
    if (done.exitCode === 0) return { ok: true, stdout: done.stdout }
    return { ok: false, error: firstLine(done.stderr) || firstLine(done.stdout) || `now-sdk ended with code ${done.exitCode}.` }
  } catch {
    return { ok: false, error: 'now-sdk did not start. It must be on the PATH that Claude Code runs with.' }
  }
}

/** The pane's own version; a test holds it to package.json. */
const PANEL_VERSION = '1.0.0'
/** The tools whose versions Setup lists beside the ones it checks, by the name shown. */
const VERSION_TOOLS: readonly (readonly [string, string])[] = [
  ['npm', 'npm'],
  ['pnpm', 'pnpm'],
  ['uv', 'uv'],
  ['Git', 'git'],
]

/** Each tool's version as it prints it, or '' when it is not on the PATH. Reads only; nothing leaves this computer. */
async function toolVersions($: Engine): Promise<Record<string, string>> {
  const read = async ([name, program]: readonly [string, string]): Promise<[string, string]> => {
    try {
      const done = await $.process.run([program, '--version'], { timeoutMs: 10_000 })
      return [name, done.exitCode === 0 ? (/\d+\.\d+(\.\d+)?[^\s)]*/.exec(done.stdout)?.[0] ?? '') : '']
    } catch {
      return [name, '']
    }
  }
  return Object.fromEntries(await Promise.all(VERSION_TOOLS.map(read)))
}

async function nodeVersion($: Engine): Promise<string | null> {
  try {
    const done = await $.process.run(['node', '--version'], { timeoutMs: 10_000 })
    return done.exitCode === 0 ? done.stdout.trim() : null
  } catch {
    return null
  }
}

function projectFiles($: Engine) {
  return {
    async readText(path: string) {
      try {
        return await $.fs.read(path)
      } catch {
        return null
      }
    },
    async listDirectory(path: string) {
      try {
        return (await $.fs.list(path)).map(entry => ({ name: entry.name, isDirectory: entry.kind === 'dir' }))
      } catch {
        return null
      }
    },
  }
}

/**
 * Finds the ServiceNow Docs extension: the folder the person gave, then
 * `snow-docs-mcp` on the PATH, then the Claude Desktop extension whose
 * manifest is named "servicenow-docs". A version below 0.1.7 has no command
 * line, so it is reported as old and never run.
 */
async function findDocs($: Engine, optionFolder: string): Promise<NonNullable<PanelData['docs']>> {
  // Read from the environment, not with a command: `printenv` is not on Windows.
  const env = {
    HOME: await $.env.get('HOME'),
    USERPROFILE: await $.env.get('USERPROFILE'),
    APPDATA: await $.env.get('APPDATA'),
    XDG_CONFIG_HOME: await $.env.get('XDG_CONFIG_HOME'),
  }
  // Without a home folder only an absolute option folder and the PATH are tried.
  const home = homeFolder(env)
  let old: NonNullable<PanelData['docs']> = { kind: 'none' }
  const check = async (folder: string) => {
    let version: string | undefined
    try {
      version = versionFromPyproject(await $.fs.read(`${folder}/pyproject.toml`))
    } catch {
      return undefined
    }
    if (isDocsVersionOk(version)) return { kind: 'folder', folder, version }
    if (version && old.kind === 'none') old = { kind: 'old', version, folder }
    return undefined
  }

  const option = expandHome(optionFolder, home)
  if (option) {
    const found = await check(option)
    if (found) return found
  }
  // `which` finds a program on macOS and Linux, `where` on Windows.
  for (const finder of ['which', 'where']) {
    try {
      if ((await $.process.run([finder, 'snow-docs-mcp'], { timeoutMs: 5000 })).exitCode === 0) return { kind: 'path' }
    } catch {
      // This system has no such command, or the program is not on the PATH.
    }
  }
  // The "Claude Extensions" folder of Claude Desktop, wherever this system keeps it.
  for (const extensions of extensionFolders(env)) {
    try {
      for (const entry of await $.fs.list(extensions)) {
        if (entry.kind !== 'dir') continue
        const folder = `${extensions}/${entry.name}`
        try {
          if (JSON.parse(await $.fs.read(`${folder}/manifest.json`)).name !== 'servicenow-docs') continue
        } catch {
          continue
        }
        const found = await check(folder)
        if (found) return found
      }
    } catch {
      // Not this system's folder, Claude Desktop is not installed, or it has no extensions.
    }
  }
  return old
}

/** Searches the platform documentation for a topic and keeps the passages. */
async function lookUpDocs($: Engine, topicName: string): Promise<void> {
  const { docs, topics } = await read($, data)
  const topic = topics.find(one => one.name === topicName)
  if (!topic || !docs || (docs.kind !== 'folder' && docs.kind !== 'path')) return
  const keep = (value: PanelHit[] | string) => update($, data, one => ({ ...one, docsHits: { ...one.docsHits, [topicName]: value } }))
  await keep('Searching the documentation…')
  try {
    const command = docsCommand(docs as never, 'search', [docsQueryForTopic(topic), '--limit', '3'])
    const done = await $.process.run([command.program, ...command.argv], { timeoutMs: 60_000 })
    await keep(docsHits(JSON.parse(done.stdout)))
  } catch {
    await keep('The lookup did not finish. It needs uv on the PATH that Claude Code runs with.')
  }
}

/** How much of a section is read into the pane; the rest is on the documentation's own page. */
const SECTION_CHARS = 6000

/** Reads one passage's whole section from the platform documentation. */
async function readDocs($: Engine, id: string): Promise<void> {
  const { docs } = await read($, data)
  if (!docs || (docs.kind !== 'folder' && docs.kind !== 'path')) return
  const keep = (value: string) => update($, data, one => ({ ...one, docsText: { ...one.docsText, [id]: value } }))
  await keep('')
  try {
    const command = docsCommand(docs as never, 'read', [id, '--max-chars', String(SECTION_CHARS)])
    const done = await $.process.run([command.program, ...command.argv], { timeoutMs: 60_000 })
    const result = JSON.parse(done.stdout) as { ok?: boolean; content?: string; truncated?: boolean; message?: string }
    if (!result.ok || !result.content) throw new Error(result.message)
    await keep(result.truncated ? `${result.content}\n\n*The section goes on; this is its first ${SECTION_CHARS} characters.*` : result.content)
  } catch {
    await keep('*The section could not be read.*')
  }
}

/**
 * Asks the npm registry for the newest version of the SDK and of the
 * project's AIUX package. Only on the person's press: it is the one thing
 * on Setup that leaves this computer, and it sends package names alone.
 */
async function checkUpdates($: Engine): Promise<void> {
  const { aiux } = await read($, data)
  const wanted: [string, string][] = [['ServiceNow SDK', SDK_PACKAGE]]
  if (aiux?.frameworkName && isPackageName(aiux.frameworkName)) wanted.push(['AIUX', aiux.frameworkName])
  await update($, data, value => ({ ...value, isCheckingUpdates: true }))
  const found = await Promise.all(
    wanted.map(async ([name, packageName]): Promise<[string, string]> => {
      try {
        const command = latestCommand(packageName)
        const done = await $.process.run([command.program, ...command.argv], { timeoutMs: 30_000 })
        const version = done.stdout.trim()
        return [name, done.exitCode === 0 && /^\d+(\.\d+)*/.test(version) ? version : 'Could not be checked']
      } catch {
        return [name, 'Could not be checked']
      }
    }),
  )
  await update($, data, value => ({ ...value, isCheckingUpdates: false, latest: Object.fromEntries(found) }))
}

/** Keeps the project picked for the session's folder and reads the panel again for it. */
async function pickProject($: Engine, folder: string): Promise<void> {
  const { workspace } = await read($, data)
  if (!workspace) return
  const picks = ((await $.store.get('projectPicks')) ?? {}) as Record<string, string>
  await $.store.set('projectPicks', { ...picks, [workspace]: folder })
  await load($)
}

/** Reads everything the pane shows: versions, topics, instances, the project folder. */
async function load($: Engine): Promise<void> {
  // The session's folder may be a workspace with several projects in it: the
  // panel works in the only one, or the one picked for this folder before.
  const workspace = await $.session.cwd()
  const projects = await findProjects(projectFiles($), workspace)
  const picks = ((await $.store.get('projectPicks')) ?? {}) as Record<string, string>
  const choice = chooseProject(projects, picks[workspace] ?? '')
  const cwd = 'project' in choice ? choice.project.folder : workspace
  await update($, data, value => ({ ...value, isLoading: true, cwd, workspace, projects, projectChoice: choice.kind }))

  const [version, node, versions] = await Promise.all([sdkRead($, ['--version']), nodeVersion($), toolVersions($)])
  const listed = version.ok ? await sdkRead($, ['explain', '--list', '--format', 'raw']) : undefined
  const auth = version.ok ? await sdkRead($, ['auth', '--list']) : undefined
  const instances = auth?.ok ? parseAuthList(auth.stdout) : null
  const project = await detectAiux(projectFiles($), cwd)
  // The project's package manager, by its lock file.
  const manager: 'npm' | 'pnpm' = (await projectFiles($).readText(joinPath(cwd, 'pnpm-lock.yaml'))) !== null ? 'pnpm' : 'npm'
  const docsFolder = String((await $.store.get('docsFolder')) ?? '')
  const docs = await findDocs($, docsFolder)

  await update($, data, value => ({
    ...value,
    isLoading: false,
    nodeVersion: node,
    versions,
    sdkVersion: version.ok ? version.stdout.trim() : null,
    sdkError: version.ok ? null : version.error,
    topics: listed?.ok ? parseTopicList(listed.stdout) : [],
    instances,
    instancesError: auth && !auth.ok ? auth.error : null,
    docs,
    docsFolder,
    aiux: {
      isAiux: project.isAiux,
      name: project.config.name ?? project.config.basename ?? '',
      srcDir: project.srcDir,
      pattern: project.pattern ?? '',
      version: project.version,
      framework: project.framework
        ? `${project.framework.name} ${project.framework.installed ?? project.framework.version}${project.framework.installed ? '' : ' (not installed)'}`
        : '',
      frameworkName: project.framework?.name ?? '',
      frameworkInstalled: project.framework?.installed ?? '',
      manager,
      scope: project.fluent.scope ?? '',
      checks: project.checks,
      pages: project.pages.map(page => page.route),
      widgets: project.widgets.map(widget => widget.name),
      components: project.components,
      scripts: project.scripts.map(script => script.name),
    },
  }))
  await update($, view, value =>
    instances?.some(instance => instance.alias === value.alias)
      ? value
      : { ...value, alias: instances?.find(instance => instance.isDefault)?.alias ?? instances?.[0]?.alias ?? '' },
  )
}

/** The form of a command, from the installed SDK's own --help. */
async function loadHelp($: Engine, commandId: string): Promise<void> {
  const entry = COMMANDS.find(one => one.id === commandId)
  if (!entry || (await read($, data)).helps[commandId]) return
  const words = entry.argv.filter(part => !part.startsWith('-'))
  const helped = await sdkRead($, [...words, '--help'])
  const help = helped.ok ? parseHelp(helped.stdout) : undefined
  await update($, data, value => ({
    ...value,
    helps: {
      ...value.helps,
      [commandId]: {
        parameters: help?.parameters ?? [],
        options: help ? ownOptions(help) : [],
        subcommands: help?.commands.map(one => one.name) ?? [],
      },
    },
  }))
}

async function loadTopic($: Engine, name: string): Promise<void> {
  if ((await read($, data)).topicText[name]) return
  const result = await sdkRead($, explainArgv(name))
  await update($, data, value => ({
    ...value,
    topicText: { ...value.topicText, [name]: result.ok ? result.stdout : `The topic could not be read. ${result.error}` },
  }))
}

/**
 * Asks in the host's own dialog, then runs. Review: one press. Named: the
 * alias is typed under "Other". Nothing runs when the dialog is dismissed.
 */
async function confirmAndRun(
  $: Engine,
  request: { id: string; label: string; program: string; argv: string[]; effects: readonly string[]; confirmation: string; cwd?: string; alias?: string },
): Promise<void> {
  const line = [request.program, ...toCommandLine(request.argv).split(' ').slice(1)].join(' ')
  const alias = request.alias ?? ''
  const { instances, telemetry } = await read($, data)
  const instance = instances?.find(one => one.alias === alias)
  const touchesInstance = request.effects.some(effect => effect.endsWith('-instance'))
  const where = touchesInstance && instance ? ` on ${instance.alias} (${instance.host})` : ''
  const touches = request.effects.map(effect => EFFECTS[effect as keyof typeof EFFECTS].label).join(', ')

  let answer: string
  try {
    if (request.confirmation === 'named') {
      if (!instance) {
        $.ui.toast('Choose an instance first')
        return
      }
      answer = await $.ui.ask(
        `${request.label}${where}? It runs: ${line}. ${touches}. To run it, choose Other and type the alias ${instance.alias}.`,
        { header: 'Confirm', options: ['Cancel', 'Copy command'] },
      )
      if (answer.trim() === instance.alias) answer = 'Run'
    } else {
      answer = await $.ui.ask(`${request.label}${where}? It runs: ${line}. ${touches}.`, {
        header: 'Confirm',
        options: ['Run', 'Copy command', 'Cancel'],
      })
    }
  } catch {
    return
  }
  if (answer === 'Copy command') {
    await $.ui.copy({ text: line })
    $.ui.toast('Command copied')
    return
  }
  if (answer !== 'Run') {
    $.ui.toast('Nothing was run')
    return
  }

  await update($, view, value => ({ ...value, isShowingAllOutput: false }))
  await update($, data, value => ({ ...value, run: { commandId: request.id, line, output: '', exitCode: null, isRunning: true } }))
  // The loop is the child's life, so it runs on after this handler returns.
  void (async () => {
    let output = ''
    let exitCode: number | null = null
    try {
      const child = $.process.spawn({ argv: [request.program, ...request.argv], cwd: request.cwd, env: panelEnv({ telemetry }) })
      for await (const chunk of child) {
        output = (output + chunk.text).slice(-OUTPUT_LIMIT)
        await update($, data, value => (value.run ? { ...value, run: { ...value.run, output } } : value))
      }
      exitCode = (await child.result).code
    } catch (error) {
      output += `\n${request.program} did not start or was stopped. ${error instanceof Error ? error.message : ''}`
    }
    await update($, data, value => (value.run ? { ...value, run: { ...value.run, output, exitCode, isRunning: false } } : value))
    if (request.id.startsWith('auth-') || request.id.startsWith('update-')) {
      await load($)
      if (request.id.startsWith('update-')) await update($, data, value => ({ ...value, latest: undefined }))
    }
  })()
}

/** What the panel sets up when a session starts. The plugin's one `session.start` hook calls it. */
export async function start($: Engine): Promise<void> {
  await $.command.register({ name: 'sdk-panel', description: 'Open the ServiceNow SDK panel', argumentHint: '[probe]' })
}

export const register: Register = on => {
  on('command.run', { command: 'sdk-panel' }, async ($, e) => {
    const opened = await $.ui.open({ id: PANE, title: TITLE })
    // `/sdk-panel probe` shows what this surface draws; anything else opens the panel as it was.
    const isProbe = e.args.trim() === 'probe'
    await update($, view, (value): PanelView => ({ ...value, screen: isProbe ? 'probe' : value.screen === 'probe' ? 'setup' : value.screen }))
    void load($)

    return { text: opened.isPlaced ? 'ServiceNow SDK panel opened.' : `The panel could not be shown: ${opened.reason}` }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    // The element table differs per surface; the pane uses what every
    // surface with a pane has.
    const ui = $.ui.resolve(e) as any
    const { Box, Text, Button, Input, Select, Markdown, Code } = ui
    const v = await read($, view)
    const d = await read($, data)
    const set = (change: (value: PanelView) => PanelView) => () => void update($, view, change)
    const instances = d.instances ?? []
    const defaultInstance = instances.find(instance => instance.isDefault)
    // The instance commands run against: the one chosen, else the default.
    const alias = instances.some(instance => instance.alias === v.alias) ? v.alias : ((defaultInstance ?? instances[0])?.alias ?? '')
    const selected = instances.find(instance => instance.alias === alias)
    const rows = e.viewport?.rows ?? 40
    // List and detail sit side by side when the pane is wide enough, as in
    // the HTML panel; in a narrow pane the detail takes the list's place.
    // Widths are in the pane's own columns (about 8 px each on a desktop).
    const columns = (e.props as { bodyColumns?: number } | undefined)?.bodyColumns ?? 0
    const isWide = columns >= 96
    const isNarrow = columns > 0 && columns < 80
    /** Wide enough for the screens down the left, the list and the detail side by side. */
    const hasRail = columns >= RAIL_COLUMNS

    // ------------------------------------------------------------ building blocks
    const row = (...children: unknown[]) => (
      <Box flexDirection="row" gap="sm" flexWrap="wrap" alignItems="center">
        {children}
      </Box>
    )
    const between = (left: unknown, right: unknown) => (
      <Box flexDirection="row" justifyContent="space-between" alignItems="center" gap="md">
        {left}
        {right}
      </Box>
    )
    const title = (text: string) => (
      <Text size="title" weight="semibold">
        {text}
      </Text>
    )
    const label = (text: string) => (
      <Text size="footnote" dimColor>
        {text}
      </Text>
    )
    const quiet = (text: string) => <Text dimColor>{text}</Text>
    const hint = (text: string) => (
      <Text size="caption" dimColor>
        {text}
      </Text>
    )
    /** A framed group with its name, so the parts of a screen are told apart at a glance. */
    // A search field and its filter on one line, across the section: the
    // field at the start and the filter at the end. Neither can be made
    // wider (a desktop draws a one-line field at a fixed 180 pt and a menu
    // as wide as its text, whatever box they are in; seen in the probe on
    // 2026-11-14), and a field of two lines, which does fill, is twice as
    // tall as the menu beside it. Where both do not fit, the filter goes to
    // a line of its own. No submit label, so no button: the list narrows as
    // you type.
    const finder = (field: unknown, filter: unknown, ...rest: unknown[]) =>
      section(
        null,
        <Box flexDirection="row" alignItems="center" justifyContent="space-between" gap="sm" flexWrap="wrap">
          {field}
          {filter}
        </Box>,
        ...rest,
      )
    const section = (name: string | null, ...children: unknown[]) => (
      <Box flexDirection="column" gap="sm" padding="md" borderStyle="round" borderDimColor>
        {name ? label(name) : null}
        {children}
      </Box>
    )
    /** The one bordered surface of a screen: the thing you act on. */
    const surface = (...children: unknown[]) => (
      <Box flexDirection="column" gap="md" padding="md" borderStyle="round" flexGrow={1}>
        {children}
      </Box>
    )
    /**
     * A field. Where there is room it is a key and its value: the name on
     * the left, the control and its description on the right. In a narrow
     * pane a name beside a field wraps and the two stop lining up, so there
     * the name sits above the field and both run the full width.
     */
    const pair = (name: string, isRequired: boolean, control: unknown, description?: string) => {
      const key = (
        <Text weight="medium">
          {name}
          {isRequired ? <Text dimColor> (required)</Text> : null}
        </Text>
      )
      return isNarrow ? (
        <Box flexDirection="column" gap="xs">
          {key}
          {control}
          {description ? hint(description) : null}
        </Box>
      ) : (
        <Box flexDirection="row" gap="md" alignItems="flex-start">
          <Box width="30%" paddingY="xs">
            {key}
          </Box>
          <Box width="70%" flexDirection="column" gap="xs">
            {control}
            {description ? hint(description) : null}
          </Box>
        </Box>
      )
    }
    /**
     * The command line, as wide as its surface: the program quiet, the
     * command strong, the rest plain. A desktop draws its own Code element
     * only as wide as its text, so this is a Box and Text.
     */
    const commandBox = (id: string, program: string, argv: readonly string[], commandWords: number) => {
      const words = [program, ...argv.map(arg => toCommandLine([arg]).slice('now-sdk '.length))]
      return (
        <Box flexDirection="row" justifyContent="space-between" alignItems="center" gap="md" paddingX="md" paddingY="sm" borderStyle="round" borderDimColor>
          <Text mono>
            {words.map((word, index) =>
              index === 0 ? <Text dimColor>{`${word} `}</Text> : index <= commandWords ? <Text weight="semibold">{`${word} `}</Text> : `${word} `,
            )}
          </Text>
          <Button
            key={`copy-${id}`}
            plain
            label="Copy"
            onPress={async () => {
              await $.ui.copy({ text: words.join(' ') })
              $.ui.toast('Command copied')
            }}
          />
        </Box>
      )
    }
    const split = (list: unknown, detail: unknown) => (
      <Box flexDirection="row" gap="lg" alignItems="flex-start">
        <Box flexDirection="column" gap="sm" width="40%">
          {list}
        </Box>
        <Box flexDirection="column" width="60%" flexGrow={1}>
          {detail}
        </Box>
      </Box>
    )
    // A terminal takes a picture and draws nothing for it, so there the
    // sign is a character.
    const hasPictures = Boolean(ui.Svg) && e.surface !== 'terminal'
    const effectLabel = (effect: string) => EFFECTS[effect as keyof typeof EFFECTS].label
    const signMark = (sign: Sign) =>
      hasPictures ? (
        <ui.Svg alt={SIGN_WORD[sign]} width={SIGN_PX} height={SIGN_ROW_PX} source={signPicture(sign)} />
      ) : (
        <Text color={SIGN_THEME_COLOR[sign]}>{SIGN_CHARACTER[sign]}</Text>
      )
    // A picture in a row gives way when the text beside it is long, and
    // then draws smaller: its box must not shrink, or the signs differ in
    // size from row to row and the names beside them start in different places.
    const signBox = (sign: Sign, key?: string) => (
      <Box key={key} flexShrink={0} {...(hasPictures ? {} : { width: MARK_SLOT })}>
        {signMark(sign)}
      </Box>
    )
    /** An effect's sign is its place: this computer or an instance. */
    const glyph = (effect: string) => signBox(effect.endsWith('-instance') ? 'instance' : 'local')
    /** One mark with its words. */
    const mark = (effect: string) => (
      <Box flexDirection="row" alignItems="center" gap="xs">
        {glyph(effect)}
        <Text dimColor>{effectLabel(effect)}</Text>
      </Box>
    )
    const marksText = (effects: readonly string[]) => (
      <Box flexDirection="row" alignItems="center" gap="md" flexWrap="wrap">
        {effects.map(mark)}
      </Box>
    )
    /**
     * The row of Checks and Versions: a mark that says the state, the name, then
     * a quiet value, so the values of both sections stand in one column.
     */
    const statusRow = (status: string, name: string, value: unknown, action?: unknown, under?: string) => (
      <Box flexDirection="column">
        <Box flexDirection="row" gap="sm" alignItems="flex-start">
          <Text color={STATUS_COLOR[status]}>{STATUS_SIGN[status]}</Text>
          <Box width="40%">
            <Text weight="medium">{name}</Text>
          </Box>
          <Box flexDirection="column" flexGrow={1} flexShrink={1} minWidth={0}>
            {value}
          </Box>
          {action ? <Box flexShrink={0}>{action}</Box> : null}
        </Box>
        {under ? hint(`    ${under}`) : null}
      </Box>
    )
    const checkRow = (check: { status: string; label: string; value?: string; fix?: string; detail?: string }) =>
      statusRow(
        check.status,
        check.label,
        check.value ? quiet(check.value) : null,
        undefined,
        check.fix ?? (check.status !== 'ok' ? check.detail : undefined),
      )
    /** One pane has one scroll, so a long detail ends with a way back up to the list. */
    const toTop = (key: string) => (
      <Button key={key} plain label="Back to top" onPress={() => void $.ui.scroll({ to: 'start', in: PANE })} />
    )
    const OUTPUT_LINES = 24
    const output = (run: NonNullable<PanelData['run']>) => {
      const lines = run.output.replace(/\n+$/, '').split('\n')
      const shown = v.isShowingAllOutput ? lines : lines.slice(-OUTPUT_LINES)
      return (
        <Box flexDirection="column" gap="sm">
          {between(
            <Text weight="medium">{run.isRunning ? 'Running…' : run.exitCode === 0 ? 'Finished' : `Ended with code ${run.exitCode ?? 'unknown'}`}</Text>,
            run.output
              ? row(
                  lines.length > OUTPUT_LINES ? (
                    <Button
                      key="output-all"
                      plain
                      label={v.isShowingAllOutput ? `Show the last ${OUTPUT_LINES} lines` : `Show all ${lines.length} lines`}
                      onPress={set(value => ({ ...value, isShowingAllOutput: !value.isShowingAllOutput }))}
                    />
                  ) : null,
                  <Button
                    key="output-copy"
                    plain
                    label="Copy output"
                    onPress={async () => {
                      await $.ui.copy({ text: run.output })
                      $.ui.toast('Output copied')
                    }}
                  />,
                )
              : null,
          )}
          {run.output ? (
            <Box flexDirection="column" paddingX="md" paddingY="sm" borderStyle="round" borderDimColor>
              <Text mono size="footnote">
                {shown.join('\n')}
              </Text>
            </Box>
          ) : null}
        </Box>
      )
    }

    // The screens, on one line, by name, as one control: a track with a
    // shared background, the tabs as plain names on it, and the screen you
    // are on filled. A desktop draws a button at its own width and it
    // cannot shrink, so there are three states and never a mix that reads
    // as broken: five tabs; three and a More menu; or one picker for all.
    // The width the row of screens has, in points. From the probe at 36 and
    // 52 columns (271 and 433 pt of content): about 10 pt a column, less 95,
    // and less the 22 pt the row's own frame and padding take.
    const available = columns > 0 ? columns * 10 - 95 - 22 : Number.POSITIVE_INFINITY
    const tabsPt = (screens: typeof SCREENS) => screens.reduce((sum, [id]) => sum + (TAB_TEXT_PT[id] ?? 70) + BUTTON_PAD_PT + TAB_GAP_PT, 0)
    // The menu is as wide as the longest name it can show.
    const morePt = (screens: typeof SCREENS) => Math.max(TAB_TEXT_PT.more ?? 36, ...screens.map(([id]) => TAB_TEXT_PT[id] ?? 70)) + SELECT_PAD_PT
    let count = SCREENS.length
    if (tabsPt(SCREENS) > available) {
      // As many tabs as fit beside the menu for the rest, down to one.
      count = 0
      for (let fits = SCREENS.length - 1; fits > 0; fits -= 1) {
        if (tabsPt(SCREENS.slice(0, fits)) + morePt(SCREENS.slice(fits)) <= available) {
          count = fits
          break
        }
      }
    }
    const visible = SCREENS.slice(0, count)
    const overflow = SCREENS.slice(visible.length)
    const isInOverflow = overflow.some(([id]) => id === v.screen)
    const tab = ([id, name]: readonly [PanelScreen, string]) =>
      v.screen === id ? (
        <Button key={`tab-${id}`} label={name} variant="primary" onPress={() => {}} />
      ) : (
        <Button key={`tab-${id}`} label={name} plain onPress={set(value => ({ ...value, screen: id }))} />
      )
    const tabs =
      count === 0 ? (
        <Box flexDirection="row" alignItems="center" gap="sm" paddingX="sm" paddingY="xs" borderStyle="round" borderDimColor>
          <Text dimColor>Tab</Text>
          <Select
            key="screen"
            value={v.screen}
            options={SCREENS.map(([value, name]) => ({ value, label: name }))}
            onSelect={(value: string) => void update($, view, (one): PanelView => ({ ...one, screen: value as PanelScreen }))}
          />
        </Box>
      ) : (
        // No track or frame around the screens: the filled one is the mark.
        // The tabs stand together at the start, 4 pt apart; the menu for
        // the rest stays at the end of the line.
        // With all five showing there is no menu, and the tabs stand in the middle of the line.
        // The row has the frame every section has, and no background.
        <Box flexDirection="row" alignItems="center" justifyContent={overflow.length > 0 ? 'space-between' : 'center'} paddingX="sm" paddingY="xs" borderStyle="round" borderDimColor>
          <Box flexDirection="row" alignItems="center" gap={TAB_GAP}>
            {visible.map(tab)}
          </Box>
          {overflow.length > 0 ? (
            <Select
              key="screens-more"
              value={isInOverflow ? v.screen : 'more'}
              options={[...(isInOverflow ? [] : [{ value: 'more', label: 'More' }]), ...overflow.map(([value, name]) => ({ value, label: name }))]}
              onSelect={(value: string) => {
                if (value !== 'more') void update($, view, (one): PanelView => ({ ...one, screen: value as PanelScreen }))
              }}
            />
          ) : null}
        </Box>
      )
    // In a wide pane the screens are a rail down the left: the names
    // stacked, so nothing can run out of room, and the screen has
    // the rest of the width for its list and its detail. A filled button is
    // taller than a plain one and insets its name further, so each item
    // sits in a row of one height and a plain name is nudged in to line up
    // with the filled one.
    const rail = (
      <Box flexDirection="column" paddingX="sm" paddingY="xs" borderStyle="round" borderDimColor>
        {SCREENS.map(screen => (
          <Box flexDirection="row" alignItems="center" minHeight={RAIL_ROW} {...(v.screen === screen[0] ? {} : { paddingLeft: RAIL_INSET })}>
            {tab(screen)}
          </Box>
        ))}
      </Box>
    )
    /**
     * The top of a screen: its title and its actions. Beside each other
     * where they fit; in a narrow pane the actions go under the title, the
     * main one first, so they never pile up beside it.
     */
    const head = (titleText: string, ...actions: unknown[]) =>
      isNarrow && actions.length > 1 ? (
        <Box flexDirection="column" gap="sm">
          {title(titleText)}
          {row(...[...actions].reverse())}
        </Box>
      ) : (
        between(title(titleText), row(...actions))
      )

    // ---------------------------------------------------------------- setup
    const setupScreen = () => {
      const setup = evaluateSetup({
        nodeVersion: d.nodeVersion,
        sdkVersion: d.sdkVersion,
        topicCount: d.sdkVersion ? d.topics.length : null,
        instances: d.instances as never,
        instancesError: d.instancesError,
        docs: d.docs,
      })
      // Each thing is on the screen once: a check carries its version, and what
      // has a version but no check (the panel, the package managers, Git, AIUX)
      // follows in the same list. `latest` is what Check for updates got from the
      // npm registry; it is asked about the SDK and the AIUX package only.
      const updateOf = (name: 'ServiceNow SDK' | 'AIUX', installed: string) => {
        const latest = d.latest?.[name]
        const canUpdate = isUpdateAvailable(latest, installed)
        const id = name === 'AIUX' ? 'update-aiux' : 'update-sdk'
        return {
          canUpdate,
          // What is out, or why the registry gave no version.
          note: canUpdate ? <Text color="warning">{`${latest} is out`}</Text> : latest !== undefined && !/^\d/.test(latest) ? quiet(latest) : null,
          button: canUpdate ? (
            <Button
              key={id}
              label="Update"
              onPress={() => {
                const command =
                  name === 'AIUX'
                    ? updateCommand({ kind: 'project', name: d.aiux?.frameworkName ?? '', manager: d.aiux?.manager ?? 'npm' })
                    : updateCommand({ kind: 'sdk' })
                void confirmAndRun($, {
                  id,
                  label: `Update ${name} to ${latest}`,
                  program: command.program,
                  argv: command.argv,
                  effects: ['changes-local'],
                  confirmation: 'review',
                  cwd: name === 'AIUX' ? d.cwd : undefined,
                })
              }}
            />
          ) : undefined,
        }
      }
      const sdkUpdate = updateOf('ServiceNow SDK', d.sdkVersion ?? '')
      // A newer SDK turns a passing check into one to look at; it never hides a problem.
      const checks = setup.checks.map(check =>
        check.id === 'sdk' && check.status === 'ok' && sdkUpdate.canUpdate ? { ...check, status: 'attention' as const } : check,
      )
      const tools: [string, string][] = [
        ['Panel', PANEL_VERSION],
        ...VERSION_TOOLS.map(([name]): [string, string] => [name, d.versions?.[name] ?? '']),
      ]
      const aiuxUpdate = d.aiux?.framework ? updateOf('AIUX', d.aiux.frameworkInstalled ?? '') : undefined
      const toFix = checks.filter(check => check.status === 'problem').length
      const toLookAt = checks.filter(check => check.status !== 'ok').length + (aiuxUpdate?.canUpdate ? 1 : 0)
      // The checks say whether the setup is ready, so they need no headline
      // above them: their own title carries the state, with the actions at its end.
      const checksTitle = d.isLoading
        ? 'Reading the SDK setup…'
        : d.isCheckingUpdates
          ? 'Checking for updates…'
          : toFix > 0
            ? `Checks, ${toFix} to fix`
            : toLookAt > 0
              ? `Checks, ${toLookAt} to look at`
              : 'Checks'
      return (
        <Box flexDirection="column" gap="md">
          {section(
            null,
            <Box flexDirection="row" justifyContent="space-between" alignItems="center" gap="sm" flexWrap="wrap">
              {label(checksTitle)}
              <Box flexDirection="row" gap="sm" flexShrink={0}>
                <Button key="check-updates" label="Check for updates" onPress={() => void checkUpdates($)} />
                <Button key="refresh" label="Refresh" onPress={() => void load($)} />
              </Box>
            </Box>,
            d.sdkError ? <Text color="error">{d.sdkError}</Text> : null,
            ...checks.map(check =>
              check.id === 'sdk'
                ? statusRow(
                    check.status,
                    check.label,
                    [check.value ? quiet(check.value) : null, sdkUpdate.note],
                    sdkUpdate.button,
                    check.fix,
                  )
                : checkRow(check),
            ),
            // Found is fine; a tool that is not there is not a fault, so it gets the dash.
            ...tools.map(([name, version]) => statusRow(version ? 'ok' : 'unknown', name, quiet(version || 'Not found'))),
            d.aiux?.framework && aiuxUpdate
              ? statusRow(aiuxUpdate.canUpdate ? 'attention' : 'ok', 'AIUX', [quiet(d.aiux.framework), aiuxUpdate.note], aiuxUpdate.button)
              : null,
            d.run && d.run.commandId.startsWith('update-') ? output(d.run) : null,
          )}
          {section(
            'Project',
            ...projectLines(),
            // The folder in a frame of its own, across the section, as a setting has.
            d.projectChoice === 'pick' ? null : (
              <Box flexDirection="column" paddingX="md" paddingY="sm" borderStyle="round" borderDimColor>
                <Text mono>{d.cwd}</Text>
              </Box>
            ),
          )}
          {section(
            'Settings',
            // Each setting has a frame of its own inside the section, so it is
            // plain where one ends and the next begins.
            <Box flexDirection="column" gap="xs" paddingX="md" paddingY="sm" borderStyle="round" borderDimColor>
              {between(
                <Text weight="medium">{d.telemetry ? 'SDK telemetry is on' : 'SDK telemetry is off'}</Text>,
                <Button key="telemetry" label={d.telemetry ? 'Turn off' : 'Turn on'} onPress={() => void update($, data, value => ({ ...value, telemetry: !value.telemetry }))} />,
              )}
              {hint('The SDK sends usage events to ServiceNow for the commands it runs. This setting covers what the panel starts.')}
            </Box>,
            // A reserve for when the docs extension is not found: shown then,
            // and while a folder is set, so it can be changed or cleared.
            (d.docs && (d.docs.kind === 'folder' || d.docs.kind === 'path')) && !d.docsFolder ? null : (
            <Box flexDirection="column" paddingX="md" paddingY="sm" borderStyle="round" borderDimColor>
            {pair(
              'ServiceNow Docs folder',
              false,
              <Input
                key="docs-folder"
                rows={2}
                submitLabel="Save"
                placeholder="~/projects/servicenow-docs-mcp"
                value={d.docsFolder}
                onInput={(value: string) => void update($, data, one => ({ ...one, docsFolder: value }))}
                onSubmit={async (value: string) => {
                  await $.store.set('docsFolder', value.trim())
                  await load($)
                }}
              />,
              'Optional. A checkout of servicenow-docs-mcp, for when the docs extension is not installed.',
            )}
            </Box>
            ),
          )}
        </Box>
      )
    }

    // ------------------------------------------------------------ instances
    const instancesScreen = () => {
      const built = addInstanceArgv({ host: v.add.host, signIn: v.add.signIn as 'oauth' | 'basic', alias: v.add.alias })
      const removeInstance = async (instance: (typeof instances)[number]) => {
        const remove = removeInstanceArgv(instance.alias, instances as never)
        if (!('argv' in remove)) return
        let typed = ''
        try {
          typed = await $.ui.ask(
            `Remove ${instance.alias} (${instance.host})? It runs: ${toCommandLine(remove.argv)}. Changes local: the stored credentials are deleted; the instance is not changed. To remove it, choose Other and type the alias ${instance.alias}.`,
            { header: 'Confirm', options: ['Cancel', 'Copy command'] },
          )
        } catch {
          return
        }
        if (typed === 'Copy command') {
          await $.ui.copy({ text: toCommandLine(remove.argv) })
          $.ui.toast('Command copied')
          return
        }
        if (typed.trim() !== instance.alias) {
          $.ui.toast('Nothing was removed')
          return
        }
        const { telemetry } = await read($, data)
        try {
          const done = await $.process.run(['now-sdk', ...remove.argv], { env: panelEnv({ telemetry }), timeoutMs: READ_TIMEOUT_MS })
          $.ui.toast(done.exitCode === 0 ? `${instance.alias} removed` : firstLine(done.stderr) || 'The instance could not be removed')
        } catch {
          $.ui.toast('now-sdk did not start')
        }
        await load($)
      }
      const field = (key: 'host' | 'alias', name: string, placeholder: string, description: string) =>
        pair(
          name,
          true,
          <Input
            key={`add-${key}`}
            rows={2}
            placeholder={placeholder}
            value={v.add[key]}
            onInput={(value: string) => void update($, view, one => ({ ...one, add: { ...one.add, [key]: value.trim() } }))}
            onSubmit={(value: string) => void update($, view, one => ({ ...one, add: { ...one.add, [key]: value.trim() } }))}
          />,
          description,
        )
      return (
        <Box flexDirection="column" gap="md">
          {head('Instances', <Button key="add" label="Add instance" variant="primary" onPress={set(value => ({ ...value, isAdding: true }))} />)}
          {d.instancesError ? <Text color="error">{d.instancesError}</Text> : null}
          {instances.length === 0 && !d.instancesError ? quiet('No instances yet. Add one to run commands against it.') : null}
          {instances.map(instance =>
            section(
              null,
              (() => {
                const actions = row(
                    <Button
                      key={`use-${instance.alias}`}
                      label="Set as default"
                      onPress={() => {
                        const use = useInstanceArgv(instance.alias, instances as never)
                        if ('argv' in use) {
                          void confirmAndRun($, {
                            id: 'auth-use',
                            label: `Set ${instance.alias} as default`,
                            program: 'now-sdk',
                            argv: use.argv,
                            effects: ['changes-local'],
                            confirmation: 'review',
                            alias,
                          })
                        }
                      }}
                    />,
                    <Button key={`remove-${instance.alias}`} label="Remove" onPress={() => void removeInstance(instance)} />,
                )
                return isNarrow ? (
                  <Box flexDirection="column" gap="xs">
                    {between(
                      <Text mono weight="semibold">
                        {instance.alias}
                      </Text>,
                      row(quiet(SIGN_IN[instance.signIn] ?? instance.signIn), instance.isDefault ? <Text weight="medium">Default</Text> : null),
                    )}
                    <Text mono dimColor size="footnote" wrap="truncate-middle">
                      {instance.host}
                    </Text>
                    {instance.isDefault ? null : actions}
                  </Box>
                ) : (
                  <Box flexDirection="row" gap="md" alignItems="center">
                    <Box flexDirection="column" width="50%">
                      <Text mono weight="semibold">
                        {instance.alias}
                      </Text>
                      <Text mono dimColor size="footnote" wrap="truncate-middle">
                        {instance.host}
                      </Text>
                    </Box>
                    <Box width="12%">{quiet(SIGN_IN[instance.signIn] ?? instance.signIn)}</Box>
                    <Box width="38%" flexDirection="row" justifyContent="flex-end" gap="sm">
                      {instance.isDefault ? <Text weight="medium">Default</Text> : actions}
                    </Box>
                  </Box>
                )
              })(),
            ),
          )}
          {v.isAdding
            ? surface(
                <Text size="heading" weight="semibold">
                  Add instance
                </Text>,
                field('host', 'Instance', 'dev12345', 'A name such as dev12345, or a full https address.'),
                field('alias', 'Alias', 'dev', 'The short name you choose for this instance.'),
                pair(
                  'Sign-in',
                  true,
                  <Select
                    key="add-sign-in"
                    value={v.add.signIn}
                    options={[
                      { value: 'oauth', label: 'OAuth' },
                      { value: 'basic', label: 'Basic' },
                    ]}
                    onSelect={(value: string) => void update($, view, one => ({ ...one, add: { ...one.add, signIn: value } }))}
                  />,
                ),
                quiet('Run this in your terminal. The SDK asks you to sign in there, so your password never passes through this panel.'),
                'argv' in built ? commandBox('add', 'now-sdk', built.argv, 1) : (v.add.host || v.add.alias) ? <Text color="error">{built.error}</Text> : null,
                between(
                  row(
                    <Button
                      key="add-check"
                      label="Check for the instance"
                      variant="primary"
                      onPress={async () => {
                        const before = (await read($, data)).instances ?? []
                        await load($)
                        const change = diffInstances(before as never, ((await read($, data)).instances ?? []) as never)
                        $.ui.toast(
                          change.added.length > 0
                            ? `${change.added.join(', ')} was added${change.defaultAlias && change.added.includes(change.defaultAlias) ? ' and is the default' : ''}`
                            : 'No new instance yet',
                        )
                      }}
                    />,
                    <Button key="add-close" label="Cancel" onPress={set(value => ({ ...value, isAdding: false }))} />,
                  ),
                  marksText(['reads-instance', 'changes-local']),
                ),
              )
            : null}
          {hint("Passwords and tokens stay in the SDK's encrypted store. This panel never sees them.")}
        </Box>
      )
    }

    // ------------------------------------------------------------- commands
    const field = (commandId: string, key: string, spec: PanelField) => {
      const values = v.values[commandId] ?? {}
      const write = (value: string) =>
        void update($, view, one => ({ ...one, values: { ...one.values, [commandId]: { ...(one.values[commandId] ?? {}), [key]: value } } }))
      let control
      if (spec.type === 'boolean' || spec.choices) {
        const options =
          spec.type === 'boolean'
            ? [
                { value: 'true', label: 'Yes' },
                { value: 'false', label: 'No' },
              ]
            : (spec.choices ?? []).map(choice => ({ value: choice }))
        control = <Select key={`f-${commandId}-${key}`} value={values[key] ?? spec.defaultValue ?? options[0]?.value} options={options} onSelect={write} />
      } else {
        const isPath = spec.defaultValue?.startsWith('/')
        // A desktop draws a field of two lines or more as wide as its box,
        // with its button beside it, and a one-line field at a fixed, narrow
        // width. Filling the width matters more here than matching the
        // button's height, so every field is two lines; a script gets four.
        control = (
          <Input
            key={`f-${commandId}-${key}`}
            rows={spec.name === 'script' ? 4 : 2}
            placeholder={isPath ? 'Current folder' : spec.defaultValue}
            value={values[key] ?? ''}
            onInput={write}
            onSubmit={write}
          />
        )
      }
      return pair(labelOf(spec.name), spec.isRequired, control, spec.description)
    }

    // ------------------------------------------------------------ project
    const projects = d.projects ?? []
    const projectName = (one: PanelProject) => `${one.path || one.folder}${one.isAiux ? '  AIUX' : ''}`
    /** The projects of the session's folder, when there is more than one to choose from. */
    const projectPicker = () =>
      projects.length > 1 ? (
        <Box flexShrink={0}>
          <Select
            key="project"
            value={d.projectChoice === 'pick' ? 'pick' : d.cwd}
            options={[
              ...(d.projectChoice === 'pick' ? [{ value: 'pick', label: 'Pick a project' }] : []),
              ...projects.map(one => ({ value: one.folder, label: projectName(one) })),
            ]}
            onSelect={(value: string) => {
              if (value !== 'pick') void pickProject($, value)
            }}
          />
        </Box>
      ) : null
    /** What Setup says about the folder: where the project was found, or that one is to be picked. */
    const projectLines = () => {
      if (d.projectChoice === 'pick') return [quiet(`${d.workspace} holds ${projects.length} projects. Pick the one to work in.`), projectPicker()]
      if (projects.length > 1) return [projectPicker()]
      const only = projects[0]
      if (only?.isAbove) return [hint(`The session works in ${d.workspace}, inside this project`)]
      if (only && only.path) return [hint(`Found in ${d.workspace}`)]
      return []
    }

    const commandDetail = (entry: (typeof LISTED)[number]) => {
      const help = d.helps[entry.id]
      const command = { ...entry, help: help ?? { parameters: [], options: [] } }
      const values = v.values[entry.id] ?? {}
      const argv = composeArgv(command, values, alias)
      const effects = effectsOf(entry)
      const options = formOptions(command) as PanelField[]
      const required = options.filter(option => option.isRequired)
      const optional = options.filter(option => !option.isRequired)
      const run = d.run?.commandId === entry.id ? d.run : null
      const review = () => {
        const missing = missingRequired(command, values)
        if (missing) {
          $.ui.toast(`${labelOf(missing)} is required`)
          return
        }
        if (entry.group === 'CI/CD') {
          $.ui.toast('CI/CD commands are not run from the panel yet. Copy the command instead.')
          return
        }
        const verdict = classify(argv)
        if (verdict.confirmation === 'blocked' || verdict.confirmation === 'terminal') {
          $.ui.toast(verdict.reason ?? 'The panel does not run this command.')
          return
        }
        if (entry.needsProject && d.projectChoice === 'pick') {
          $.ui.toast('Pick the project to run it in')
          return
        }
        void confirmAndRun($, { id: entry.id, label: entry.label, program: 'now-sdk', argv, effects, confirmation: verdict.confirmation, cwd: d.cwd || undefined, alias })
      }
      return surface(
        between(title(entry.label), marksText(effects)),
        quiet(entry.summary),
        // What to know before running it, in a box of its own with the yellow
        // of the warning sign: a tint behind and a frame, the words in the
        // pane's own text color so they read on a light and a dark pane.
        entry.note ? (
          <Box key="note" flexDirection="column" paddingX="md" paddingY="sm" borderStyle="round" borderColor={NOTE_FRAME} backgroundColor={NOTE_TINT}>
            <Text>{entry.note}</Text>
          </Box>
        ) : null,
        // The command line: what will run, as it will run.
        commandBox(entry.id, 'now-sdk', argv, entry.argv.filter(part => !part.startsWith('-')).length),
        row(
          <Button key="run" label="Review and run" variant="primary" onPress={review} />,
          entry.contactsInstance && selected ? quiet(`on ${selected.alias} (${selected.host.replace('https://', '')})`) : null,
        ),
        // A command that works on a project says which one, and asks when the folder holds several.
        entry.needsProject && projects.length > 1
          ? row(d.projectChoice === 'pick' ? quiet('In project') : quiet('In'), projectPicker())
          : entry.needsProject && projects[0]?.path
            ? quiet(`In ${projects[0].path}`)
            : null,
        !help ? quiet('Reading the options…') : null,
        help && help.subcommands.length > 0 ? quiet(`It has its own commands: ${help.subcommands.map(name => name.split(' ').pop()).join(', ')}.`) : null,
        ...(help?.parameters ?? []).map(parameter => field(entry.id, `param:${parameter.name}`, parameter)),
        ...required.map(option => field(entry.id, `opt:${option.name}`, option)),
        optional.length > 0 ? (
          <Button
            key="more"
            plain
            label={v.isShowingMore ? 'Fewer options' : `More options (${optional.length})`}
            onPress={set(value => ({ ...value, isShowingMore: !value.isShowingMore }))}
          />
        ) : null,
        ...(v.isShowingMore ? optional.map(option => field(entry.id, `opt:${option.name}`, option)) : []),
        run ? output(run) : null,
        run && isWide ? toTop('command-top') : null,
      )
    }

    const commandsScreen = () => {
      const words = v.commandQuery.toLowerCase().split(/\s+/).filter(Boolean)
      const shown = LISTED.filter(one => {
        const text = `${one.label} ${one.summary} ${one.argv.join(' ')}`.toLowerCase()
        const hasEffect = v.effects.length === 0 || effectsOf(one).some(effect => v.effects.includes(effect))
        return hasEffect && words.every(word => text.includes(word))
      })
      const entry = LISTED.find(one => one.id === v.commandId)
      const toolbar = finder(
          <Input
            key="command-search"
            placeholder="Search commands"
            value={v.commandQuery}
            onInput={(value: string) => void update($, view, one => ({ ...one, commandQuery: value }))}
            onSubmit={(value: string) => void update($, view, one => ({ ...one, commandQuery: value }))}
          />,
          <Select
            key="effect-filter"
            value={v.effects[0] ?? 'all'}
            options={[
              { value: 'all', label: 'All commands' },
              ...(['changes-local', 'reads-instance', 'changes-instance'] as const).map(effect => ({ value: effect, label: EFFECTS[effect].label })),
            ]}
            onSelect={(value: string) => void update($, view, one => ({ ...one, effects: value === 'all' ? [] : [value] }))}
          />,
      )
      // What the commands run against, at the top and across the pane: it
      // decides where every command on this screen lands.
      // About how much room a framed section has inside it, in points.
      const innerPt = columns > 0 ? columns * COLUMN_PT - 68 : Number.POSITIVE_INFINITY
      const host = selected ? selected.host.replace('https://', '') : 'None chosen'
      // A menu squeezed by long text beside it draws as an empty box, so its
      // box never shrinks. Built only where it is drawn: a menu with no
      // options is refused.
      const picker = () => (
        <Box flexShrink={0}>
          <Select
            key="instance"
            value={alias}
            options={instances.map(instance => ({ value: instance.alias, label: instance.alias }))}
            onSelect={(value: string) => void update($, view, one => ({ ...one, alias: value }))}
          />
        </Box>
      )
      const pickerPt = Math.max(0, ...instances.map(instance => instance.alias.length)) * NAME_CHAR_PT + SELECT_PAD_PT
      // The address beside the menu where both fit; under it where they do not.
      const isBarStacked = host.length * NAME_CHAR_PT + 12 + pickerPt > innerPt
      const instanceBar =
        instances.length === 0 ? null : isBarStacked ? (
          <Box flexDirection="column" gap="xs" paddingX="md" paddingY="sm" borderStyle="round" borderDimColor>
            <Box flexDirection="row" alignItems="center" justifyContent="space-between" gap="md">
              <Text dimColor size="footnote">
                Instance
              </Text>
              {picker()}
            </Box>
            <Text mono size="footnote" wrap="truncate-middle">
              {host}
            </Text>
          </Box>
        ) : (
          <Box flexDirection="row" alignItems="center" justifyContent="space-between" gap="md" paddingX="md" paddingY="sm" borderStyle="round" borderDimColor>
            <Box flexDirection="column" flexShrink={1} minWidth={0}>
              <Text dimColor size="footnote">
                Instance
              </Text>
              <Text mono size="footnote" wrap="truncate-middle">
                {host}
              </Text>
            </Box>
            {picker()}
          </Box>
        )
      // A command's words (build, cicd install) sit at the end of its row,
      // and only where the longest name and its words fit side by side:
      // otherwise they run past the frame. The detail shows the whole line.
      const rowPt = Math.max(0, ...LISTED.map(one => (one.label.length + one.argv.join(' ').length) * NAME_CHAR_PT)) + 42
      const hasWords = !isWide && rowPt <= innerPt
      // How wide the column of words is, in pane columns: the longest, at about 0.9 column a character.
      const wordsColumns = Math.ceil(Math.max(0, ...LISTED.map(one => one.argv.join(' ').length)) * 0.9)
      const list = (
        <Box flexDirection="column" gap="sm">
          {shown.length === 0 ? quiet(v.commandQuery ? `No command matches "${v.commandQuery}".` : 'No command has this effect.') : null}
          {GROUPS.filter(group => shown.some(one => one.group === group)).map(group =>
            section(
              group,
              ...shown
                .filter(one => one.group === group)
                .map(one => (
                  <Box flexDirection="row" alignItems="flex-start">
                    {signBox(signOf(one), `sign-${one.id}`)}
                    <Box flexDirection="column" flexGrow={1} flexShrink={1} minWidth={0}>
                      {between(
                        <Button
                          key={`cmd-${one.id}`}
                          label={one.label}
                          {...(one.id === v.commandId && isWide ? {} : { plain: true as const })}
                          onPress={() => {
                            void update($, view, value => ({ ...value, commandId: one.id, isShowingMore: false }))
                            void loadHelp($, one.id)
                          }}
                        />,
                        hasWords ? (
                          // A column of one width for every row, its words at the end.
                          <Box flexDirection="row" justifyContent="flex-end" flexShrink={0} minWidth={wordsColumns}>
                            <Text dimColor mono size="footnote">
                              {one.argv.join(' ')}
                            </Text>
                          </Box>
                        ) : null,
                      )}
                      {/* A plain button's name is inset by about 7 pt; so is what it does.
                          It stops where the column of words begins, so the row is a grid:
                          sign, name and what it does, words. */}
                      <Box paddingLeft="xs" paddingRight={hasWords ? wordsColumns + 1.5 : 'xs'}>
                        <Text dimColor size="footnote">
                          {one.summary}
                        </Text>
                      </Box>
                    </Box>
                  </Box>
                )),
            ),
          )}
        </Box>
      )
      if (isWide) {
        return (
          <Box flexDirection="column" gap="md">
            {instanceBar}
            {split([toolbar, list], entry ? commandDetail(entry) : surface(<Text weight="medium">No command chosen</Text>, quiet('Choose a command in the list to see what it runs and what it touches.')))}
          </Box>
        )
      }
      if (entry) {
        return (
          <Box flexDirection="column" gap="md">
            {instanceBar}
            <Button key="back-commands" plain label={`${BACK_SIGN}  Back to commands`} onPress={set(value => ({ ...value, commandId: '' }))} />
            {commandDetail(entry)}
          </Box>
        )
      }
      return (
        <Box flexDirection="column" gap="md">
          {instanceBar}
          {toolbar}
          {list}
        </Box>
      )
    }

    // -------------------------------------------------------------- explain
    const explainScreen = () => {
      const topic = d.topics.find(one => one.name === v.topicName)
      const found = searchTopics(d.topics as never, v.topicQuery, v.topicKind ? { kind: v.topicKind as 'api' } : {})
      // One pane has one scroll, so the list is kept to what fits: pages, not a long column.
      const shownCount = Math.max(8, Math.min(40, Math.floor((rows - 22) / 1.8)))
      const pages = Math.max(1, Math.ceil(found.length / shownCount))
      const page = Math.min(v.topicPage, pages - 1)
      const first = page * shownCount
      // What a lookup in the platform documentation found for the open topic
      // sits under the topic's buttons, above its text, at every width. A
      // column of its own beside the topic was tried: the topic became
      // narrow and long, and four columns were too many.
      const hits = topic ? d.docsHits[topic.name] : undefined
      // A passage is a closed row: its page, and its section under it. Open,
      // it shows a line or two of what it says and can be read whole. One is
      // open at a time, so the list stays short.
      // The room a title has, in points: the pane's content (about 10 pt a
      // column less 95, from the probe), the share this column has of it, less
      // the two frames around it, the button's inset and the sign. A title is
      // sentence text, about 7 pt a character; the first estimate, at 8 pt and
      // with wider margins, cut titles with room to spare.
      const hitPt = (columns > 0 ? (columns * 10 - 95) * (hasRail ? 0.84 : 1) : 600) * (isWide ? 0.6 : 1) - 90
      const hitChars = Math.max(16, Math.floor(hitPt / 7))
      const fitTitle = (name: string, less = 0) => {
        const room = Math.max(12, hitChars - less)
        return name.length > room ? `${name.slice(0, room - 1)}…` : name
      }
      const hitRow = (hit: PanelHit, index: number) => {
        const isOpen = v.docsOpen === hit.id
        const section = docsSection(hit)
        const summary = docsSummary(hit)
        const whole = d.docsText?.[hit.id]
        const canRead = isOpen && whole === undefined
        return (
          <Box flexDirection="column">
            {/* Read section is on the title's line, at its end, level with the title, and only while the row is open. */}
            <Box flexDirection="row" alignItems="center" justifyContent="space-between" gap="sm">
              <Button
                key={`hit-${index}`}
                plain
                label={`${isOpen ? CHEVRON_OPEN : CHEVRON_CLOSED}  ${fitTitle(hit.title, canRead ? READ_BUTTON_CHARS : 0)}`}
                onPress={set(value => ({ ...value, docsOpen: isOpen ? '' : hit.id }))}
              />
              {canRead ? (
                <Box flexShrink={0}>
                  <Button key={`read-${index}`} label="Read section" onPress={() => void readDocs($, hit.id)} />
                </Box>
              ) : null}
            </Box>
            {/* Set in to stand under the title: as far as a plain button sets its
                name in, and then past the sign and its two spaces (11 pt in the
                owner's screenshot, about 1.25 columns), so the sign has a column of its own. */}
            <Box flexDirection="column" gap="xs" paddingX="xs">
              <Box flexDirection="column" gap="xs" paddingLeft={HIT_SIGN_COLUMNS}>
              {/* A passage with no section of its own is the top of its page. */}
              {hint(section || 'Overview')}
              {isOpen && hit.title.length > hitChars ? <Text weight="medium">{hit.title}</Text> : null}
              {isOpen && whole === undefined && summary ? <Text>{summary}</Text> : null}
              {isOpen && whole === '' ? quiet('Reading the section…') : null}
              {isOpen && whole ? <Markdown key={`section-${index}`} text={whole} /> : null}
              {isOpen ? (
                <Text mono dimColor size="caption">
                  {hit.id}
                </Text>
              ) : null}
              </Box>
            </Box>
          </Box>
        )
      }
      const docsFound = () => [
        typeof hits === 'string' ? quiet(hits) : null,
        Array.isArray(hits) && hits.length === 0 ? quiet('The documentation has nothing on this.') : null,
        ...(Array.isArray(hits) ? hits.map(hitRow) : []),
      ]
      const reader = (one: NonNullable<typeof topic>) => {
        const text = d.topicText[one.name]
        return surface(
          between(
            <Text mono size="title" weight="semibold">
              {one.name}
            </Text>,
            quiet(kindLabel(one.kind as 'api' | 'guide' | 'other')),
          ),
          // The actions come before the text: a topic is long, and under it they were not found.
          row(
            <Button
              key="ask"
              label="Ask Claude about this"
              onPress={() => void $.prompt.submit({ text: `Explain the ServiceNow SDK topic ${one.name} (now-sdk explain ${one.name}) and how I would use it in this project.` })}
            />,
            d.docs && (d.docs.kind === 'folder' || d.docs.kind === 'path') ? (
              <Button key="docs" label="Look up in ServiceNow Docs" onPress={() => void lookUpDocs($, one.name)} />
            ) : null,
          ),
          hits !== undefined ? (
            <Box flexDirection="column" gap="sm" paddingX="md" paddingY="sm" borderStyle="round" borderDimColor>
              {label('ServiceNow Docs')}
              {docsFound()}
            </Box>
          ) : null,
          text ? <Markdown key="topic" text={text} /> : quiet('Reading the topic…'),
          text && isWide ? toTop('topic-top') : null,
        )
      }
      // A desktop draws a button as wide as its label and never cuts it, so a
      // long topic name pushed its kind out of the frame. The name is cut
      // here to what the list has room for; the reader shows it whole.
      const listPt = (columns > 0 ? (columns * COLUMN_PT - 30) * (hasRail ? 0.84 : 1) : 600) * (isWide ? 0.4 : 1) - 28
      const nameChars = Math.max(12, Math.floor((listPt - 90) / NAME_CHAR_PT))
      const fitName = (name: string) => (name.length > nameChars ? `${name.slice(0, nameChars - 1)}…` : name)
      const toolbar = finder(
          <Input
            key="topic-search"
            placeholder={`Search ${d.topics.length} topics`}
            value={v.topicQuery}
            onInput={(value: string) => void update($, view, one => ({ ...one, topicQuery: value, topicPage: 0 }))}
            onSubmit={(value: string) => void update($, view, one => ({ ...one, topicQuery: value, topicPage: 0 }))}
          />,
          <Select
            key="kind-filter"
            value={v.topicKind || 'all'}
            options={[
              { value: 'all', label: 'All kinds' },
              { value: 'api', label: 'API' },
              { value: 'guide', label: 'Guide' },
              { value: 'other', label: 'Reference' },
            ]}
            onSelect={(value: string) => void update($, view, one => ({ ...one, topicKind: value === 'all' ? '' : value, topicPage: 0 }))}
          />,
        hint(found.length === 1 ? '1 topic' : `${found.length} topics`),
      )
      const list = section(
        'Topics',
        ...found.slice(first, first + shownCount).map(one => (
          <Box flexDirection="row" alignItems="center" justifyContent="space-between" gap="sm">
            <Button
              key={`topic-${one.name}`}
              plain
              label={fitName(one.name)}
              onPress={() => {
                void update($, view, value => ({ ...value, topicName: one.name }))
                void loadTopic($, one.name)
              }}
            />
            <Text dimColor size="footnote">
              {kindLabel(one.kind)}
            </Text>
          </Box>
        )),
        d.topics.length === 0 ? quiet(d.sdkError ?? 'No topics were read. Press Refresh on Setup.') : null,
        pages > 1
          ? between(
              hint(`${first + 1} to ${Math.min(first + shownCount, found.length)} of ${found.length}`),
              row(
                page > 0 ? <Button key="topics-previous" label="Previous" onPress={set(value => ({ ...value, topicPage: page - 1 }))} /> : null,
                page < pages - 1 ? <Button key="topics-next" label="Next" onPress={set(value => ({ ...value, topicPage: page + 1 }))} /> : null,
              ),
            )
          : null,
      )
      if (isWide) {
        return (
          <Box flexDirection="column" gap="md">
            {split([toolbar, list], topic ? reader(topic) : surface(<Text weight="medium">No topic chosen</Text>, quiet('Choose a topic in the list to read it.')))}
          </Box>
        )
      }
      if (topic) {
        return (
          <Box flexDirection="column" gap="md">
            <Button key="back-topics" plain label={`${BACK_SIGN}  Back to topics`} onPress={set(value => ({ ...value, topicName: '' }))} />
            {reader(topic)}
          </Box>
        )
      }
      return (
        <Box flexDirection="column" gap="md">
          {toolbar}
          {list}
        </Box>
      )
    }

    // ----------------------------------------------------------------- aiux
    const aiuxScreen = () => {
      const project = d.aiux
      if (d.projectChoice === 'pick') {
        const apps = projects.filter(one => one.isAiux)
        return (
          <Box flexDirection="column" gap="md">
            {title('Pick a project')}
            {quiet(
              `${d.workspace} holds ${projects.length} projects` +
                (apps.length > 0 ? `; ${apps.length === 1 ? 'the AIUX app is' : 'the AIUX apps are'} ${apps.map(one => one.path).join(', ')}.` : '.'),
            )}
            {projectPicker()}
          </Box>
        )
      }
      if ((!project || !project.isAiux) && projects.length > 0) {
        const apps = projects.filter(one => one.isAiux)
        return (
          <Box flexDirection="column" gap="md">
            {title('This project is not an AIUX app')}
            {quiet(
              `An AIUX app has an aiux.json file at its root. ${d.cwd} has none.` +
                (apps.length > 0 ? ` In this folder: ${apps.map(one => one.path).join(', ')}.` : ''),
            )}
            {projectPicker()}
          </Box>
        )
      }
      if (!project || !project.isAiux) {
        return (
          <Box flexDirection="column" gap="md">
            {title('No AIUX project here')}
            {quiet(`An AIUX project has an aiux.json file at its root. ${d.cwd} has none, nor the two levels of folders under it.`)}
            {surface(
              <Text weight="medium">Create AIUX application</Text>,
              commandBox('aiux-init', 'now-sdk', ['init', '--template', 'javascript.aiux'], 1),
              marksText(['changes-local']),
              hint('Run it in your terminal: it asks for the application name and scope.'),
            )}
          </Box>
        )
      }
      const failing = project.checks.filter(check => check.status !== 'ok')
      const column = (name: string, items: string[]) => (
        <Box flexDirection="column" width="33%">
          {label(`${name}  ${items.length}`)}
          {items.length === 0 ? quiet('None') : items.map(item => <Text mono>{item}</Text>)}
        </Box>
      )
      return (
        <Box flexDirection="column" gap="md">
          {title(project.name || 'AIUX project')}
          {quiet([d.cwd, `Source ${project.srcDir || '.'}`, project.version ? `Version ${project.version}` : '', project.framework ?? '', project.pattern ? `${project.pattern} pattern` : '', project.scope ? `Scope ${project.scope}` : ''].filter(Boolean).join('   '))}
          {section(failing.length === 0 ? `Checks, all ${project.checks.length} pass` : `Checks, ${failing.length} to look at`, ...failing.map(checkRow))}
          {/* What you run comes before what the project holds: the lists of pages and components are long. */}
          {section(
            'Scripts',
            ...project.scripts.map(name => {
              const changesInstance = name.startsWith('deploy')
              return between(
                <Text>
                  <Text mono>{`${changesInstance ? '● ' : ' ■'} `}</Text>
                  <Text weight="medium">{SCRIPT_LABELS[name] ?? name}</Text>
                  <Text dimColor mono size="footnote">{`  pnpm run ${name}`}</Text>
                </Text>,
                <Button
                  key={`script-${name}`}
                  label="Review and run"
                  onPress={() =>
                    void confirmAndRun($, {
                      id: `script-${name}`,
                      label: SCRIPT_LABELS[name] ?? name,
                      program: 'pnpm',
                      argv: ['run', name],
                      effects: [changesInstance ? 'changes-instance' : 'changes-local'],
                      confirmation: changesInstance ? 'named' : 'review',
                      cwd: d.cwd || undefined,
                      alias,
                    })
                  }
                />,
              )
            }),
          )}
          {d.run?.commandId.startsWith('script-') ? output(d.run) : null}
          {section(
            'Contents',
            <Box flexDirection="row" gap="md">
              {column('Pages', project.pages)}
              {column('Widgets', project.widgets)}
              {column('Components', project.components)}
            </Box>,
          )}
        </Box>
      )
    }

    // ---------------------------------------------------------------- probe
    // `/sdk-panel probe` draws one of everything, labelled, so a picture of
    // it shows what this surface makes of each element and style.
    const probeScreen = () => {
      const props = (e.props ?? {}) as Record<string, unknown>
      const swatch = (name: string, extra: Record<string, unknown>) => (
        <Box padding="sm" {...extra}>
          <Text size="footnote">{name}</Text>
        </Box>
      )
      return (
        <Box flexDirection="column" gap="md">
          {title('What this surface draws')}
          <Text mono size="footnote">{`surface ${e.surface}  bodyColumns ${String(props.bodyColumns)}  viewport ${e.viewport?.columns ?? '?'}x${e.viewport?.rows ?? '?'}  placement ${String(props.placement)}`}</Text>
          {label('Borders: round, single, double, bold, dim, colored, none')}
          <Box flexDirection="row" gap="sm" flexWrap="wrap">
            {swatch('round', { borderStyle: 'round' })}
            {swatch('single', { borderStyle: 'single' })}
            {swatch('double', { borderStyle: 'double' })}
            {swatch('bold', { borderStyle: 'bold' })}
            {swatch('round dim', { borderStyle: 'round', borderDimColor: true })}
            {swatch('round warning', { borderStyle: 'round', borderColor: 'warning' })}
            {swatch('no border', {})}
          </Box>
          {label('Backgrounds by theme key, then two raw colors')}
          <Box flexDirection="row" gap="sm" flexWrap="wrap">
            {['subtle', 'inactive', 'suggestion', 'success', 'warning', 'error', 'claude', 'permission', 'promptBorder', 'bashBorder'].map(key => swatch(key, { backgroundColor: key }))}
            {swatch('#f6f5f1', { backgroundColor: '#f6f5f1' })}
            {swatch('#282725', { backgroundColor: '#282725' })}
          </Box>
          {label('Text sizes, weights, colors, styles')}
          <Box flexDirection="row" gap="md" flexWrap="wrap" alignItems="center">
            {(['caption', 'footnote', 'body', 'heading', 'title'] as const).map(size => (
              <Text size={size}>{size}</Text>
            ))}
            {(['regular', 'medium', 'semibold', 'bold'] as const).map(weight => (
              <Text weight={weight}>{weight}</Text>
            ))}
          </Box>
          <Box flexDirection="row" gap="md" flexWrap="wrap" alignItems="center">
            {['text', 'inactive', 'subtle', 'suggestion', 'success', 'warning', 'error', 'claude', 'permission'].map(key => (
              <Text color={key}>{key}</Text>
            ))}
            <Text dimColor>dimColor</Text>
            <Text mono>mono</Text>
            <Text underline>underline</Text>
            <Text italic>italic</Text>
            <Text inverse>inverse</Text>
            <Text backgroundColor="warning">background</Text>
          </Box>
          {label('Buttons: default, primary, plain, dim, with styled text inside')}
          <Box flexDirection="row" gap="sm" flexWrap="wrap" alignItems="center">
            <Button key="probe-default" label="Default" onPress={() => {}} />
            <Button key="probe-primary" label="Primary" variant="primary" onPress={() => {}} />
            <Button key="probe-plain" label="Plain" plain onPress={() => {}} />
            <Button key="probe-dim" label="Dim" dimColor onPress={() => {}} />
            <Button key="probe-styled" plain onPress={() => {}}>
              <Text underline weight="bold">
                underlined bold
              </Text>
              <Text dimColor mono>
                {' dim mono'}
              </Text>
            </Button>
            <Text>text beside buttons</Text>
          </Box>
          {label('Widths: 25%, 50%, 100% boxes; an Input and a Select inside a 100% box; an Input of 3 rows')}
          {swatch('25%', { width: '25%', borderStyle: 'single' })}
          {swatch('50%', { width: '50%', borderStyle: 'single' })}
          {swatch('100%', { width: '100%', borderStyle: 'single' })}
          <Box flexDirection="column" width="100%" alignItems="stretch" gap="sm">
            <Input key="probe-input" placeholder="Input in a 100% box" value="" onInput={() => {}} onSubmit={() => {}} />
            <Input key="probe-labelled" label="Labelled" placeholder="Input with a label" value="" onInput={() => {}} onSubmit={() => {}} />
            <Input key="probe-rows" rows={3} placeholder="Input of 3 rows" value="" onInput={() => {}} onSubmit={() => {}} />
            <Select key="probe-select" label="Select" value="a" options={[{ value: 'a', label: 'Option A' }, { value: 'b', label: 'Option B' }]} onSelect={() => {}} />
          </Box>
          {label('A one-line Input and a Select: in a column that stretches its children, then each in a box that grows')}
          <Box flexDirection="column" alignItems="stretch" gap="xs">
            <Input key="probe-stretch" placeholder="One line, stretched" value="" onInput={() => {}} onSubmit={() => {}} />
            <Select key="probe-select-stretch" value="a" options={[{ value: 'a', label: 'Option A' }, { value: 'b', label: 'Option B' }]} onSelect={() => {}} />
          </Box>
          <Box flexDirection="row" gap="sm">
            <Box flexGrow={1} flexDirection="column" alignItems="stretch">
              <Input key="probe-grow" placeholder="One line, growing" value="" onInput={() => {}} onSubmit={() => {}} />
            </Box>
            <Box flexGrow={1} flexDirection="column" alignItems="stretch">
              <Select key="probe-select-grow" value="a" options={[{ value: 'a', label: 'Option A' }, { value: 'b', label: 'Option B' }]} onSelect={() => {}} />
            </Box>
          </Box>
          {label('Signs for a row that opens, as plain buttons: closed and open, with the code of the first')}
          <Box flexDirection="column">
            {(
              [
                ['\u25B8', '\u25BE', '25B8 small'],
                ['\u25BA', '\u25BC', '25BA large'],
                ['\u25B6\uFE0E', '\u25BC', '25B6 text'],
                ['\u23F5', '\u23F7', '23F5'],
                ['\u2BC8', '\u2BC6', '2BC8'],
                ['\u{1F782}', '\u{1F783}', '1F782'],
                ['\u25B9', '\u25BF', '25B9 hollow'],
                ['\u203A', '\u2304', '203A chevron'],
                ['\u276F', '\uFE40', '276F heavy'],
              ] as const
            ).map(([closed, open, name], index) => (
              <Box flexDirection="row" alignItems="center" gap="md">
                <Button key={`probe-closed-${index}`} plain label={`${closed}  Closed row`} onPress={() => {}} />
                <Button key={`probe-open-${index}`} plain label={`${open}  Open row`} onPress={() => {}} />
                <Text dimColor size="footnote">
                  {name}
                </Text>
              </Box>
            ))}
          </Box>
          {label('Two columns, 36% and 64%, each with a border')}
          <Box flexDirection="row" gap="md">
            {swatch('36%', { width: '36%', borderStyle: 'round' })}
            {swatch('64%', { width: '64%', borderStyle: 'round' })}
          </Box>
          {label('Code, wrapped and in a 100% box')}
          <Code source="now-sdk query incident --query 'active=true' --auth dev" language="sh" wrap="wrap" />
          <Box width="100%" flexDirection="column" alignItems="stretch">
            <Code source="now-sdk build" language="sh" wrap="wrap" />
          </Box>
          {label('Markdown with a table and a rule')}
          <Markdown key="probe-markdown" text={'A line.\n\n---\n\n| Mark | Meaning |\n| --- | --- |\n| ■ | Changes local |\n| ● | Changes instance |'} />
          {label(`Elements this surface has: ${Object.keys(ui).sort().join(', ')}`)}

          {label('Space steps as a gap between boxes: xs, sm, md, lg, xl, then 1 and 2 as numbers')}
          {(['xs', 'sm', 'md', 'lg', 'xl', 1, 2] as const).map(step => (
            <Box flexDirection="row" gap={step} alignItems="center">
              {swatch(String(step), { borderStyle: 'round' })}
              {swatch('next', { borderStyle: 'round' })}
            </Box>
          ))}
          {label('Space steps as padding in a box: xs, sm, md, lg, xl')}
          <Box flexDirection="row" gap="sm" flexWrap="wrap" alignItems="flex-start">
            {(['xs', 'sm', 'md', 'lg', 'xl'] as const).map(step => (
              <Box padding={step} borderStyle="round">
                <Text size="footnote">{step}</Text>
              </Box>
            ))}
          </Box>
          {label('Margin md around the middle box; marginLeft lg; columnGap lg with rowGap xs, wrapping')}
          <Box flexDirection="row" alignItems="center">
            {swatch('a', { borderStyle: 'round' })}
            {swatch('margin md', { borderStyle: 'round', margin: 'md' })}
            {swatch('marginLeft lg', { borderStyle: 'round', marginLeft: 'lg' })}
          </Box>
          <Box flexDirection="row" flexWrap="wrap" columnGap="lg" rowGap="xs" width="60%">
            {['one', 'two', 'three', 'four', 'five', 'six', 'seven'].map(name => swatch(name, { borderStyle: 'round' }))}
          </Box>

          {label('justifyContent: flex-start, center, flex-end, space-between, space-around, space-evenly')}
          {(['flex-start', 'center', 'flex-end', 'space-between', 'space-around', 'space-evenly'] as const).map(justify => (
            <Box flexDirection="row" justifyContent={justify} borderStyle="round" borderDimColor>
              {swatch(justify, { borderStyle: 'round' })}
              {swatch('b', { borderStyle: 'round' })}
              {swatch('c', { borderStyle: 'round' })}
            </Box>
          ))}
          {label('alignItems in a row with a tall box: flex-start, center, flex-end, stretch; then alignSelf flex-end on the last')}
          {(['flex-start', 'center', 'flex-end', 'stretch'] as const).map(align => (
            <Box flexDirection="row" alignItems={align} gap="sm" borderStyle="round" borderDimColor>
              <Box borderStyle="round" paddingY="lg" paddingX="sm">
                <Text size="footnote">tall</Text>
              </Box>
              {swatch(align, { borderStyle: 'round' })}
              {swatch('self end', { borderStyle: 'round', alignSelf: 'flex-end' })}
            </Box>
          ))}
          {label('flexDirection: row-reverse, column-reverse; flexWrap wrap-reverse')}
          <Box flexDirection="row-reverse" gap="sm">
            {swatch('1', { borderStyle: 'round' })}
            {swatch('2', { borderStyle: 'round' })}
            {swatch('3', { borderStyle: 'round' })}
          </Box>
          <Box flexDirection="column-reverse">
            <Text size="footnote">first in the code</Text>
            <Text size="footnote">second in the code</Text>
          </Box>
          <Box flexDirection="row" flexWrap="wrap-reverse" gap="xs" width="50%">
            {['one', 'two', 'three', 'four', 'five', 'six'].map(name => swatch(name, { borderStyle: 'round' }))}
          </Box>
          {label('flexGrow 1 beside flexGrow 2; a box that may not shrink beside long text')}
          <Box flexDirection="row" gap="sm">
            {swatch('grow 1', { borderStyle: 'round', flexGrow: 1 })}
            {swatch('grow 2', { borderStyle: 'round', flexGrow: 2 })}
          </Box>
          <Box flexDirection="row" gap="sm">
            {swatch('shrink 0', { borderStyle: 'round', flexShrink: 0 })}
            <Text size="footnote">Long text beside it that takes more than the line has, so that something must give way, and it is this text that wraps.</Text>
          </Box>
          {label('Sizes in cells: width 10, 20; height 3; minWidth 30; minHeight 4')}
          <Box flexDirection="row" gap="sm" alignItems="flex-start" flexWrap="wrap">
            {swatch('w 10', { borderStyle: 'round', width: 10 })}
            {swatch('w 20', { borderStyle: 'round', width: 20 })}
            {swatch('h 3', { borderStyle: 'round', height: 3 })}
            {swatch('minW 30', { borderStyle: 'round', minWidth: 30 })}
            {swatch('minH 4', { borderStyle: 'round', minHeight: 4 })}
          </Box>
          {label('overflow hidden on a box 12 wide; display none (nothing between the two marks)')}
          <Box width={12} overflow="hidden" borderStyle="round">
            <Text size="footnote" wrap="truncate-end">overflow-hidden-cuts-this-long-word-off</Text>
          </Box>
          <Box flexDirection="row" gap="sm">
            <Text size="footnote">[</Text>
            <Box display="none">
              <Text size="footnote">hidden</Text>
            </Box>
            <Text size="footnote">]</Text>
          </Box>
          {label('position: a box set absolutely at the right of a relative box; one moved with top and left')}
          <Box position="relative" borderStyle="round" paddingY="md" paddingX="sm">
            <Text size="footnote">relative box</Text>
            <Box position="absolute" top={0} right={0} borderStyle="round" borderColor="warning">
              <Text size="footnote">absolute top right</Text>
            </Box>
          </Box>
          <Box position="relative" top={1} left={4} borderStyle="round">
            <Text size="footnote">relative, top 1 left 4</Text>
          </Box>
          <Box minHeight={1} />
          {label('Hover: point at each. A box that takes a background and a frame; text that takes a color; a button')}
          <Box flexDirection="row" gap="sm" flexWrap="wrap" alignItems="center">
            <Box key="probe-hover-box" padding="sm" borderStyle="round" borderDimColor hover={{ backgroundColor: 'rgba(128, 128, 128, 0.16)', borderColor: 'suggestion' }}>
              <Text size="footnote">hover box</Text>
            </Box>
            <Box key="probe-hover-text" padding="sm">
              <Text size="footnote" hover={{ color: 'suggestion', bold: true }}>
                hover text
              </Text>
            </Box>
            <Box key="probe-hover-button-box">
              <Button key="probe-hover-button" plain label="hover button" hover={{ color: 'claude' }} onPress={() => {}} />
            </Box>
          </Box>
          {label('Border colors by theme key; backgrounds and text in the theme keys not shown above')}
          <Box flexDirection="row" gap="sm" flexWrap="wrap">
            {['suggestion', 'success', 'error', 'claude', 'permission', 'inactive'].map(name => swatch(name, { borderStyle: 'round', borderColor: name }))}
          </Box>
          <Box flexDirection="row" gap="sm" flexWrap="wrap">
            {['text', 'inverseText', 'remember', 'merged', 'planMode', 'autoAccept', 'ide', 'diffAdded', 'diffRemoved', 'diffAddedDimmed', 'diffRemovedDimmed', 'diffAddedWord', 'diffRemovedWord'].map(name =>
              swatch(name, { backgroundColor: name }),
            )}
          </Box>
          <Box flexDirection="row" gap="md" flexWrap="wrap">
            {['inverseText', 'remember', 'merged', 'planMode', 'autoAccept', 'promptBorder', 'bashBorder', 'ide', 'diffAdded', 'diffRemoved'].map(name => (
              <Text color={name}>{name}</Text>
            ))}
            <Text color="#e5484d">#e5484d</Text>
            <Text color="rgba(45, 164, 78, 0.6)">rgba</Text>
          </Box>

          {label('Text: bold, strikethrough, tabular figures beside plain ones, right to left')}
          <Box flexDirection="row" gap="md" flexWrap="wrap">
            <Text bold>bold</Text>
            <Text strikethrough>strikethrough</Text>
            <Text tabular>1111 tabular</Text>
            <Text>1111 plain</Text>
            <Text dir="rtl">right to left</Text>
            <Text weight="semibold" size="footnote" dimColor>
              semibold footnote dim
            </Text>
          </Box>
          {label('Text wrap in a box 24 wide: wrap, end, middle, truncate, truncate-start, truncate-middle, truncate-end')}
          {(['wrap', 'end', 'middle', 'truncate', 'truncate-start', 'truncate-middle', 'truncate-end'] as const).map(wrap => (
            <Box width={24} borderStyle="round" borderDimColor>
              <Text size="footnote" wrap={wrap}>{`${wrap}: australia:markdown/application-development/servicenow-sdk`}</Text>
            </Box>
          ))}

          {label('Buttons: secondary, dim and plain, with a hotkey (1, w), dismiss, text and styled text as children')}
          <Box flexDirection="row" gap="sm" flexWrap="wrap" alignItems="center">
            <Button key="probe-secondary" label="Secondary" variant="secondary" onPress={() => {}} />
            <Button key="probe-dim-plain" label="Dim plain" plain dimColor onPress={() => {}} />
            <Button key="probe-hotkey-1" label="Hotkey 1" hotkey="1" onPress={() => {}} />
            <Button key="probe-hotkey-w" label="Hotkey w" hotkey="w" onPress={() => {}} />
            <Button key="probe-dismiss" label="Dismiss" role="dismiss" onPress={() => {}} />
            <Button key="probe-children" onPress={() => {}}>
              Name <Text dimColor>2m</Text>
            </Button>
          </Box>
          {label('Input: one line with a submit label; two lines with one; four lines')}
          <Input key="probe-submit" submitLabel="Send" placeholder="One line, submit label Send" value="" onInput={() => {}} onSubmit={() => {}} />
          <Input key="probe-rows-2" rows={2} submitLabel="Save" placeholder="Two lines, submit label Save" value="" onInput={() => {}} onSubmit={() => {}} />
          <Input key="probe-rows-4" rows={4} placeholder="Four lines" value="" onInput={() => {}} onSubmit={() => {}} />
          <Input key="probe-value" value="An input that holds text" onInput={() => {}} onSubmit={() => {}} />
          {label('Select: a long option; options without labels')}
          <Box flexDirection="row" gap="sm" flexWrap="wrap">
            <Select
              key="probe-select-long"
              value="long"
              options={[
                { value: 'long', label: 'An option with a long name to see how wide a menu gets' },
                { value: 'b', label: 'Short' },
              ]}
              onSelect={() => {}}
            />
            <Select key="probe-select-bare" value="reads-instance" options={[{ value: 'reads-instance' }, { value: 'changes-instance' }]} onSelect={() => {}} />
          </Box>

          {label('Code: TypeScript with a path and a first line of 40; a diff; a long line cut at its end')}
          <Code source={"export const table = Table({\n  name: 'x_acme_work_order',\n})"} language="ts" path="src/fluent/table.now.ts" startLine={40} />
          <Code source={"@@ -1,3 +1,3 @@\n const a = 1\n-const b = 2\n+const b = 3\n const c = 4"} format="diff" language="ts" path="src/a.ts" />
          <Code source="now-sdk query incident --query 'active=true^priority<=2^assignment_group.name=Service Desk' --fields number,short_description,priority --limit 50 --auth dev" language="sh" wrap="truncate-end" />
          {label('Markdown: headings, emphasis, lists, a quote, inline code, a code block, a link, a task list; then dim')}
          <Markdown
            key="probe-markdown-all"
            text={
              '# Heading 1\n\n## Heading 2\n\n### Heading 3\n\nPlain, **bold**, *italic*, ~~struck~~, `inline code` and a [link](https://www.servicenow.com/docs).\n\n- A bullet\n  - A nested bullet\n- Another\n\n1. First\n2. Second\n\n> A quote.\n\n```ts\nconst a = 1\n```\n\n- [ ] To do\n- [x] Done\n'
            }
          />
          <Markdown key="probe-markdown-dim" dimColor text={'Dim Markdown with **bold** and `code`.'} />
          {ui.Link ? label('Link: with a label, and bare') : null}
          {ui.Link ? (
            <Box flexDirection="row" gap="md" flexWrap="wrap">
              <ui.Link href="https://www.servicenow.com/docs" label="ServiceNow documentation" />
              <ui.Link href="https://www.servicenow.com/docs" />
            </Box>
          ) : null}
          {ui.Progress ? label('Progress: a third done; with its own words; in a color; running with no known end; done') : null}
          {ui.Progress ? (
            <Box flexDirection="column" gap="sm">
              <ui.Progress label="Reading topics" value={1} max={3} />
              <ui.Progress label="Installing" value={412} max={900} valueText="412 of 900" />
              <ui.Progress label="In a color" value={0.6} color="success" />
              <ui.Progress label="Running" />
              <ui.Progress label="Done" value={1} />
            </Box>
          ) : null}
          {label(`Not drawn here: Image and Raster are a terminal's (this surface ${ui.Image ? 'has' : 'has no'} Image, ${ui.Raster ? 'has' : 'has no'} Raster); Client needs a module of its own.`)}

          {ui.Svg ? label('Svg, sized in CSS pixels: a monitor as an image; with its own width and height; in a frame; a cloud; a 32 px red square') : null}
          {ui.Svg ? (
            <Box flexDirection="row" gap="md" alignItems="center">
              <ui.Svg alt="A monitor" width={24} height={24} source={`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">${PROBE_MONITOR}</svg>`} />
              <ui.Svg alt="A monitor" source={`<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">${PROBE_MONITOR}</svg>`} />
              <ui.Svg alt="A monitor" width={24} height={24} isInteractive source={`<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">${PROBE_MONITOR}</svg>`} />
              <ui.Svg alt="A cloud" width={24} height={24} source={`<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">${PROBE_CLOUD}</svg>`} />
              <ui.Svg alt="A red square" width={32} height={32} source={'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><rect width="32" height="32" fill="#e5484d"/></svg>'} />
            </Box>
          ) : null}
          {label('Signs as text: circle, triangle, diamond, check, warning, cloud, keyboard, monitor, laptop')}
          <Box flexDirection="row" gap="md" alignItems="center">
            <Text color="success">{'\u25CF'}</Text>
            <Text color="warning">{'\u25B2'}</Text>
            <Text color="error">{'\u25C6'}</Text>
            <Text color="success">{'\u2713'}</Text>
            <Text color="warning">{'\u26A0\uFE0E'}</Text>
            <Text dimColor>{'\u2601\uFE0E'}</Text>
            <Text dimColor>{'\u2328\uFE0E'}</Text>
            <Text dimColor>{'\u{1F5A5}\uFE0E'}</Text>
            <Text dimColor>{'\u{1F4BB}'}</Text>
          </Box>
        </Box>
      )
    }

    const screens: Record<Exclude<PanelScreen, 'probe'>, () => unknown> = {
      setup: setupScreen,
      instances: instancesScreen,
      commands: commandsScreen,
      explain: explainScreen,
      aiux: aiuxScreen,
    }

    return (
      <Box flexDirection="column" gap="md" paddingX="md" paddingY="sm">
        {hasRail ? (
          <Box flexDirection="row" gap="lg" alignItems="flex-start">
            <Box width="14%" flexDirection="column">
              {rail}
            </Box>
            <Box width="86%" flexDirection="column">
              {v.screen === 'probe' ? probeScreen() : screens[v.screen]()}
            </Box>
          </Box>
        ) : (
          [tabs, v.screen === 'probe' ? probeScreen() : screens[v.screen]()]
        )}
      </Box>
    )
  })
}
