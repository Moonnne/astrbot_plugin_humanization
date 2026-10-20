import { createApp } from 'vue';
import { createVuetify } from 'vuetify';
import { VApp } from 'vuetify/components/VApp';
import { VAlert } from 'vuetify/components/VAlert';
import { VAutocomplete } from 'vuetify/components/VAutocomplete';
import { VBtn } from 'vuetify/components/VBtn';
import { VCard, VCardActions, VCardText, VCardTitle } from 'vuetify/components/VCard';
import { VChip } from 'vuetify/components/VChip';
import { VCombobox } from 'vuetify/components/VCombobox';
import { VDataTableServer } from 'vuetify/components/VDataTable';
import { VDialog } from 'vuetify/components/VDialog';
import { VDivider } from 'vuetify/components/VDivider';
import { VIcon } from 'vuetify/components/VIcon';
import { VMain } from 'vuetify/components/VMain';
import { VProgressLinear } from 'vuetify/components/VProgressLinear';
import { VContainer, VRow, VCol, VSpacer } from 'vuetify/components/VGrid';
import { VSelect } from 'vuetify/components/VSelect';
import { VSlider } from 'vuetify/components/VSlider';
import { VSnackbar } from 'vuetify/components/VSnackbar';
import { VSwitch } from 'vuetify/components/VSwitch';
import { VTable } from 'vuetify/components/VTable';
import { VTextField } from 'vuetify/components/VTextField';
import { VTextarea } from 'vuetify/components/VTextarea';
import { VExpandXTransition } from 'vuetify/components/transitions';
import { aliases, mdi } from 'vuetify/iconsets/mdi-svg';
import { zhHans } from 'vuetify/locale';
import 'vuetify/styles';
import App from './App.vue';

// Match AstrBot's PurpleTheme palette; all layout uses Vuetify utilities.
const vuetify = createVuetify({
  components: {
    VApp, VAlert, VAutocomplete, VBtn, VCard, VCardActions, VCardText, VCardTitle,
    VChip, VCombobox, VDataTableServer, VDialog, VDivider, VIcon, VMain,
    VProgressLinear, VContainer, VRow, VCol, VSpacer, VSelect, VSlider,
    VSnackbar, VSwitch, VTable, VTextField, VTextarea, VExpandXTransition,
  },
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
