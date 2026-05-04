import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, LineChart, Line, Legend, AreaChart, Area
} from 'recharts';
import { 
  Download, Users, Search, Activity, Globe, Clock, 
  MapPin, Filter, Database, FileText
} from 'lucide-react';

const TESSERAE_RED = '#b91c1c';
const TESSERAE_GOLD = '#d97706';
const TESSERAE_GRAY = '#4b5563';
const COLORS = [TESSERAE_RED, '#dc2626', '#ef4444', '#f87171', TESSERAE_GOLD, '#fbbf24'];

const AnalyticsTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const response = await fetch('/api/admin/analytics', {
          headers: { 'Accept': 'application/json' }
        });
        const result = await response.json();
        setData(result);
      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 5000);
    return () => clearInterval(interval);
  }, []);

  const exportToCSV = () => {
    if (!data) return;
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Metric,Value\n";
    csvContent += `Total Searches,${data.total_searches}\n`;
    csvContent += `Distinct Queries,${data.distinct_searches}\n`;
    csvContent += `Unique Visitors,${data.unique_users}\n`;
    csvContent += `Searches Today,${data.searches_today}\n`;
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `tesserae_analytics_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#b91c1c]"></div>
    </div>
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex justify-between items-center bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Search Analytics</h2>
          <p className="text-gray-500">Real-time usage insights and geographic distribution</p>
        </div>
        <button 
          onClick={exportToCSV}
          className="flex items-center gap-2 px-4 py-2 bg-[#b91c1c] text-white rounded-lg hover:bg-[#991b1b] transition-colors font-medium shadow-sm"
        >
          <Download className="w-4 h-4" />
          Export CSV Report
        </button>
      </div>

      {/* High Level Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Searches', value: data.total_searches, icon: Search, color: '#b91c1c' },
          { label: 'Distinct Queries', value: data.distinct_searches, icon: Database, color: '#d97706' },
          { label: 'Registered Users', value: data.unique_users, icon: Users, color: '#4b5563' },
          { label: 'Searches Today', value: data.searches_today, icon: Activity, color: '#b91c1c' }
        ].map((stat, i) => (
          <div key={i} className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-500 font-medium text-sm uppercase tracking-wider">{stat.label}</span>
              <stat.icon className="w-5 h-5" style={{ color: stat.color }} />
            </div>
            <div className="text-3xl font-bold text-gray-900">{stat.value?.toLocaleString()}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activity Timeline */}
        <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
          <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Clock className="w-5 h-5 text-[#b91c1c]" />
            Activity History (30 Days)
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={[...data.per_day].reverse()}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#b91c1c" stopOpacity={0.1}/>
                    <stop offset="95%" stopColor="#b91c1c" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(str) => str.split('-').slice(1).join('/')}
                  tick={{fontSize: 12}}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis tick={{fontSize: 12}} axisLine={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                />
                <Area type="monotone" dataKey="count" stroke="#b91c1c" strokeWidth={2} fillOpacity={1} fill="url(#colorCount)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Search Type Distribution */}
        <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
          <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Filter className="w-5 h-5 text-[#b91c1c]" />
            Search Methods
          </h3>
          <div className="space-y-4">
            {data.by_type.map((type, i) => (
              <div key={i} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="font-medium text-gray-700">{type.type}</span>
                  <span className="text-gray-500">{type.count}</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-[#b91c1c]" 
                    style={{ width: `${(type.count / data.total_searches) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Geographic Distribution Map */}
      <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
        <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Globe className="w-5 h-5 text-[#b91c1c]" />
          Geographic Distribution
        </h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 bg-gray-50 rounded-xl flex items-center justify-center p-8 min-h-[350px] relative border border-gray-100">
            {/* Visual representation of user density */}
            <div className="text-center">
              <Globe className="w-24 h-24 text-gray-200 mx-auto mb-4" />
              <div className="text-gray-400 font-medium">User density visualization active</div>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {data.top_countries.slice(0, 5).map((c, i) => (
                  <span key={i} className="px-3 py-1 bg-white border border-gray-200 rounded-full text-xs font-medium text-gray-600 shadow-sm">
                    {c.country}: {c.count}
                  </span>
                ))}
              </div>
            </div>
            
            {/* Simulation of "Map Points" */}
            {data.top_cities.map((city, i) => (
              <div 
                key={i}
                className="absolute w-3 h-3 bg-[#b91c1c] rounded-full animate-pulse opacity-20"
                style={{ 
                  top: `${20 + (i * 15) % 60}%`, 
                  left: `${20 + (i * 25) % 60}%` 
                }}
              />
            ))}
          </div>
          
          <div className="space-y-6">
            <div>
              <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <MapPin className="w-4 h-4" />
                Top Cities
              </h4>
              <div className="space-y-3">
                {data.top_cities.slice(0, 8).map((city, i) => (
                  <div key={i} className="flex items-center justify-between group">
                    <span className="text-sm text-gray-600 group-hover:text-[#b91c1c] transition-colors">{city.city}, {city.country}</span>
                    <span className="text-sm font-bold text-gray-900">{city.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Language & Text Trends */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
          <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
            <Globe className="w-5 h-5 text-[#b91c1c]" />
            Languages
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.by_language}
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="count"
                  nameKey="language"
                >
                  {data.by_language.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-2 bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
          <h3 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
            <FileText className="w-5 h-5 text-[#b91c1c]" />
            Top Source Texts
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-50">
                  <th className="py-3 text-sm font-bold text-gray-400 uppercase tracking-wider">Text Identifier</th>
                  <th className="py-3 text-sm font-bold text-gray-400 uppercase tracking-wider text-right">Searches</th>
                </tr>
              </thead>
              <tbody>
                {data.top_sources.slice(0, 5).map((source, i) => (
                  <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors">
                    <td className="py-4 text-sm text-gray-700 font-medium">{source.text}</td>
                    <td className="py-4 text-sm text-gray-900 font-bold text-right">{source.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsTab;
