import { createApp } from 'vue';
import { createVuetify } from 'vuetify';
import * as components from 'vuetify/components';
import * as directives from 'vuetify/directives';
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg';
import { zhHans } from 'vuetify/locale';
import 'vuetify/styles';
import App from './App.vue';

// Match AstrBot's PurpleTheme palette; all layout uses Vuetify utilities.
const vuetify = createVuetify({
  components, directives,
  icons: { defaultSet: 'mdi', aliases, sets: { mdi } },
  locale: { locale: 'zhHans', messages: { zhHans } },
  theme: {
    defaultTheme: 'light',
    themes: {
      light: { colors: { primary: '#3c96ca', secondary: '#2f86bd', background: '#ffffff', surface: '#ffffff', error: '#f44336' } },
      dark: { dark: true, colors: { primary: '#5ba4d4', secondary: '#4a95c4', background: '#1a1a1a', surface: '#242424', 'on-background':'#e8eaed', 'on-surface':'#e8eaed', error: '#ff4d4f' } },
    },
  },
  defaults: {
    VBtn: { variant: 'tonal' },
    VTextField: { variant: 'outlined', density: 'comfortable' },
    VSelect: { variant: 'outlined', density: 'comfortable' },
    VAutocomplete: { variant: 'outlined', density: 'comfortable' },
    VCombobox: { variant: 'outlined', density: 'comfortable' },
    VCard: { variant: 'flat', border: true, rounded: 'lg' },
  },
});

const bridge = window.AstrBotPluginView;
if (bridge) {
  bridge.ready().then(context => {
    const setTheme = ctx => { vuetify.theme.global.name.value = ctx.isDark ? 'dark' : 'light'; };
    setTheme(context);
    const off = bridge.onContext(setTheme);
    window.addEventListener('beforeunload', off, { once: true });
    createApp(App).provide('bridge', bridge).use(vuetify).mount('#app');
  }).catch(error => { document.getElementById('app').textContent = error.message; });
} else {
  document.getElementById('app').textContent = '请从 AstrBot 控制面板打开 Humanization 视图';
}
