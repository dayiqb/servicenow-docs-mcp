// @ts-check
/**
 * The setup status: is the SDK usable on this computer, and what is missing.
 *
 * The thresholds come from the `now-sdk-setup` skill and the SDK itself:
 * Node 20 or later; `explain` needs SDK 4.6.0, `query` needs 4.8.0.
 *
 * No Node imports.
 */

/**
 * @typedef {'ok' | 'attention' | 'problem' | 'unknown'} SetupStatus
 */

/**
 * @typedef {object} SetupCheck
 * @property {string} id
 * @property {string} label
 * @property {SetupStatus} status
 * @property {string} value      What was found, e.g. "v26.8.1".
 * @property {string} [fix]      What to do, when something is.
 */

/**
 * @typedef {object} SetupFacts
 * @property {string | null} nodeVersion     e.g. "v26.8.1"; null when Node was not found.
 * @property {string | null} sdkVersion      e.g. "4.14.0"; null when now-sdk was not found.
 * @property {number | null} topicCount      Topics `explain --list` returned; null when not read.
 * @property {import('./instances.js').Instance[] | null} instances  null when the list was not read.
 * @property {string | null} [instancesError] Why the list could not be read.
 * @property {{ kind: string, version?: string } | null} [docs]
 *   The ServiceNow Docs extension as cli/docs.js found it; null or absent when not looked for.
 */

export const MINIMUM = Object.freeze({ node: '20.0.0', sdk: '4.6.0', sdkQuery: '4.8.0' });

/**
 * @param {SetupFacts} facts
 * @returns {{ status: SetupStatus, checks: SetupCheck[] }}
 */
export function evaluateSetup(facts) {
  /** @type {SetupCheck[]} */
  const checks = [];

  if (facts.nodeVersion === null) {
    checks.push({
      id: 'node',
      label: 'Node.js',
      status: 'problem',
      value: 'Not found',
      fix: 'Install Node.js 20 or later.',
    });
  } else if (compareVersions(facts.nodeVersion, MINIMUM.node) < 0) {
    checks.push({
      id: 'node',
      label: 'Node.js',
      status: 'problem',
      value: facts.nodeVersion,
      fix: 'The SDK needs Node.js 20 or later.',
    });
  } else {
    checks.push({ id: 'node', label: 'Node.js', status: 'ok', value: facts.nodeVersion });
  }

  if (facts.sdkVersion === null) {
    checks.push({
      id: 'sdk',
      label: 'ServiceNow SDK',
      status: 'problem',
      value: 'Not found',
      fix: 'Run npm install -g @servicenow/sdk@latest in your terminal.',
    });
  } else if (compareVersions(facts.sdkVersion, MINIMUM.sdk) < 0) {
    checks.push({
      id: 'sdk',
      label: 'ServiceNow SDK',
      status: 'problem',
      value: facts.sdkVersion,
      fix: `Documentation lookup needs ${MINIMUM.sdk} or later. Run npm install -g @servicenow/sdk@latest.`,
    });
  } else if (compareVersions(facts.sdkVersion, MINIMUM.sdkQuery) < 0) {
    checks.push({
      id: 'sdk',
      label: 'ServiceNow SDK',
      status: 'attention',
      value: facts.sdkVersion,
      fix: `Query needs ${MINIMUM.sdkQuery} or later.`,
    });
  } else {
    checks.push({ id: 'sdk', label: 'ServiceNow SDK', status: 'ok', value: facts.sdkVersion });
  }

  if (facts.topicCount === null) {
    checks.push({ id: 'explain', label: 'SDK documentation', status: 'unknown', value: 'Not read' });
  } else if (facts.topicCount === 0) {
    checks.push({
      id: 'explain',
      label: 'SDK documentation',
      status: 'problem',
      value: 'No topics',
      fix: 'Run now-sdk explain --list in your terminal to see the error.',
    });
  } else {
    checks.push({
      id: 'explain',
      label: 'SDK documentation',
      status: 'ok',
      value: `${facts.topicCount} topics`,
    });
  }

  if (facts.instances === null) {
    checks.push({
      id: 'instances',
      label: 'Instances',
      status: 'unknown',
      value: facts.instancesError ?? 'Not read',
    });
  } else if (facts.instances.length === 0) {
    checks.push({
      id: 'instances',
      label: 'Instances',
      status: 'attention',
      value: 'None',
      fix: 'Add an instance to run commands against it.',
    });
  } else {
    const defaultInstance = facts.instances.find((instance) => instance.isDefault);
    checks.push({
      id: 'instances',
      label: 'Instances',
      status: defaultInstance ? 'ok' : 'attention',
      value: defaultInstance
        ? `${facts.instances.length}, default ${defaultInstance.alias}`
        : `${facts.instances.length}, no default`,
      ...(defaultInstance ? {} : { fix: 'Set a default instance.' }),
    });
  }

  if (facts.docs) {
    const found = facts.docs.kind === 'folder' || facts.docs.kind === 'path';
    checks.push(
      found
        ? { id: 'docs', label: 'ServiceNow Docs extension', status: 'ok', value: facts.docs.version ?? 'Found' }
        : {
            id: 'docs',
            label: 'ServiceNow Docs extension',
            status: 'attention',
            value: facts.docs.kind === 'old' ? `${facts.docs.version}, too old` : 'Not found',
            fix:
              facts.docs.kind === 'old'
                ? 'Optional. Lookups in the platform documentation need version 0.1.7 or later.'
                : 'Optional. With it, the panel can look up the platform documentation.',
          },
    );
  }

  return { status: worst(checks.map((one) => one.status)), checks };
}

/**
 * Compares two versions by their numeric parts: negative when `a` is older.
 * A leading "v" and anything after a dash (a pre-release tag) are ignored.
 *
 * @param {string} a
 * @param {string} b
 */
export function compareVersions(a, b) {
  const left = parts(a);
  const right = parts(b);
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const difference = (left[index] ?? 0) - (right[index] ?? 0);
    if (difference !== 0) return difference;
  }
  return 0;
}

/** @param {string} version */
function parts(version) {
  return version
    .trim()
    .replace(/^v/i, '')
    .split('-')[0]
    .split('.')
    .map((part) => Number.parseInt(part, 10) || 0);
}

/** @param {SetupStatus[]} statuses @returns {SetupStatus} */
function worst(statuses) {
  if (statuses.includes('problem')) return 'problem';
  if (statuses.includes('attention')) return 'attention';
  if (statuses.includes('unknown')) return 'unknown';
  return 'ok';
}
