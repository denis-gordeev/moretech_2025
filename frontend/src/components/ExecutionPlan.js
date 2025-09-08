import React, { useState } from 'react';
import { Database, Clock, BarChart3, HardDrive, Eye, EyeOff } from 'lucide-react';
import JsonView from '@uiw/react-json-view';

const ExecutionPlan = ({ executionPlan }) => {
  const [showRawPlan, setShowRawPlan] = useState(false);

  if (!executionPlan) {
    return null;
  }

  const formatNumber = (num) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
  };

  const formatTime = (ms) => {
    if (ms >= 1000) {
      return (ms / 1000).toFixed(2) + 's';
    }
    return ms.toFixed(2) + 'ms';
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900 flex items-center">
          <Database className="w-5 h-5 mr-2" />
          План выполнения
        </h2>
        <button
          onClick={() => setShowRawPlan(!showRawPlan)}
          className="btn btn-secondary flex items-center"
        >
          {showRawPlan ? (
            <>
              <EyeOff className="w-4 h-4 mr-1" />
              Скрыть JSON
            </>
          ) : (
            <>
              <Eye className="w-4 h-4 mr-1" />
              Показать JSON
            </>
          )}
        </button>
      </div>

      {/* Основные метрики */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-blue-50 p-4 rounded-lg">
          <div className="flex items-center">
            <BarChart3 className="w-5 h-5 text-blue-600 mr-2" />
            <div>
              <p className="text-sm text-blue-600 font-medium">Общая стоимость</p>
              <p className="text-2xl font-bold text-blue-900">
                {formatNumber(executionPlan.total_cost)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-green-50 p-4 rounded-lg">
          <div className="flex items-center">
            <Clock className="w-5 h-5 text-green-600 mr-2" />
            <div>
              <p className="text-sm text-green-600 font-medium">Время выполнения</p>
              <p className="text-2xl font-bold text-green-900">
                {formatTime(executionPlan.execution_time)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-purple-50 p-4 rounded-lg">
          <div className="flex items-center">
            <Database className="w-5 h-5 text-purple-600 mr-2" />
            <div>
              <p className="text-sm text-purple-600 font-medium">Количество строк</p>
              <p className="text-2xl font-bold text-purple-900">
                {formatNumber(executionPlan.rows)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-orange-50 p-4 rounded-lg">
          <div className="flex items-center">
            <HardDrive className="w-5 h-5 text-orange-600 mr-2" />
            <div>
              <p className="text-sm text-orange-600 font-medium">Ширина строки</p>
              <p className="text-2xl font-bold text-orange-900">
                {executionPlan.width} байт
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Сырой JSON план */}
      {showRawPlan && (
        <div className="mt-4">
          <h3 className="text-lg font-medium text-gray-900 mb-2">JSON План выполнения</h3>
          <div className="bg-gray-50 p-4 rounded-lg max-h-96 overflow-auto">
            <JsonView
              value={executionPlan.plan_json}
              collapsed={2}
              displayDataTypes={false}
              displayObjectSize={false}
              enableClipboard={false}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ExecutionPlan;
