import { useState } from 'react';
import { LoadingSpinner } from '../common';

// The Translation tab's machine translation on request, for a passage with no
// aligned human translation. The route (backend/machine_translation.py) asks
// the free campus model; the figures in the note come from the route's answer.

const SHORT_NAMES = { grc: 'Greek' };

function kindPhrase(kind) {
  const name = SHORT_NAMES[kind.language] || kind.language_name;
  return `${name} ${kind.form}`;
}

function Note({ result }) {
  const [open, setOpen] = useState(false);
  const { kind, reliability: rel, model } = result;
  const phrase = kindPhrase(kind);
  const source = SHORT_NAMES[kind.language] || kind.language_name;
  return (
    <div className="mb-2">
      <p className="text-[11px] text-gray-500 leading-snug">
        {`Machine translation by ${model}, unreviewed. `}
        {rel
          ? `In our test it was fully right for ${rel.right} of ${rel.of} ${phrase} passages. `
          : `We did not test it on ${source} ${kind.form}. `}
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
                className="text-red-700 underline">
          What this means
        </button>
      </p>
      {open && (
        <p className="text-[11px] text-gray-600 leading-snug mt-1" data-testid="mt-disclosure">
          {'In the test, passages were graded blind: fully right meant a reader who knows no '}
          {`${source} would understand the passage correctly, nearly right meant one wrong word, name, number or relation, and wrong meant the main sense was lost or a clause was invented. `}
          {rel && `Of ${rel.of} ${phrase} passages, ${rel.right} were fully right, ${rel.nearly} nearly right and ${rel.wrong} wrong. `}
          {'The usual faults are a wrong word, a wrong name or number, or a relation turned around, so trust the gist and check any detail that matters. '}
          {'Pasting the passage into a commercial model gave a markedly better result in the same test (fully right for 106 and 111 of the same 121 passages). You can paste this passage into a commercial model too for a likely better result. The source text can be selected and copied.'}
        </p>
      )}
    </div>
  );
}

export default function MachineTranslation({ work, refs, language }) {
  const [state, setState] = useState({ phase: 'idle' });

  const ask = () => {
    setState({ phase: 'loading' });
    const q = `work=${encodeURIComponent(work)}&refs=${encodeURIComponent(refs.join('|'))}&language=${encodeURIComponent(language)}`;
    fetch(`/api/translation/machine?${q}`)
      .then((r) => r.json().catch(() => ({})).then((d) => ({ status: r.status, d })))
      .then(({ status, d }) => {
        if (status === 200 && d.available) setState({ phase: 'done', result: d });
        else setState({ phase: 'error', message: d.reason || 'The machine translation could not be made just now.' });
      })
      .catch(() => setState({ phase: 'error', message: 'The machine translation could not be made just now.' }));
  };

  if (state.phase === 'done') {
    const { result } = state;
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-3 mt-2">
        <Note result={result} />
        {result.lines.map((line, i) => (
          <p key={i} className="text-sm text-gray-800 leading-relaxed">{line}</p>
        ))}
      </div>
    );
  }
  return (
    <div className="mt-2">
      {state.phase === 'loading'
        ? <LoadingSpinner />
        : (
          <button type="button" onClick={ask}
                  className="text-sm px-3 py-1.5 rounded border border-gray-300 text-gray-800 hover:bg-gray-50">
            Translate by machine
          </button>
        )}
      {state.phase === 'error' && <p className="text-sm text-gray-600 mt-2">{state.message}</p>}
    </div>
  );
}
