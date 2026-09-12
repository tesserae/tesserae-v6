import { useState, useEffect } from 'react';

export default function BlogArchivePage({ setPageType }) {
  const [expandedPost, setExpandedPost] = useState(null);
  const [v3BlogPosts, setV3BlogPosts] = useState([]);

  useEffect(() => {
    let isMounted = true;
    import('../../data/v3_blog_posts.json')
      .then((module) => {
        if (!isMounted) return;
        const data = module && module.default ? module.default : module;
        setV3BlogPosts(data);
      })
      .catch((error) => {
        console.error('Failed to load v3_blog_posts.json', error);
      });
    return () => { isMounted = false; };
  }, []);

  const togglePost = (key) => {
    setExpandedPost(expandedPost === key ? null : key);
  };

  return (
    <div className="bg-white rounded-lg shadow p-4 sm:p-8">
      <div className="mb-6">
        <button
          onClick={() => setPageType('research')}
          className="text-sm text-red-600 hover:text-red-800 mb-3 inline-flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Research
        </button>
        <h2 className="text-2xl font-semibold text-gray-900 mb-2">Archived V3 Blog Posts</h2>
        <p className="text-gray-600 text-sm">
          These posts were preserved from the legacy Tesserae Version 3 website blog (2019–2021).
          Original content recovered from the Wayback Machine.
        </p>
      </div>

      <div className="space-y-4">
        {v3BlogPosts.map((post, index) => {
          const postKey = post.url || `post-${index}`;
          const isExpanded = expandedPost === postKey;
          return (
            <div
              key={postKey}
              className="border border-gray-200 rounded-lg overflow-hidden bg-white hover:border-red-200 transition-colors"
            >
              <button
                onClick={() => togglePost(postKey)}
                aria-expanded={isExpanded}
                aria-controls={`panel-${postKey.replace(/[^a-zA-Z0-9]/g, '-')}`}
                className="w-full px-5 py-4 flex items-center justify-between bg-gray-50 hover:bg-red-50 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
              >
                <div className="pr-4">
                  <h4 className="text-base font-medium text-gray-900 mb-1">{post.title}</h4>
                  <span className="text-xs text-gray-500 font-medium">
                    {post.author && post.author !== 'Tesserae Project Team'
                      ? `${post.author} — ${post.date}`
                      : post.date}
                  </span>
                </div>
                <svg
                  className={`w-5 h-5 text-gray-500 flex-shrink-0 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {isExpanded && (
                <div id={`panel-${postKey.replace(/[^a-zA-Z0-9]/g, '-')}`} className="px-5 py-4 border-t border-gray-100 bg-white">
                  {post.author && (
                    <p className="text-sm text-gray-600 mb-3">
                      <span className="font-medium">By {post.author}</span>
                    </p>
                  )}
                  {post.url && (
                    <a
                      href={post.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center text-xs text-red-600 hover:text-red-800 font-medium mb-4"
                    >
                      View Original on Wayback Machine
                      <svg className="w-3 h-3 ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  )}
                  <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                    {post.content}
                  </div>
                  {post.images && post.images.length > 0 && (
                    <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {post.images.map((imgSrc, imgIdx) => (
                        <img
                          key={imgIdx}
                          src={imgSrc}
                          alt={`Archived illustration from ${post.title}`}
                          className="rounded border border-gray-200 shadow-sm max-w-full h-auto"
                          onError={(e) => { e.target.style.display = 'none'; }}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
