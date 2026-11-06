// The notice shown while a comparison waits for the server to start it.
// `message` is the plain sentence the server sends (place in line or memory,
// time waited so far, how long a request is held).
const QueuedNotice = ({ message }) => (
  <div
    role="status"
    className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4 text-center max-w-md"
  >
    <div className="text-amber-800 font-medium mb-1">Waiting to start</div>
    <div className="text-amber-700 text-sm">{message}</div>
    <div className="text-amber-600 text-xs mt-2">
      Your comparison starts by itself when there is room. You can cancel it below.
    </div>
  </div>
);

export default QueuedNotice;
