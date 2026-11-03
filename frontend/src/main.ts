import { t } from './i18n';
// @ts-ignore CSS imports are handled by the bundler.
import './style.css';

export function renderApp(rootElement: HTMLElement): void {
  const heading = document.createElement('h1');
  heading.textContent = t('greeting');
  rootElement.replaceChildren(heading);
}

const appContainer = document.querySelector<HTMLElement>('#app');
if (appContainer) {
  renderApp(appContainer);
}

