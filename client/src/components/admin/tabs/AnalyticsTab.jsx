import React, { useState, useEffect } from 'react';
import { 
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, LineChart, Line, Legend, AreaChart, Area
} from 'recharts';
import { 
  Download, Users, Search, Activity, Globe, Clock, 
  MapPin, Filter, Database, FileText
} from 'lucide-react';
import GeographicMap from './GeographicMap';
import { formatTesseraeIdentifier } from '../../../utils/textNames';

const TESSERAE_RED = '#b91c1c';
const TESSERAE_GOLD = '#d97706';
const TESSERAE_GRAY = '#4b5563';
const COLORS = [TESSERAE_RED, '#dc2626', '#ef4444', '#f87171', TESSERAE_GOLD, '#fbbf24'];

const AnalyticsTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [graphMetric, setGraphMetric] = useState('searches'); // 'searches', 'users', 'cache'

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
    const interval = setInterval(fetchAnalytics, 30000);
    return () => clearInterval(interval);
  }, []);

  const LANG_NAMES = { 
    la: 'Latin', 
    grc: 'Greek', 
    en: 'English',
    cop: 'Coptic',
    ar: 'Arabic',
    he: 'Hebrew',
    ur: 'Urdu',
    fa: 'Farsi',
    el: 'Modern Greek',
    syr: 'Syriac'
  };

  const exportToCSV = () => {
    if (!data) return;
    
    const lines = [];
    const today = new Date().toISOString().split('T')[0];

    lines.push('TESSERAE V6 — USER ANALYTICS EXPORT');
    lines.push(`Exported: ${today}`);
    lines.push('');

    lines.push('SUMMARY');
    lines.push('Metric,Value');
    lines.push(`Total Searches,${data.total_searches || 0}`);
    lines.push(`Distinct Queries,${data.distinct_searches || 0}`);
    lines.push(`Unique Users,${data.unique_users || 'N/A'}`);
    const todayCount = data.per_day?.find(d => d.date === today)?.count || data.searches_today || 0;
    lines.push(`Searches Today,${todayCount}`);
    lines.push(`Cache Hits,${data.cache_hits || 0}`);
    lines.push(`Cache Misses,${data.cache_misses || 0}`);
    lines.push('');

    if (data.by_type?.length) {
      lines.push('SEARCHES BY TYPE');
      lines.push('Type,Count');
      data.by_type.forEach(item => lines.push(`${item.type},${item.count}`));
      lines.push('');
    }

    if (data.by_language?.length) {
      lines.push('SEARCHES BY LANGUAGE');
      lines.push('Language,Count');
      data.by_language.forEach(item =>
        lines.push(`${LANG_NAMES[item.language] || item.language},${item.count}`)
      );
      lines.push('');
    }

    if (data.top_sources?.length) {
      lines.push('TOP SOURCE TEXTS');
      lines.push('Text,Count');
      data.top_sources.forEach(item =>
        lines.push(`"${item.text.replace(/"/g, '""')}",${item.count}`)
      );
      lines.push('');
    }

    if (data.top_targets?.length) {
      lines.push('TOP TARGET TEXTS');
      lines.push('Text,Count');
      data.top_targets.forEach(item =>
        lines.push(`"${item.text.replace(/"/g, '""')}",${item.count}`)
      );
      lines.push('');
    }

    if (data.per_day?.length) {
      lines.push('DAILY SEARCH ACTIVITY');
      lines.push('Date,Count');
      data.per_day.forEach(item => lines.push(`${item.date},${item.count}`));
      lines.push('');
    }

    if (data.top_countries?.length) {
      lines.push('TOP COUNTRIES');
      lines.push('Country,Count');
      data.top_countries.forEach(item => lines.push(`${item.country},${item.count}`));
      lines.push('');
    }

    if (data.top_cities?.length) {
      lines.push('TOP CITIES');
      lines.push('City,Country,Count');
      data.top_cities.forEach(item =>
        lines.push(`"${item.city}","${item.country || ''}",${item.count}`)
      );
    }

    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tesserae_analytics_${today}.csv`;
    a.click();
    URL.revokeObjectURL(url);
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
        <div className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm flex flex-col justify-between">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <Clock className="w-5 h-5 text-[#b91c1c]" />
              Activity History (30 Days)
            </h3>
            
            {/* Metric Selector Buttons */}
            <div className="bg-gray-100 p-0.5 rounded-lg flex border border-gray-200">
              <button
                onClick={() => setGraphMetric('searches')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  graphMetric === 'searches'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Searches
              </button>
              <button
                onClick={() => setGraphMetric('users')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  graphMetric === 'users'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Active Users
              </button>
              <button
                onClick={() => setGraphMetric('cache')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  graphMetric === 'cache'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Cache Performance
              </button>
            </div>
          </div>
          
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              {graphMetric === 'searches' && (
                <AreaChart data={[...(data?.per_day || [])].reverse()}>
                  <defs>
                    <linearGradient id="colorSearches" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#b91c1c" stopOpacity={0.15}/>
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
                  <Area type="monotone" name="Searches" dataKey="count" stroke="#b91c1c" strokeWidth={2} fillOpacity={1} fill="url(#colorSearches)" />
                </AreaChart>
              )}

              {graphMetric === 'users' && (
                <AreaChart data={[...(data?.per_day || [])].reverse()}>
                  <defs>
                    <linearGradient id="colorUsers" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#d97706" stopOpacity={0.15}/>
                      <stop offset="95%" stopColor="#d97706" stopOpacity={0}/>
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
                  <Area type="monotone" name="Active Users" dataKey="users" stroke="#d97706" strokeWidth={2} fillOpacity={1} fill="url(#colorUsers)" />
                </AreaChart>
              )}

              {graphMetric === 'cache' && (
                <LineChart data={[...(data?.per_day || [])].reverse()}>
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
                  <Legend verticalAlign="top" height={36} iconType="circle" />
                  <Line type="monotone" name="Cache Hits" dataKey="cache_hits" stroke="#10b981" strokeWidth={2.5} activeDot={{ r: 6 }} dot={{ r: 3 }} />
                  <Line type="monotone" name="Cache Misses" dataKey="cache_misses" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              )}
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <GeographicMap 
            topCities={data.top_cities || []} 
            topCountries={data.top_countries || []} 
          />
          
          <div className="space-y-6 flex flex-col justify-center">
            <div>
              <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <MapPin className="w-4 h-4 text-[#b91c1c]" />
                Top Cities
              </h4>
              <div className="space-y-3">
                {data.top_cities.slice(0, 8).map((city, i) => (
                  <div key={i} className="flex items-center justify-between group border-b border-gray-50 pb-2 last:border-0">
                    <span className="text-sm text-gray-600 group-hover:text-[#b91c1c] transition-colors">{city.city}, {city.country}</span>
                    <span className="text-sm font-bold text-gray-900 bg-gray-50 px-2 py-0.5 rounded-full">{city.count}</span>
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
                  data={data.by_language?.map(item => ({
                    ...item,
                    name: LANG_NAMES[item.language] || item.language
                  })) || []}
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="count"
                  nameKey="name"
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
                    <td className="py-4 text-sm text-gray-700 font-medium" title={source.text}>
                      {formatTesseraeIdentifier(source.text)}
                    </td>
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
