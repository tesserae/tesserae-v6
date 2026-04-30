import { LANG_NAMES } from '../adminConstants';

export default function AnalyticsTab({ analytics }) {
  return (
    <div className="space-y-6">
      <h3 className="font-medium text-gray-900">User Analytics</h3>
      {analytics ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-blue-50 p-4 rounded">
              <div className="text-sm text-gray-600">Total Searches</div>
              <div className="text-2xl font-bold text-gray-900">{(analytics.total_searches || 0).toLocaleString()}</div>
            </div>
            <div className="bg-amber-50 p-4 rounded">
              <div className="text-sm text-gray-600">Searches Today</div>
              <div className="text-2xl font-bold text-gray-900">
                {/* FIX: use analytics.searches_today — backend sends it as a top-level field,
                    not inside per_day. The old per_day?.find() always returned 0. */}
                {analytics.searches_today ?? 0}
              </div>
            </div>
            <div className="bg-amber-50 p-4 rounded">
              <div className="text-sm text-gray-600">Unique Users</div>
              <div className="text-2xl font-bold text-gray-900">{analytics.unique_users ?? 0}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Searches by Type</h4>
              <div className="bg-gray-50 rounded p-3 space-y-2">
                {analytics.by_type?.length > 0
                  ? analytics.by_type.map(item => (
                    <div key={item.type} className="flex justify-between text-sm">
                      <span className="text-gray-600">{item.type}</span>
                      <span className="font-medium">{item.count}</span>
                    </div>
                  ))
                  : <p className="text-gray-500 text-sm">No data</p>}
              </div>
            </div>
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Searches by Language</h4>
              <div className="bg-gray-50 rounded p-3 space-y-2">
                {analytics.by_language?.length > 0
                  ? analytics.by_language.map(item => (
                    <div key={item.language} className="flex justify-between text-sm">
                      <span className="text-gray-600">{LANG_NAMES[item.language] || item.language}</span>
                      <span className="font-medium">{item.count}</span>
                    </div>
                  ))
                  : <p className="text-gray-500 text-sm">No data</p>}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Top Source Texts</h4>
              <div className="bg-gray-50 rounded p-3 space-y-2 max-h-48 overflow-y-auto">
                {analytics.top_sources?.length > 0
                  ? analytics.top_sources.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-gray-600 truncate max-w-[200px]" title={item.text}>{item.text}</span>
                      <span className="font-medium">{item.count}</span>
                    </div>
                  ))
                  : <p className="text-gray-500 text-sm">No data</p>}
              </div>
            </div>
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Top Target Texts</h4>
              <div className="bg-gray-50 rounded p-3 space-y-2 max-h-48 overflow-y-auto">
                {analytics.top_targets?.length > 0
                  ? analytics.top_targets.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-gray-600 truncate max-w-[200px]" title={item.text}>{item.text}</span>
                      <span className="font-medium">{item.count}</span>
                    </div>
                  ))
                  : <p className="text-gray-500 text-sm">No data</p>}
              </div>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Daily Search Activity (Last 30 Days)</h4>
            <div className="bg-gray-50 rounded p-3 max-h-48 overflow-y-auto">
              {analytics.per_day?.length > 0 ? (
                <div className="space-y-1">
                  {analytics.per_day.slice(0, 14).map(item => (
                    <div key={item.date} className="flex justify-between text-sm">
                      <span className="text-gray-600">{item.date}</span>
                      <span className="font-medium">{item.count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No recent searches</p>
              )}
            </div>
          </div>



          <div className="border-t pt-6">
            <h4 className="text-sm font-medium text-gray-700 mb-4">Geographic Distribution</h4>

            {(analytics.top_cities?.length > 0 || analytics.top_countries?.length > 0) ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                  <div>
                    <h5 className="text-xs font-medium text-gray-500 uppercase mb-2">Top Countries</h5>
                    <div className="bg-gray-50 rounded p-3 space-y-2">
                      {analytics.top_countries?.length > 0
                        ? analytics.top_countries.map((item, i) => (
                          <div key={i} className="flex justify-between text-sm">
                            <span className="text-gray-600">{item.country}</span>
                            <span className="font-medium">{item.count}</span>
                          </div>
                        ))
                        : <p className="text-gray-500 text-sm">No data</p>}
                    </div>
                  </div>
                  <div>
                    <h5 className="text-xs font-medium text-gray-500 uppercase mb-2">Top Cities</h5>
                    <div className="bg-gray-50 rounded p-3 space-y-2 max-h-48 overflow-y-auto">
                      {analytics.top_cities?.length > 0
                        ? analytics.top_cities.map((item, i) => (
                          <div key={i} className="flex justify-between text-sm">
                            <span className="text-gray-600">{item.city}{item.country ? `, ${item.country}` : ''}</span>
                            <span className="font-medium">{item.count}</span>
                          </div>
                        ))
                        : <p className="text-gray-500 text-sm">No data</p>}
                    </div>
                  </div>
                </div>

                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-100">
                  <h5 className="text-sm font-medium text-gray-700 mb-3">User Distribution Map</h5>
                  <div className="relative bg-white rounded p-4 min-h-[200px] flex flex-col items-center justify-center">
                    {analytics.top_cities?.length > 0 ? (
                      <div className="w-full">
                        <div className="flex flex-wrap gap-2 justify-center">
                          {analytics.top_cities.slice(0, 10).map((city, idx) => {
                            const maxCount = Math.max(...analytics.top_cities.map(c => c.count));
                            const size = Math.max(24, Math.min(80, (city.count / maxCount) * 80));
                            const opacity = 0.4 + (city.count / maxCount) * 0.6;
                            return (
                              <div
                                key={idx}
                                className="flex flex-col items-center group cursor-pointer"
                                title={`${city.city}, ${city.country}: ${city.count} searches`}
                              >
                                <div
                                  className="rounded-full bg-red-500 flex items-center justify-center text-white text-xs font-bold shadow-lg transition-transform hover:scale-110"
                                  style={{ width: size, height: size, opacity: opacity }}
                                >
                                  {city.count}
                                </div>
                                <span className="text-xs text-gray-600 mt-1 max-w-[60px] truncate text-center">
                                  {city.city}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                        <p className="text-xs text-gray-500 text-center mt-4">
                          Circle size indicates relative search volume. Hover for details.
                        </p>
                      </div>
                    ) : (
                      <p className="text-gray-500 text-sm">No geographic data available yet</p>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-gray-50 rounded p-4 text-center">
                <p className="text-gray-500 text-sm">No geographic data available yet.</p>
                <p className="text-gray-400 text-xs mt-1">User locations are tracked via IP geolocation when searches are performed.</p>
              </div>
            )}
          </div>
        </>
      ) : (
        <p className="text-gray-500 text-sm">Loading analytics...</p>
      )}
    </div>
  );
}
