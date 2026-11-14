// @ts-check
/**
 * Reads the text `now-sdk <command> --help` prints (yargs format) into data,
 * so the panel can draw a form for a command from the installed SDK's own
 * description instead of a copy that goes stale.
 *
 * No Node imports.
 */

/**
 * @typedef {object} HelpOption
 * @property {string} name          Long name without dashes, e.g. "display-value".
 * @property {string[]} flags       As written, e.g. ["-q", "--query"].
 * @property {string} description
 * @property {string} [type]        boolean, string, number, array or count.
 * @property {boolean} isRequired
 * @property {string[]} [choices]
 * @property {string} [defaultValue]
 * @property {boolean} isGlobal     True for --debug, --help and --version.
 */

/**
 * @typedef {object} HelpParameter
 * @property {string} name
 * @property {string} description
 * @property {string} [type]
 * @property {boolean} isRequired
 * @property {string} [defaultValue]
 */

/**
 * @typedef {object} HelpSubcommand
 * @property {string} name          e.g. "auth" or "cicd test".
 * @property {string} usage         e.g. "now-sdk download <directory>".
 * @property {string} summary
 * @property {string[]} aliases
 */

/**
 * @typedef {object} Help
 * @property {string} usage
 * @property {string} description
 * @property {HelpSubcommand[]} commands
 * @property {HelpParameter[]} parameters
 * @property {{ title: string, options: HelpOption[] }[]} groups
 * @property {string} examples      The examples block as printed, or "".
 */

const GLOBAL_OPTIONS = new Set(['debug', 'help', 'version']);
const HEADER = /^(\S[^:]*):\s*$/;
const OPTION_START = /^\s+((?:-\w,\s+)?--[\w-]+)(?:\s{2,}|\s*$)(.*)$/;
const COMMAND_START = /^\s+(now-sdk\s+\S.*?)(?:\s{2,}|\s*$)(.*)$/;
const PARAMETER_START = /^\s{2}(\w[\w.-]*)\s{2,}(.*)$/;
const BANNER = /^[\s_/\\|<>.()-]*$/;

/**
 * @param {string} text what `--help` printed
 * @returns {Help}
 */
export function parseHelp(text) {
  const lines = stripAnsi(text).replaceAll('\r', '').split('\n');

  /** @type {Help} */
  const help = { usage: '', description: '', commands: [], parameters: [], groups: [], examples: '' };
  /** @type {string[]} */
  const intro = [];
  let section = '';
  /** @type {{ kind: 'option' | 'command' | 'parameter', head: string, body: string } | undefined} */
  let item;
  /** @type {string[]} */
  const exampleLines = [];

  const flush = () => {
    if (!item) return;
    if (item.kind === 'option') addOption(help, section, item.head, item.body);
    if (item.kind === 'command') help.commands.push(toSubcommand(item.head, item.body));
    if (item.kind === 'parameter') help.parameters.push(toParameter(item.head, item.body));
    item = undefined;
  };

  for (const line of lines) {
    const header = HEADER.exec(line);
    if (header && !line.startsWith(' ')) {
      flush();
      section = header[1];
      continue;
    }
    if (!section) {
      intro.push(line);
      continue;
    }
    if (section === 'Examples') {
      exampleLines.push(line);
      continue;
    }
    if (line.trim() === '') {
      flush();
      continue;
    }
    if (!line.startsWith(' ')) {
      // Text after the sections (the epilogue) ends them.
      flush();
      section = 'Epilogue';
      continue;
    }
    if (section === 'Epilogue') continue;

    const start =
      section === 'Commands'
        ? match(COMMAND_START, line, 'command')
        : section === 'Parameters'
          ? match(PARAMETER_START, line, 'parameter')
          : match(OPTION_START, line, 'option');
    if (start) {
      flush();
      item = start;
    } else if (item) {
      item.body = join(item.body, line.trim());
    }
  }
  flush();

  const text0 = intro.filter((line) => !BANNER.test(line) || line.trim() === '');
  const firstText = text0.findIndex((line) => line.trim() !== '');
  if (firstText >= 0 && text0[firstText].trimStart().startsWith('now-sdk')) {
    help.usage = text0[firstText].trim();
    help.description = paragraph(text0.slice(firstText + 1));
  } else {
    help.description = paragraph(text0);
  }
  help.examples = exampleLines.join('\n').trim();
  return help;
}

/**
 * The options a form shows: every group's options without the three global
 * ones.
 *
 * @param {Help} help
 * @returns {HelpOption[]}
 */
export function ownOptions(help) {
  return help.groups.flatMap((group) => group.options).filter((option) => !option.isGlobal);
}

/** @param {string} text */
export function stripAnsi(text) {
  // eslint-disable-next-line no-control-regex
  return text.replace(/\x1b\[[0-9;]*[A-Za-z]/g, '');
}

/**
 * @param {RegExp} pattern
 * @param {string} line
 * @param {'option' | 'command' | 'parameter'} kind
 */
function match(pattern, line, kind) {
  const found = pattern.exec(line);
  return found ? { kind, head: found[1].trim(), body: found[2].trim() } : undefined;
}

/**
 * Joins a wrapped line onto what came before. yargs breaks a long bracketed
 * tag (a default path, a choices list) in the middle, so inside an open
 * bracket the pieces join without a space.
 *
 * @param {string} before
 * @param {string} piece
 */
function join(before, piece) {
  if (!before) return piece;
  const isInsideTag = before.lastIndexOf('[') > before.lastIndexOf(']');
  if (!isInsideTag) return `${before} ${piece}`;
  return /[,:]$/.test(before) ? `${before} ${piece}` : `${before}${piece}`;
}

/** @param {string[]} lines */
function paragraph(lines) {
  return lines
    .map((line) => line.trim())
    .join('\n')
    .split(/\n{2,}/)
    .map((block) => block.replaceAll('\n', ' ').trim())
    .filter(Boolean)
    .join('\n\n');
}

/**
 * Takes the trailing yargs tags off a description: [string], [required],
 * [choices: ...], [default: ...], [aliases: ...].
 *
 * @param {string} body
 */
function splitTags(body) {
  /** @type {{ type?: string, isRequired: boolean, choices?: string[], defaultValue?: string, aliases: string[] }} */
  const tags = { isRequired: false, aliases: [] };
  let rest = body;
  const tag = /\s*\[(boolean|string|number|array|count|required|(?:choices|default|aliases): [^\]]*)\]\s*$/;
  for (let found = tag.exec(rest); found; found = tag.exec(rest)) {
    const value = found[1];
    if (value === 'required') tags.isRequired = true;
    else if (value.startsWith('choices: ')) tags.choices = splitList(value.slice(9));
    else if (value.startsWith('default: ')) tags.defaultValue = unquote(value.slice(9).trim());
    else if (value.startsWith('aliases: ')) tags.aliases = splitList(value.slice(9));
    else tags.type = value;
    rest = rest.slice(0, found.index);
  }
  return { description: rest.trim(), tags };
}

/** @param {string} list */
function splitList(list) {
  return list
    .split(',')
    .map((part) => unquote(part.trim()))
    .filter(Boolean);
}

/** @param {string} value */
function unquote(value) {
  return value.replace(/^"(.*)"$/, '$1');
}

/**
 * @param {Help} help
 * @param {string} section
 * @param {string} head
 * @param {string} body
 */
function addOption(help, section, head, body) {
  const flags = head.split(/,\s+/);
  const name = (flags.find((flag) => flag.startsWith('--')) ?? flags[0]).replace(/^-+/, '');
  const { description, tags } = splitTags(body);
  /** @type {HelpOption} */
  const option = { name, flags, description, isRequired: tags.isRequired, isGlobal: GLOBAL_OPTIONS.has(name) };
  if (tags.type) option.type = tags.type;
  if (tags.choices) option.choices = tags.choices;
  if (tags.defaultValue !== undefined) option.defaultValue = tags.defaultValue;

  let group = help.groups.find((one) => one.title === section);
  if (!group) {
    group = { title: section, options: [] };
    help.groups.push(group);
  }
  group.options.push(option);
}

/**
 * @param {string} head
 * @param {string} body
 * @returns {HelpSubcommand}
 */
function toSubcommand(head, body) {
  const { description, tags } = splitTags(body);
  const words = head.replace(/^now-sdk\s+/, '').split(/\s+/);
  const name = words.filter((word) => !/^[<[]/.test(word)).join(' ');
  return { name, usage: head, summary: description, aliases: tags.aliases };
}

/**
 * @param {string} head
 * @param {string} body
 * @returns {HelpParameter}
 */
function toParameter(head, body) {
  const { description, tags } = splitTags(body);
  /** @type {HelpParameter} */
  const parameter = { name: head, description, isRequired: tags.isRequired };
  if (tags.type) parameter.type = tags.type;
  if (tags.defaultValue !== undefined) parameter.defaultValue = tags.defaultValue;
  return parameter;
}
