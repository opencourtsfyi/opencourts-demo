import { describe, it, expect, beforeEach } from 'vitest';
import { renderApp } from '../src/main';
import { t } from '../src/i18n';

describe('renderApp', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="app"></div>';
  });

  it('renders "Hello, World" inside the root element', () => {
    const root = document.getElementById('app') as HTMLElement;
    renderApp(root);

    const heading = root.querySelector('h1');
    expect(heading).not.toBeNull();
    expect(heading?.textContent).toBe('Hello, World');
  });

  it('uses the translation key for the greeting', () => {
    expect(t('greeting')).toBe('Hello, World');
  });
});

