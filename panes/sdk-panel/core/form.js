// @ts-check
/**
 * From a command's `--help` and what the person typed to the arguments that
 * will run. Both panels build their forms and their command line with this,
 * so they cannot disagree about what a form means.
 *
 * No Node imports.
 */

/**
 * @typedef {object} FormCommand
 * @property {string} id
 * @property {string[]} argv
 * @property {{ parameters: { name: string, isRequired: boolean }[],
 *   options: { name: string, flags?: string[], type?: string, isRequired: boolean, defaultValue?: string }[] }} help
 */

/**
 * @typedef {Record<string, string | boolean | undefined>} FormValues
 * Keyed "param:<name>" and "opt:<name>".
 */

/**
 * The options a form shows: not `--auth` (the instance picker sets it) and
 * not a flag the command itself is (`install --info`).
 *
 * @template {FormCommand} C
 * @param {C} command
 * @returns {C['help']['options']}
 */
export function formOptions(command) {
  return command.help.options.filter(
    (option) => option.name !== 'auth' && !(option.flags ?? [`--${option.name}`]).some((flag) => command.argv.includes(flag)),
  );
}

/** @param {FormCommand} command */
export function takesInstance(command) {
  return command.help.options.some((option) => option.name === 'auth');
}

/**
 * The arguments after `now-sdk`. A value equal to the option's default is
 * left out; a boolean that differs from its default becomes `--name` or
 * `--no-name`; the alias, when the command takes one, is always passed.
 *
 * @param {FormCommand} command
 * @param {FormValues} values
 * @param {string} [alias]
 * @returns {string[]}
 */
export function composeArgv(command, values, alias) {
  const argv = [...command.argv];
  for (const parameter of command.help.parameters) {
    const value = String(values[`param:${parameter.name}`] ?? '').trim();
    if (value) argv.push(value);
  }
  for (const option of formOptions(command)) {
    const raw = values[`opt:${option.name}`];
    if (option.type === 'boolean') {
      const isDefaultOn = option.defaultValue === 'true';
      const isOn = raw === undefined || raw === '' ? isDefaultOn : raw === true || raw === 'true';
      if (isOn !== isDefaultOn) argv.push(isOn ? `--${option.name}` : `--no-${option.name}`);
    } else {
      const value = String(raw ?? '').trim();
      if (value && value !== option.defaultValue) argv.push(`--${option.name}`, value);
    }
  }
  if (alias && takesInstance(command)) argv.push('--auth', alias);
  return argv;
}

/**
 * The name of the first required parameter or option without a value, or
 * undefined when the form is complete.
 *
 * @param {FormCommand} command
 * @param {FormValues} values
 */
export function missingRequired(command, values) {
  for (const parameter of command.help.parameters) {
    if (parameter.isRequired && !String(values[`param:${parameter.name}`] ?? '').trim()) return parameter.name;
  }
  for (const option of formOptions(command)) {
    if (option.isRequired && !String(values[`opt:${option.name}`] ?? '').trim()) return option.name;
  }
  return undefined;
}

/**
 * An option name as a label: "display-value" is "Display value".
 *
 * @param {string} name
 */
export function labelOf(name) {
  const words = name
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[-_.]/g, ' ')
    .toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
