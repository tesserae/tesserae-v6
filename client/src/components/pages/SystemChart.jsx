import React from 'react';

// The machinery of Tesserae as it stands, drawn as a block schematic for
// the Help page's "How the system is built" topic. Static SVG, no state.
// Solid lines are paths taken during a request; dashed lines are jobs that
// run once or on a schedule. Update the figures and parts when one changes
// (the window count, the models, a new service).

const INK = '#1c1917';
const BODY = '#44403c';
const MUTED = '#79716b';
const RULE = '#a8a29e';
const PANEL = '#f7f5f3';
const CARD = '#ffffff';
const ACCENT = '#b91c1c';

const SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';

function Box({ x, y, w, h, title, lines = [], note }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} fill={CARD} stroke={INK} strokeWidth="1" />
      <text x={x + 10} y={y + 17} fontSize="12" fontWeight="600" fill={INK}>{title}</text>
      {lines.map((t, i) => (
        <text key={i} x={x + 10} y={y + 33 + i * 14} fontSize="11" fill={BODY}>{t}</text>
      ))}
      {note && (
        <text x={x + w - 8} y={y + 17} fontSize="10" fill={MUTED} textAnchor="end">{note}</text>
      )}
    </g>
  );
}

function Panel({ x, y, w, h, label }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} fill={PANEL} stroke={RULE} strokeWidth="1" />
      <text x={x + 10} y={y - 6} fontSize="10" fontWeight="600" letterSpacing="1.4" fill={MUTED}>
        {label.toUpperCase()}
      </text>
    </g>
  );
}

// A straight or elbowed connector. `d` is an SVG path; the arrowhead sits at
// its end. Dashed connectors are jobs, solid ones are request paths.
function Line({ d, dashed = false, accent = false, label, lx, ly, anchor = 'middle' }) {
  const stroke = accent ? ACCENT : INK;
  return (
    <g>
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth="1"
        strokeDasharray={dashed ? '4 3' : undefined}
        markerEnd={accent ? 'url(#arrow-accent)' : 'url(#arrow-ink)'}
      />
      {label && (
        <text x={lx} y={ly} fontSize="10" fill={accent ? ACCENT : MUTED} textAnchor={anchor}>{label}</text>
      )}
    </g>
  );
}

export default function SystemChart() {
  return (
    <div className="overflow-x-auto">
      <svg
        viewBox="0 0 960 760"
        width="100%"
        style={{ minWidth: 720, display: 'block', fontFamily: SANS }}
        role="img"
        aria-label="A schematic of the parts of Tesserae: the browser and AI assistants on the left, the server with its application, data and two helper services in the middle, the BullsAI gateway and compute on the right, and the recurrent and one-off jobs below."
      >
        <defs>
          <marker id="arrow-ink" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={INK} />
          </marker>
          <marker id="arrow-accent" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={ACCENT} />
          </marker>
        </defs>

        {/* Column 1: the people */}
        <text x="30" y="34" fontSize="10" fontWeight="600" letterSpacing="1.4" fill={MUTED}>YOU</text>
        <Box x={20} y={50} w={190} h={54} title="Your browser" lines={['the Tesserae page']} />
        <Box x={20} y={150} w={190} h={54} title="Your AI assistant" lines={['through the connector']} />

        {/* Column 2: the server */}
        <Panel x={250} y={50} w={430} h={470} label="The server, at the University at Buffalo" />
        <Box
          x={270} y={70} w={390} h={92}
          title="Web application"
          note="three workers"
          lines={[
            'phrase, line, rare-word and cross-language search',
            'Reader, Similar Passages, Theme Search, Tessa',
            'Repository, uploads, downloads, the connector',
          ]}
        />
        <Box x={270} y={196} w={390} h={190} title="Data on disk" note="read on request" />
        <g fontSize="11" fill={BODY}>
          <text x="282" y="229">texts in .tess form</text>
          <text x="282" y="245">lemma caches, one per text</text>
          <text x="282" y="261">inverted index, lemma to lines</text>
          <text x="282" y="277">word tables: frequencies, bigrams,</text>
          <text x="282" y="291">formula counts</text>
          <text x="282" y="307">dictionaries: synonyms, cross-</text>
          <text x="282" y="321">language word pairs</text>
          <text x="282" y="337">line vectors for the semantic channel</text>
          <text x="282" y="353">connections map, reuse table</text>
          <text x="282" y="369">database: accounts, Repository</text>
          <text x="478" y="229" fontWeight="600" fill={INK}>Passage index</text>
          <text x="478" y="245">one window per passage, with its</text>
          <text x="478" y="259">text, a description and a vector</text>
          <text x="478" y="285" fontWeight="600" fill={INK}>Work descriptions</text>
          <text x="478" y="301">one blurb per work</text>
          <text x="478" y="327" fontWeight="600" fill={INK}>Languages</text>
          <text x="478" y="343">Latin, Greek, English,</text>
          <text x="478" y="357">Coptic, Hebrew</text>
        </g>
        <Box
          x={270} y={420} w={185} h={80}
          title="Query encoder"
          lines={['turns a Theme Search query', 'into a vector', 'multilingual-e5-large']}
        />
        <Box
          x={475} y={420} w={185} h={80}
          title="Reader"
          lines={['re-ranks Theme Search results', 'a trained MiniLM cross-encoder']}
        />

        {/* Column 3: BullsAI */}
        <Panel x={720} y={50} w={220} h={470} label="BullsAI, the campus AI platform" />
        <Box
          x={735} y={70} w={190} h={134}
          title="Gateway"
          lines={[
            'hosted open models, one address',
            '',
            'Tessa, each request (Qwen 3.8)',
            'passage descriptions, one pass',
            'over the corpus (GLM 5.3 Flash)',
            'work descriptions, one pass',
          ]}
        />
        <Box
          x={735} y={290} w={190} h={176}
          title="Compute"
          lines={[
            'GPUs allotted job by job, from a',
            'command-line tool on the server',
            '',
            'one-off jobs:',
            'vectors for newly added texts',
            'training the Reader re-ranker',
            'whole-corpus comparisons',
            'description batches too large',
            'for the gateway',
          ]}
        />

        {/* Request paths (solid). Every search reads the data; only Theme
            Search also goes through the two helper services. */}
        <Line d="M210 77 H270" accent />
        <Line d="M210 177 H240 V116 H270" accent />
        <Line d="M465 162 V196" accent label="every search" lx={472} ly={183} anchor="start" />
        <Line d="M270 116 H258 V460 H270" accent />
        <Line d="M258 460 V510 H567 V500" accent />
        <text x="270" y="409" fontSize="10" fill={ACCENT}>Theme Search only: the query is encoded, the results re-ranked</text>
        <Line d="M660 100 H735" accent label="Tessa" lx={697} ly={113} />

        {/* Jobs (dashed) */}
        <Panel x={20} y={570} w={920} h={160} label="Jobs" />
        <g fontSize="11" fill={BODY}>
          <text x="36" y="596" fontWeight="600" fill={INK}>Recurrent</text>
          <text x="36" y="614">each request: a results cache, and Tessa's</text>
          <text x="36" y="628">second pass checking dates and attributions</text>
          <text x="36" y="648">each code change: GitHub runs the tests, the</text>
          <text x="36" y="662">build and an automated review. Production</text>
          <text x="36" y="676">pulls the merged code</text>
          <text x="36" y="696">weekly: a review of Tessa's recorded exchanges.</text>
          <text x="36" y="710">Failures become graded test questions</text>

          <text x="356" y="596" fontWeight="600" fill={INK}>One-off, when the corpus changes</text>
          <text x="356" y="614">convert the text to .tess, build its lemma cache,</text>
          <text x="356" y="628">add it to the inverted index and the word tables</text>
          <text x="356" y="648">cut it into passage windows, describe them</text>
          <text x="356" y="662">(gateway), encode them, append to the index</text>
          <text x="356" y="682">rebuild the connections map and reuse table,</text>
          <text x="356" y="696">write the work's blurb</text>

          <text x="676" y="596" fontWeight="600" fill={INK}>One-off, on BullsAI compute</text>
          <text x="676" y="614">vectors for whole corpora</text>
          <text x="676" y="628">re-ranker training</text>
          <text x="676" y="642">whole-corpus comparisons</text>
        </g>
        {/* Jobs (dashed), each column to the part it works on: the corpus
            jobs rebuild the data on disk and send their describing to the
            gateway; the GPU jobs run on the compute. */}
        <Line d="M560 570 V540 H668 V300 H660" dashed label="corpus jobs rebuild the data" lx={552} ly={549} anchor="end" />
        <Line d="M640 570 V552 H930 V140 H925" dashed label="describing batches go to the gateway" lx={866} ly={546} anchor="end" />
        <Line d="M880 570 V466" dashed label="GPU jobs" lx={874} ly={566} anchor="end" />

        {/* Legend */}
        <g fontSize="10" fill={MUTED}>
          <path d="M20 750 H50" stroke={ACCENT} strokeWidth="1" />
          <text x="56" y="753">during a request</text>
          <path d="M150 750 H180" stroke={INK} strokeWidth="1" strokeDasharray="4 3" />
          <text x="186" y="753">a job, run once or on a schedule</text>
          <text x="940" y="753" textAnchor="end">as of October 2026</text>
        </g>
      </svg>
    </div>
  );
}
