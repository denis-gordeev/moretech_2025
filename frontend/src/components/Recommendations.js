import React, { useState } from 'react';
import { Lightbulb, ChevronDown, ChevronRight, ExternalLink, Copy } from 'lucide-react';

const Recommendations = ({ recommendations }) => {
  const [expandedItems, setExpandedItems] = useState({});

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="card">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <Lightbulb className="w-5 h-5 mr-2" />
          Рекомендации по оптимизации
        </h2>
        <div className="text-center py-8 text-gray-500">
          <Lightbulb className="w-12 h-12 mx-auto mb-4 text-gray-300" />
          <p>Рекомендации по оптимизации не найдены</p>
        </div>
      </div>
    );
  }

  const toggleExpanded = (index) => {
    setExpandedItems(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const getPriorityBadge = (priority) => {
    const baseClasses = "badge";
    switch (priority) {
      case 'high':
        return `${baseClasses} badge-high`;
      case 'medium':
        return `${baseClasses} badge-medium`;
      case 'low':
        return `${baseClasses} badge-low`;
      default:
        return `${baseClasses} bg-gray-100 text-gray-800`;
    }
  };

  const getTypeIcon = (type) => {
    switch (type.toLowerCase()) {
      case 'index':
        return '📊';
      case 'query_rewrite':
        return '✏️';
      case 'config':
        return '⚙️';
      case 'structure':
        return '🏗️';
      default:
        return '💡';
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="card">
      <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
        <Lightbulb className="w-5 h-5 mr-2" />
        Рекомендации по оптимизации
        <span className="ml-2 text-sm font-normal text-gray-500">
          ({recommendations.length} найдено)
        </span>
      </h2>

      <div className="space-y-4">
        {recommendations.map((recommendation, index) => (
          <div
            key={index}
            className="border border-gray-200 rounded-lg overflow-hidden"
          >
            <div
              className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
              onClick={() => toggleExpanded(index)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3 flex-1">
                  <span className="text-2xl">
                    {getTypeIcon(recommendation.type)}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <h3 className="font-medium text-gray-900">
                        {recommendation.title}
                      </h3>
                      <span className={getPriorityBadge(recommendation.priority)}>
                        {recommendation.priority.toUpperCase()}
                      </span>
                      {recommendation.estimated_speedup && (
                        <span className="badge bg-green-100 text-green-800">
                          +{recommendation.estimated_speedup.toFixed(0)}% ускорение
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 line-clamp-2">
                      {recommendation.description}
                    </p>
                  </div>
                </div>
                <div className="ml-4">
                  {expandedItems[index] ? (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  )}
                </div>
              </div>
            </div>

            {expandedItems[index] && (
              <div className="px-4 pb-4 border-t border-gray-100">
                <div className="pt-4 space-y-4">
                  {/* Потенциальное улучшение */}
                  <div>
                    <h4 className="font-medium text-gray-900 mb-2 flex items-center">
                      <ExternalLink className="w-4 h-4 mr-1" />
                      Потенциальное улучшение
                    </h4>
                    <p className="text-sm text-gray-600 bg-blue-50 p-3 rounded-lg">
                      {recommendation.potential_improvement}
                    </p>
                  </div>

                  {/* Реализация */}
                  <div>
                    <h4 className="font-medium text-gray-900 mb-2 flex items-center">
                      <Copy className="w-4 h-4 mr-1" />
                      Как реализовать
                    </h4>
                    <div className="bg-gray-50 p-3 rounded-lg">
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono">
                        {recommendation.implementation}
                      </pre>
                      <button
                        onClick={() => copyToClipboard(recommendation.implementation)}
                        className="mt-2 text-xs text-blue-600 hover:text-blue-800 flex items-center"
                      >
                        <Copy className="w-3 h-3 mr-1" />
                        Копировать
                      </button>
                    </div>
                  </div>

                  {/* Дополнительная информация */}
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Тип: {recommendation.type}</span>
                    {recommendation.estimated_speedup && (
                      <span>
                        Ожидаемое ускорение: {recommendation.estimated_speedup.toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Сводка по приоритетам */}
      <div className="mt-6 p-4 bg-gray-50 rounded-lg">
        <h4 className="font-medium text-gray-900 mb-2">Сводка по приоритетам</h4>
        <div className="flex space-x-4 text-sm">
          <div className="flex items-center">
            <span className="badge badge-high mr-2">HIGH</span>
            <span className="text-gray-600">
              {recommendations.filter(r => r.priority === 'high').length} критических
            </span>
          </div>
          <div className="flex items-center">
            <span className="badge badge-medium mr-2">MEDIUM</span>
            <span className="text-gray-600">
              {recommendations.filter(r => r.priority === 'medium').length} важных
            </span>
          </div>
          <div className="flex items-center">
            <span className="badge badge-low mr-2">LOW</span>
            <span className="text-gray-600">
              {recommendations.filter(r => r.priority === 'low').length} дополнительных
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Recommendations;
