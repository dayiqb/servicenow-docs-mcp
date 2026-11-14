// @ts-check
/**
 * A made-up AIUX project in memory, used by the tests and by the previews.
 * `SECRET` stands in for the sign-in value an aiux.json can hold; it is a
 * sample, not a real credential.
 */

/**
 * A project in memory: paths to file text. Folders exist where files do.
 * @param {Record<string, string>} tree
 * @returns {import('../core/aiux.js').ProjectFiles}
 */
export function memoryFiles(tree) {
  return {
    async readText(path) {
      return Object.hasOwn(tree, path) ? tree[path] : null;
    },
    async listDirectory(path) {
      const prefix = `${path}/`;
      /** @type {Map<string, boolean>} */
      const entries = new Map();
      for (const file of Object.keys(tree)) {
        if (!file.startsWith(prefix)) continue;
        const rest = file.slice(prefix.length);
        const cut = rest.indexOf('/');
        if (cut === -1) entries.set(rest, false);
        else entries.set(rest.slice(0, cut), true);
      }
      if (entries.size === 0) return null;
      return [...entries].map(([name, isDirectory]) => ({ name, isDirectory }));
    },
  };
}

export const SECRET = 'Basic c2FtcGxlOnNhbXBsZQ==';

export const sampleProject = {
  '/app/aiux.json': JSON.stringify({
    name: 'Field Service Desk',
    basename: 'field-service-desk',
    landing: '/home',
    srcDir: 'src/lux',
    projectId: 'x_acme_fsd',
    development: { token: SECRET },
    build: { exclude: ['**/*.test.js'] },
  }),
  '/app/package.json': JSON.stringify({
    name: 'field-service-desk',
    version: '1.4.0',
    dependencies: { lit: '^3.2.0' },
    devDependencies: { '@servicenow/aiux-cli': '^2.0.0', '@servicenow/aiux': '^2.1.0' },
    aiux: { basename: 'field-service-desk' },
    scripts: { dev: 'aiux dev', build: 'aiux build', deploy: 'aiux deploy', 'deploy:full': 'pnpm run build && pnpm run deploy', lint: 'eslint .' },
  }),
  '/app/now.config.json': JSON.stringify({ scope: 'x_acme_fsd', scopeId: 'a1b2c3d4e5f60718293a4b5c6d7e8f90' }),
  '/app/src/lux/application.js': '',
  '/app/src/lux/theme.js': '',
  '/app/src/lux/pages/layout.js': '',
  '/app/src/lux/pages/home/page.js': '',
  '/app/src/lux/pages/home/components/hero.js': '',
  '/app/src/lux/pages/list/[table]/page.js': '',
  '/app/src/lux/pages/record/[table]/[id]/page.js': '',
  '/app/src/lux/pages/home/_variants/manager/page.js': '',
  '/app/src/lux/widgets/open-work-orders/index.js': '',
  '/app/src/lux/widgets/open-work-orders/server.js': '',
  '/app/src/lux/widgets/technician-map/index.js': '',
  '/app/src/lux/components/status-chip.js': '',
  '/app/src/lux/components/work-order-card/index.js': '',
  '/app/node_modules/x/pages/page.js': '',
};

