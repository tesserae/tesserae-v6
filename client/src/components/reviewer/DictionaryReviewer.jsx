/**
 * External reviewer page for the dictionary-review tool.
 * Mounted at /dictionary-review/:token. No admin login required; the token
 * in the URL authenticates the reviewer against the backend.
 *
 * The page is a self-contained app: it does NOT use the main site's header,
 * nav, or admin chrome. Only the reviewer's queue, votes, gamification UI,
 * and a small profile card.
 */
import { useState, useEffect, useCallback } from 'react';

const API_BASE = '/api/reviewer';

function ProgressBar({ done, total }) {
  if (!total) return null;
  const pct = Math.min(100, Math.round((done / total) * 100));
  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-gray-600 mb-1">
        <span>{done} of {total} reviewed</span>
        <span>{pct}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className="bg-red-700 h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function StatsCard({ name, stats, queueRemaining, totalPending }) {
  const totalDone = totalPending ? (totalPending - queueRemaining) : 0;
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
      <div className="flex flex-wrap items-baseline justify-between mb-3 gap-2">
        <h2 className="text-lg font-semibold">Hello, {name}</h2>
        <span className="text-sm text-gray-600">
          {stats?.streak_days >= 1 && (
            <span className="inline-flex items-center gap-1 mr-3">
              <span aria-hidden>🔥</span>
              <span>{stats.streak_days}-day streak</span>
            </span>
          )}
          Today: {stats?.today_count ?? 0}
        </span>
      </div>
      <ProgressBar done={totalDone} total={totalPending} />
      <div className="text-xs text-gray-500 mt-2">
        Your votes: {stats?.total_votes ?? 0} total
        {' '}({stats?.yes_votes ?? 0} confirmed, {stats?.no_votes ?? 0} rejected, {stats?.unsure_votes ?? 0} unsure)
      </div>
    </div>
  );
}

function JointProgressCard({ reviewers }) {
  if (!reviewers || reviewers.length < 2) return null;
  const max = Math.max(...reviewers.map(r => r.total_votes), 1);
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
      <h3 className="text-sm font-semibold mb-2 text-gray-700">Reviewer progress</h3>
      <div className="space-y-2">
        {reviewers.map((r, i) => {
          const pct = (r.total_votes / max) * 100;
          return (
            <div key={i}>
              <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                <span className={r.is_you ? 'font-semibold' : ''}>
                  {r.name}{r.is_you && ' (you)'}
                </span>
                <span>{r.total_votes}</span>
              </div>
              <div className="w-full bg-gray-100 rounded h-1.5">
                <div
                  className={r.is_you ? 'bg-red-700 h-1.5 rounded' : 'bg-amber-500 h-1.5 rounded'}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DisagreementBadge({ count, onClick }) {
  if (!count) return null;
  return (
    <button
      onClick={onClick}
      className="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded hover:bg-amber-200 mb-2"
    >
      {count} candidate{count === 1 ? '' : 's'} need adjudication
    </button>
  );
}

/**
 * Extract a single sentence around the lemma if the text is long. The Greek
 * corpus often stores whole paragraphs as one "line," which made the original
 * UI unreadable. We:
 *   1. If text is short (<=220 chars), return as-is.
 *   2. Find the lemma in the text (case-insensitive, accent-tolerant for Greek
 *      via Unicode normalization). Take the sentence containing the lemma,
 *      bounded by . ? ! · ; or paragraph break.
 *   3. If lemma not found, truncate to the first 200 chars + ellipsis.
 */
function trimToLemmaSentence(text, lemma) {
  if (!text) return '';
  if (text.length <= 220) return text;

  // Normalize for matching (strip accents, lowercase)
  const norm = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const tNorm = norm(text);
  const lNorm = norm(lemma || '');

  let lemmaIdx = -1;
  if (lNorm.length >= 3) {
    // Look for the lemma as a substring; the inflected form will usually start with the lemma
    // stem so this catches it even if the surface form differs slightly.
    const stem = lNorm.length > 6 ? lNorm.slice(0, 6) : lNorm;
    lemmaIdx = tNorm.indexOf(stem);
  }

  if (lemmaIdx === -1) {
    return text.slice(0, 200).trim() + '…';
  }

  // Find sentence boundaries around lemmaIdx. Greek sentence delimiters: . ; · (mid dot) and Coptic ⸫
  // Latin: . ! ?
  const delims = /[.?!;·]/g;
  let start = 0;
  let end = text.length;
  let m;
  // Walk delimiters to find the last one BEFORE lemmaIdx and the first one AFTER
  delims.lastIndex = 0;
  while ((m = delims.exec(text)) !== null) {
    if (m.index < lemmaIdx) start = m.index + 1;
    else if (m.index > lemmaIdx) { end = m.index + 1; break; }
  }
  // Pull the sentence, trim leading whitespace
  let snippet = text.slice(start, end).trim();
  // Cap excessive length even after sentence extraction
  if (snippet.length > 300) {
    // Try to keep the lemma roughly centered
    const localIdx = lemmaIdx - start;
    const windowStart = Math.max(0, localIdx - 120);
    const windowEnd = Math.min(snippet.length, localIdx + 180);
    snippet = (windowStart > 0 ? '…' : '') + snippet.slice(windowStart, windowEnd) + (windowEnd < snippet.length ? '…' : '');
  }
  return snippet;
}

function ExampleList({ examples, language }) {
  const filtered = (examples || []).filter(e => e.language === language);
  if (filtered.length === 0) {
    return <div className="text-xs text-gray-400 italic">No example sentences available.</div>;
  }
  return (
    <ul className="space-y-1.5">
      {filtered.map((e, i) => (
        <li key={i} className="text-sm text-gray-700">
          <span className="text-xs text-gray-500 mr-2 font-mono">{e.ref}</span>
          {trimToLemmaSentence(e.text, e.lemma_highlighted)}
        </li>
      ))}
    </ul>
  );
}

function AtlasStatCard({ label, value }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5 text-center">
      <div className="text-3xl font-semibold text-red-700">{value}</div>
      <div className="text-xs text-gray-600 uppercase tracking-wide mt-1">{label}</div>
    </div>
  );
}

function ConstellationSVG({ pairs }) {
  // Pairs is an array of recent_confirmations: {id, greek_lemma, latin_lemma, confirmed_by, latest_vote}.
  // We render Greek lemmas on the left, Latin lemmas on the right, with cubic Bezier curves connecting
  // confirmed pairs. The "constellation" metaphor: this is what the dictionary looks like as a network.
  if (!pairs || pairs.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center text-gray-500 text-sm italic">
        The constellation will appear here as Greek-Latin pairs are confirmed by the reviewers.
        Confirmed pairs are those that two or more reviewers have judged to be real translation equivalents.
      </div>
    );
  }

  const W = 900;
  const ROW_H = 26;
  const H = Math.max(360, pairs.length * ROW_H + 60);
  const PAD_TOP = 30;
  const LEFT_X = 110;
  const RIGHT_X = 790;

  // Deduplicate Greek and Latin lemmas, preserving order of first appearance.
  const seenG = new Set(), seenL = new Set();
  const greek = [], latin = [];
  pairs.forEach(p => {
    if (!seenG.has(p.greek_lemma)) { seenG.add(p.greek_lemma); greek.push(p.greek_lemma); }
    if (!seenL.has(p.latin_lemma)) { seenL.add(p.latin_lemma); latin.push(p.latin_lemma); }
  });
  const gPos = Object.fromEntries(greek.map((g, i) => [g, PAD_TOP + (i + 0.5) * (H - PAD_TOP * 2) / greek.length]));
  const lPos = Object.fromEntries(latin.map((l, i) => [l, PAD_TOP + (i + 0.5) * (H - PAD_TOP * 2) / latin.length]));

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Constellation (most recent {pairs.length} confirmations)
      </h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: '520px' }}>
        {pairs.map((p, i) => {
          const y1 = gPos[p.greek_lemma];
          const y2 = lPos[p.latin_lemma];
          const c1x = LEFT_X + (RIGHT_X - LEFT_X) * 0.35;
          const c2x = LEFT_X + (RIGHT_X - LEFT_X) * 0.65;
          return (
            <path
              key={i}
              d={`M ${LEFT_X} ${y1} C ${c1x} ${y1}, ${c2x} ${y2}, ${RIGHT_X} ${y2}`}
              fill="none"
              stroke="#b91c1c"
              strokeOpacity={0.25}
              strokeWidth={1.2}
            />
          );
        })}
        {greek.map(g => (
          <g key={`g-${g}`}>
            <circle cx={LEFT_X} cy={gPos[g]} r={3.5} fill="#b91c1c" />
            <text x={LEFT_X - 8} y={gPos[g]} textAnchor="end" dominantBaseline="middle" fontSize="13" fill="#111">
              {g}
            </text>
          </g>
        ))}
        {latin.map(l => (
          <g key={`l-${l}`}>
            <circle cx={RIGHT_X} cy={lPos[l]} r={3.5} fill="#b45309" />
            <text x={RIGHT_X + 8} y={lPos[l]} textAnchor="start" dominantBaseline="middle" fontSize="13" fill="#111">
              {l}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function RecentConfirmationsList({ confirmations }) {
  if (!confirmations || confirmations.length === 0) return null;
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Recent confirmations</h3>
      <ul className="text-sm divide-y divide-gray-100">
        {confirmations.map(c => (
          <li key={c.id} className="py-2 flex justify-between items-baseline">
            <span>
              <span className="font-medium">{c.greek_lemma}</span>
              <span className="mx-2 text-gray-400">↔</span>
              <span className="font-medium">{c.latin_lemma}</span>
            </span>
            <span className="text-xs text-gray-500">
              confirmed by {c.confirmed_by}
              {c.latest_vote && ' · ' + new Date(c.latest_vote).toLocaleDateString()}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ContributorBoard({ contributors }) {
  if (!contributors || contributors.length === 0) return null;
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Contributors</h3>
      <ul className="text-sm">
        {contributors.map((c, i) => (
          <li key={c.name} className="py-1.5 flex justify-between">
            <span>{c.name}</span>
            <span className="text-gray-500">
              {c.confirmations} confirmation{c.confirmations === 1 ? '' : 's'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AtlasView({ token }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    fetch(`${API_BASE}/${token}/atlas`)
      .then(r => r.json())
      .then(d => d.error ? setErr(d.error) : setData(d))
      .catch(e => setErr(e.message));
  }, [token]);

  if (err) return <div className="bg-white rounded-lg p-4 text-sm text-red-700">Failed to load atlas: {err}</div>;
  if (!data) return <div className="bg-white rounded-lg p-4 text-sm text-gray-500">Loading atlas...</div>;

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Greek-Latin Atlas</h2>
        <p className="text-sm text-gray-600">
          The map of confirmed Greek-Latin translation pairs as it grows.
          Each line is a pair that two or more reviewers have judged to be a real translation equivalent.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
        <AtlasStatCard label="Confirmed pairs" value={data.confirmed_count} />
        <AtlasStatCard label="Unique Greek lemmas" value={data.unique_greek_lemmas} />
        <AtlasStatCard label="Unique Latin lemmas" value={data.unique_latin_lemmas} />
      </div>

      <div className="mb-4">
        <ConstellationSVG pairs={data.recent_confirmations} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
        <RecentConfirmationsList confirmations={data.recent_confirmations} />
        <ContributorBoard contributors={data.contributors} />
      </div>
    </div>
  );
}

function CandidateCard({ candidate, onVote, voting }) {
  const [notes, setNotes] = useState('');
  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 px-4 py-3 mb-2">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 break-words flex-1">
          <span className="text-xl font-semibold text-gray-900">{candidate.greek_lemma}</span>
          <span className="mx-2 text-gray-400">↔</span>
          <span className="text-xl font-semibold text-gray-900">{candidate.latin_lemma}</span>
          {(candidate.greek_pos || candidate.shared_senses) && (
            <span className="ml-3 text-xs text-gray-500 whitespace-nowrap">
              {candidate.greek_pos && <span className="mr-2">{candidate.greek_pos}</span>}
              {candidate.shared_senses && <span className="italic">'{candidate.shared_senses}'</span>}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 whitespace-nowrap">
          <button
            disabled={voting}
            onClick={() => onVote(candidate.id, 'yes', notes)}
            className="bg-green-700 text-white text-sm px-3 py-1.5 rounded hover:bg-green-800 disabled:opacity-50"
            title="Confirm (J)"
          >
            ✓
          </button>
          <button
            disabled={voting}
            onClick={() => onVote(candidate.id, 'no', notes)}
            className="bg-red-700 text-white text-sm px-3 py-1.5 rounded hover:bg-red-800 disabled:opacity-50"
            title="Reject (L)"
          >
            ✗
          </button>
          <button
            disabled={voting}
            onClick={() => onVote(candidate.id, 'unsure', notes)}
            className="bg-gray-200 text-gray-800 text-sm px-3 py-1.5 rounded hover:bg-gray-300 disabled:opacity-50"
            title="Unsure (K)"
          >
            ?
          </button>
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="notes"
            className="w-32 text-xs border border-gray-200 rounded px-2 py-1.5"
          />
        </div>
      </div>
    </div>
  );
}

export default function DictionaryReviewer({ token }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [profile, setProfile] = useState(null);
  const [queue, setQueue] = useState([]);
  const [stats, setStats] = useState(null);
  const [queueRemaining, setQueueRemaining] = useState(0);
  const [totalPending, setTotalPending] = useState(0);
  const [joint, setJoint] = useState(null);
  const [disagreements, setDisagreements] = useState([]);
  const [voting, setVoting] = useState(false);
  const [voted, setVoted] = useState({});  // candidate_id -> 'yes'/'no'/'unsure'
  const [view, setView] = useState('review');  // 'review' or 'atlas'

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [profRes, queueRes, jointRes, disagreeRes] = await Promise.all([
        fetch(`${API_BASE}/${token}/profile`).then(r => r.json()),
        fetch(`${API_BASE}/${token}/queue?limit=10`).then(r => r.json()),
        fetch(`${API_BASE}/${token}/joint-progress`).then(r => r.json()),
        fetch(`${API_BASE}/${token}/disagreements`).then(r => r.json()),
      ]);
      if (profRes.error) throw new Error(profRes.error);
      setProfile(profRes);
      setStats(profRes.stats);
      setQueueRemaining(profRes.queue_remaining);
      setTotalPending(profRes.total_pending);
      setQueue(queueRes.candidates || []);
      setJoint(jointRes.reviewers || []);
      setDisagreements(disagreeRes.disagreements || []);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Keyboard shortcuts: J = Confirm, K = Unsure, L = Reject. Vim-style.
  // Operates on the first candidate currently in the queue.
  // Disabled when the user is typing in a text input/textarea (so notes
  // input does not trigger votes).
  useEffect(() => {
    const handler = (e) => {
      if (view !== 'review' || voting || queue.length === 0) return;
      const tag = (e.target?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target?.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      let vote = null;
      if (k === 'j') vote = 'yes';
      else if (k === 'k') vote = 'unsure';
      else if (k === 'l') vote = 'no';
      if (vote) {
        e.preventDefault();
        onVote(queue[0].id, vote, '');
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [view, voting, queue, token]);

  const onVote = async (candidateId, vote, notes) => {
    setVoting(true);
    try {
      const res = await fetch(`${API_BASE}/${token}/vote/${candidateId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vote, notes }),
      }).then(r => r.json());
      if (res.error) throw new Error(res.error);
      setStats(res.stats);
      setQueueRemaining(res.queue_remaining);
      setVoted(v => ({ ...v, [candidateId]: vote }));
      // Remove this candidate from the queue and reload if queue runs low
      setQueue(q => {
        const next = q.filter(c => c.id !== candidateId);
        if (next.length < 3) {
          // Top up by reloading the queue (preserves other state)
          fetch(`${API_BASE}/${token}/queue?limit=10`)
            .then(r => r.json())
            .then(d => setQueue(d.candidates || []));
        }
        return next;
      });
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setVoting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white border border-red-300 rounded p-6 max-w-md">
          <h2 className="text-lg font-semibold text-red-700 mb-2">Error</h2>
          <p className="text-sm text-gray-700">{error}</p>
          <p className="text-xs text-gray-500 mt-3">
            If the token is invalid or has expired, please contact Neil Coffee for a new link.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-6">
      <div className="max-w-4xl mx-auto px-4">
        <div className="mb-4">
          <h1 className="text-xl font-semibold text-gray-900">
            Tesserae V6 — Greek-Latin Dictionary Review
          </h1>
          <p className="text-sm text-gray-600">
            Confirm or reject candidate Greek-Latin lemma pairs. Your judgments
            build the dictionary that powers V6's cross-lingual intertext search.
          </p>
        </div>

        <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
          <div className="inline-flex rounded-lg border border-gray-200 bg-white overflow-hidden">
            <button
              onClick={() => setView('review')}
              className={`px-4 py-2 text-sm font-medium ${view === 'review' ? 'bg-red-700 text-white' : 'text-gray-700 hover:bg-gray-50'}`}
            >
              Review queue
            </button>
            <button
              onClick={() => setView('atlas')}
              className={`px-4 py-2 text-sm font-medium border-l border-gray-200 ${view === 'atlas' ? 'bg-red-700 text-white' : 'text-gray-700 hover:bg-gray-50'}`}
            >
              Atlas
            </button>
          </div>
          {view === 'review' && (
            <span className="text-xs text-gray-500">
              Shortcuts: <kbd className="px-1.5 py-0.5 bg-gray-100 border border-gray-300 rounded mx-0.5">J</kbd> confirm
              <kbd className="px-1.5 py-0.5 bg-gray-100 border border-gray-300 rounded mx-0.5">K</kbd> unsure
              <kbd className="px-1.5 py-0.5 bg-gray-100 border border-gray-300 rounded mx-0.5">L</kbd> reject
            </span>
          )}
        </div>

        {view === 'atlas' ? (
          <AtlasView token={token} />
        ) : (
        <>
        <StatsCard
          name={profile?.name}
          stats={stats}
          queueRemaining={queueRemaining}
          totalPending={totalPending}
        />

        <JointProgressCard reviewers={joint} />

        {disagreements.length > 0 && (
          <DisagreementBadge
            count={disagreements.length}
            onClick={() => alert(
              'Candidates where you and another reviewer disagreed:\n\n' +
              disagreements.slice(0, 10).map(d =>
                `${d.greek_lemma} ↔ ${d.latin_lemma}  (you: ${d.my_vote}, other: ${d.other_votes})`
              ).join('\n')
            )}
          />
        )}

        {queue.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              No more candidates in your queue
            </h2>
            <p className="text-sm text-gray-600">
              You've reviewed everything available. New candidates will appear here as they're queued.
            </p>
          </div>
        ) : (
          queue.map(c => (
            <CandidateCard
              key={c.id}
              candidate={c}
              onVote={onVote}
              voting={voting}
            />
          ))
        )}
        </>
        )}

        <div className="text-xs text-gray-400 text-center mt-6">
          Tesserae V6 · University at Buffalo · Coffee &amp; collaborators
        </div>
      </div>
    </div>
  );
}
