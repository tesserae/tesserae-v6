// Reading and writing the search a page address carries (moved out of App.jsx,
// cleaning job H4, 2026-10-13, code unchanged).

export const parseSearchParams = () => {
  const params = new URLSearchParams(window.location.search);
  return {
    source: params.get('source') || '',
    target: params.get('target') || '',
    source_author: params.get('source_author') || '',
    target_author: params.get('target_author') || '',
    lang: params.get('lang') || params.get('language') || '',
    tab: params.get('tab') || '',
    match_type: params.get('match_type') || '',
    min_matches: params.get('min_matches') ? parseInt(params.get('min_matches')) : null
  };
};

export const buildShareableUrl = (sourceText, targetText, sourceAuthor, targetAuthor, language, settings) => {
  const params = new URLSearchParams();
  if (sourceText) params.set('source', sourceText);
  if (targetText) params.set('target', targetText);
  if (sourceAuthor) params.set('source_author', sourceAuthor);
  if (targetAuthor) params.set('target_author', targetAuthor);
  if (language) params.set('lang', language);
  if (settings.match_type) params.set('match_type', settings.match_type);
  if (settings.min_matches) params.set('min_matches', settings.min_matches);
  return `${window.location.origin}/?${params.toString()}`;
};
