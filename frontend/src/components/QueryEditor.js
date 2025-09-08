import React, { useState } from 'react';
import { Play, Copy, RotateCcw } from 'lucide-react';

const QueryEditor = ({ query, onQueryChange, onAnalyze, isLoading, examples }) => {
  const [showExamples, setShowExamples] = useState(false);

  const handleExampleSelect = (exampleQuery) => {
    onQueryChange(exampleQuery);
    setShowExamples(false);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(query);
  };

  const handleClear = () => {
    onQueryChange('');
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900">SQL Запрос</h2>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowExamples(!showExamples)}
            className="btn btn-secondary"
            disabled={isLoading}
          >
            Примеры
          </button>
          <button
            onClick={handleCopy}
            className="btn btn-secondary"
            disabled={!query.trim()}
          >
            <Copy className="w-4 h-4 mr-1" />
            Копировать
          </button>
          <button
            onClick={handleClear}
            className="btn btn-secondary"
            disabled={!query.trim() || isLoading}
          >
            <RotateCcw className="w-4 h-4 mr-1" />
            Очистить
          </button>
        </div>
      </div>

      {showExamples && examples && (
        <div className="mb-4 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Примеры запросов:</h3>
          <div className="space-y-2">
            {examples.map((example, index) => (
              <div key={index} className="border border-gray-200 rounded p-2">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium text-sm">{example.name}</h4>
                    <p className="text-xs text-gray-600">{example.description}</p>
                  </div>
                  <button
                    onClick={() => handleExampleSelect(example.query)}
                    className="btn btn-primary text-xs px-2 py-1"
                  >
                    Использовать
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="relative">
        <textarea
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Введите SQL запрос для анализа..."
          className="textarea font-mono text-sm"
          rows={8}
          disabled={isLoading}
        />
        <div className="absolute bottom-2 right-2 text-xs text-gray-400">
          {query.length} символов
        </div>
      </div>

      <div className="mt-4 flex justify-end">
        <button
          onClick={onAnalyze}
          disabled={!query.trim() || isLoading}
          className="btn btn-primary flex items-center"
        >
          {isLoading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Анализирую...
            </>
          ) : (
            <>
              <Play className="w-4 h-4 mr-2" />
              Анализировать запрос
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default QueryEditor;
