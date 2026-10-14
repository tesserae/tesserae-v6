import { formatRunningTime } from '../../utils/formatting';

// The progress banner above a streaming fusion search, with the Pause/Resume
// button. Moved out of SearchResults.jsx (cleaning job H4, 2026-10-13).
const FusionProgressBanner = ({ fusionProgress, pauseUpdates, progressText, elapsedTime, onPauseToggle }) => {
  const fusionBatchTotal = fusionProgress?.batchTotal || fusionProgress?.channelsTotal || 0;
  const fusionBatchIndex = fusionProgress?.batchIndex || fusionProgress?.channelsDone?.length || 0;
  const fusionBatchPercent = fusionBatchTotal > 0
    ? Math.min(100, Math.round((fusionBatchIndex / fusionBatchTotal) * 100))
    : 0;
  const fusionPhaseLabel = fusionProgress?.phase === 'window' ? 'Window pass' : 'Line pass';
  return (
    <div className={`${pauseUpdates ? 'bg-amber-50 border-amber-200' : 'bg-blue-50 border-blue-200'} border rounded-lg p-3`}>
      <div className="flex items-center gap-3">
        {!pauseUpdates && (
          <div className="w-5 h-5 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className={`text-sm font-medium ${pauseUpdates ? 'text-amber-800' : 'text-blue-800'}`}>
            {pauseUpdates ? 'Display paused, search continues in background' : (progressText || 'Searching...')}
          </div>
          <div className={`mt-1 text-xs ${pauseUpdates ? 'text-amber-600' : 'text-blue-600'}`}>
            {fusionPhaseLabel}
            {fusionBatchTotal > 0 && ` | batch ${fusionBatchIndex} of ${fusionBatchTotal}`}
            {fusionProgress.currentChannel && ` | ${fusionProgress.currentChannel}`}
            {fusionProgress.totalMatches > 0 && ` | ${fusionProgress.totalMatches.toLocaleString()} candidates`}
            {fusionProgress.resultCount > 0 && ` | showing ${fusionProgress.resultCount.toLocaleString()}`}
          </div>
        </div>
        <button
          onClick={onPauseToggle}
          className={`text-xs px-3 py-1 rounded font-medium flex-shrink-0 ${
            pauseUpdates
              ? 'bg-amber-600 text-white hover:bg-amber-700'
              : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
          }`}
        >
          {pauseUpdates ? 'Resume' : 'Pause'}
        </button>
        <span className={`text-xs ${pauseUpdates ? 'text-amber-500' : 'text-blue-500'} tabular-nums flex-shrink-0`}>
          {elapsedTime > 0 && formatRunningTime(elapsedTime)}
        </span>
      </div>
      {fusionBatchTotal > 0 && (
        <div className={`mt-3 h-1.5 rounded-full overflow-hidden ${pauseUpdates ? 'bg-amber-100' : 'bg-blue-100'}`}>
          <div
            className={`h-full transition-all duration-300 ${pauseUpdates ? 'bg-amber-500' : 'bg-blue-600'}`}
            style={{ width: `${fusionBatchPercent}%` }}
          />
        </div>
      )}
    </div>
  );
};

export default FusionProgressBanner;
