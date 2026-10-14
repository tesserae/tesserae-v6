// The scansion line under a verse on a result card (Latin and Greek meter).
// Moved out of SearchResults.jsx (cleaning job H4, 2026-10-13).
const ScansionLine = ({ scansion }) => {
  if (!scansion || !scansion.raw) return null;
  const meterAbbr = {
    'hexameter': 'Hx',
    'pentameter': 'P',
    'hendecasyllable': 'Hn',
    'elegiac': 'E'
  };
  return (
    <div className="flex items-center gap-1 mt-1">
      <span className="font-mono text-xs text-gray-500">{scansion.raw}</span>
      <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-gray-100 text-gray-600" title={scansion.meter}>
        {meterAbbr[scansion.meter] || scansion.meter?.charAt(0).toUpperCase() || '?'}
      </span>
    </div>
  );
};

export default ScansionLine;
