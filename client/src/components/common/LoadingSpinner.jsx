const LoadingSpinner = ({ size = 'md', text = 'Loading...', elapsedTime = null, step = null }) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8'
  };
  
  const formatTime = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };
  
  return (
    <div className="flex flex-col items-center justify-center gap-2">
      <div className="flex items-center gap-2">
        <div className={`${sizeClasses[size]} border-2 border-gray-200 border-t-red-700 rounded-full animate-spin`}></div>
        {text && <span className="text-gray-600">{text}</span>}
      </div>
      {(elapsedTime !== null || step) && (
        <div className="flex items-center gap-3 text-sm text-gray-500">
          {step && <span className="font-medium">{step}</span>}
          {elapsedTime !== null && elapsedTime > 0 && (
            <span className="tabular-nums">{formatTime(elapsedTime)} elapsed</span>
          )}
        </div>
      )}
    </div>
  );
};

export default LoadingSpinner;
