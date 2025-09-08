import React from 'react';
import { Copy, CheckCircle } from 'lucide-react';

const RewrittenQuery = ({ rewrittenQuery, originalQuery }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(rewrittenQuery);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  if (!rewrittenQuery || rewrittenQuery.trim() === '') {
    return null;
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
          <h2 className="text-xl font-semibold text-gray-900">
            Исправленный запрос
          </h2>
        </div>
        <button
          onClick={handleCopy}
          className="btn btn-secondary flex items-center"
        >
          {copied ? (
            <>
              <CheckCircle className="w-4 h-4 mr-1" />
              Скопировано
            </>
          ) : (
            <>
              <Copy className="w-4 h-4 mr-1" />
              Копировать
            </>
          )}
        </button>
      </div>

      <div className="space-y-4">
        {/* Оригинальный запрос */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Оригинальный запрос:</h3>
          <div className="bg-gray-50 p-3 rounded-lg border">
            <pre className="text-sm font-mono text-gray-800 whitespace-pre-wrap">
              {originalQuery}
            </pre>
          </div>
        </div>

        {/* Исправленный запрос */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-2">Исправленный запрос:</h3>
          <div className="bg-green-50 p-3 rounded-lg border border-green-200">
            <pre className="text-sm font-mono text-green-800 whitespace-pre-wrap">
              {rewrittenQuery}
            </pre>
          </div>
        </div>

        <div className="text-sm text-gray-600 bg-blue-50 p-3 rounded-lg border border-blue-200">
          <strong>💡 Совет:</strong> LLM автоматически оптимизировал ваш запрос для лучшей производительности. 
          Вы можете скопировать исправленную версию и использовать её вместо оригинальной.
        </div>
      </div>
    </div>
  );
};

export default RewrittenQuery;
