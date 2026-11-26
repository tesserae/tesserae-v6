/**
 * The site's pages as a visitor sees them, rendered to HTML for Tessa.
 *
 * Tessa answers questions about the site from the Help page and four other
 * pages (backend/assistant/site_help.py). Until 25 November 2026 she read
 * their JSX source, so a branch that never renders reached her as fact: the
 * Help page kept a paragraph about an "official Tesserae GPT" behind a switch
 * that was never turned on, and she told a reader to use it. Rendering the
 * pages the way React does, with every Help section opened in turn, gives her
 * only what a visitor can see.
 *
 * `npm run render:tessa` writes the HTML to backend/assistant/rendered_pages/,
 * which is committed, so a deploy carries it; renderedPages.test.jsx fails
 * when the committed copy is behind the pages. Effects do not run under
 * renderToStaticMarkup, so anything a page fetches after it mounts renders as
 * its loading state, and nothing here touches the network. The Scholarship
 * sources page is left out for that reason (its whole content is fetched), and
 * site_help.py keeps reading its source.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToStaticMarkup } from 'react-dom/server';
import HelpPage from '../components/pages/HelpPage';
import AboutPage from '../components/pages/AboutPage';
import DownloadsPage from '../components/pages/DownloadsPage';
import PrivacyPage from '../components/pages/PrivacyPage';

const here = path.dirname(fileURLToPath(import.meta.url));
export const HELP_SOURCE = path.join(here, '..', 'components', 'pages', 'HelpPage.jsx');
export const OUT_DIR = path.join(here, '..', '..', '..', 'backend', 'assistant', 'rendered_pages');

/** Every Help section id, in the order the page's source tests for them. */
export function helpSectionIds() {
  const src = fs.readFileSync(HELP_SOURCE, 'utf8');
  const ids = [];
  for (const m of src.matchAll(/activeSection === '([a-z0-9-]+)'/g)) {
    if (!ids.includes(m[1])) ids.push(m[1]);
  }
  return ids;
}

/** File name to HTML, for the pages Tessa reads. */
export function renderPagesForTessa() {
  const help = helpSectionIds()
    .map((id) => `<!-- help section ${id} -->\n${renderToStaticMarkup(<HelpPage initialSection={id} />)}`)
    .join('\n');
  return {
    'help.html': help,
    'about.html': renderToStaticMarkup(<AboutPage onNavigate={() => {}} />),
    'downloads.html': renderToStaticMarkup(<DownloadsPage />),
    'privacy.html': renderToStaticMarkup(<PrivacyPage />),
  };
}
