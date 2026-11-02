import {navLayoutContext} from '@servicenow/aiux/aiux-components-nav';
import {i18n} from '@servicenow/aiux/aiux-services';
import {AppTheme} from './theme.js';

export default {
  appTheme: AppTheme,
  applicationLayout: 'aiux-nav-layout',

  setup(ctx) {
    const items = [
      {
        icon: 'home',
        title: i18n.getMessage('Dashboard'),
        action: {type: 'navigate', path: '/home'}
      },
      {
        icon: 'cog-outline',
        title: i18n.getMessage('Settings'),
        action: {type: 'navigate', path: '/settings'}
      }
    ];

    const activeRoute = ctx.app?.routes?.find(r => r.active);
    const itemsWithActive = items.map(item => ({
      ...item,
      ...(item.action?.path === activeRoute?.route && {active: true})
    }));

    const current = navLayoutContext.get();
    navLayoutContext.set({
      ...current,
      appTitle: i18n.getMessage('Lux Dashboard Builder'),
      features: {
        menus: false,
        logo: true,
        userSession: false,
        notifications: false,
        themeToggle: false,
        densityPicker: false,
        unifiedExperience: false,
        profile: true,
        helpPanel: true
      },
      items: itemsWithActive,
      defaultLogoFull: 'servicenow',
      defaultLogoIcon: 'servicenow'
    });
  },

  teardown() {
    navLayoutContext.set({
      items: [],
      defaultLogoFull: null,
      defaultLogoIcon: null
    });
  }
};
