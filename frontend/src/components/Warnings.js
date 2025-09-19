import React from 'react';
import { AlertTriangle, Info, XCircle, CheckCircle } from 'lucide-react';

const Warnings = ({ warnings }) => {
  if (!warnings || warnings.length === 0) {
    return (
      <div className="card">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
          <CheckCircle className="w-5 h-5 mr-2 text-green-600" />
          Предупреждения
        </h2>
        <div className="text-center py-8 text-gray-500">
          <CheckCircle className="w-12 h-12 mx-auto mb-4 text-green-300" />
          <p>Критических предупреждений не найдено</p>
        </div>
      </div>
    );
  }

  const getWarningIcon = (warning, index) => {
    const warningLower = warning.toLowerCase();
    
    if (warningLower.includes('error') || warningLower.includes('ошибка')) {
      return <XCircle className="w-5 h-5 text-red-600" />;
    } else if (warningLower.includes('warning') || warningLower.includes('предупреждение')) {
      return <AlertTriangle className="w-5 h-5 text-yellow-600" />;
    } else {
      return <Info className="w-5 h-5 text-blue-600" />;
    }
  };

  const getWarningColor = (warning) => {
    const warningLower = warning.toLowerCase();
    
    if (warningLower.includes('error') || warningLower.includes('ошибка')) {
      return 'border-red-200 bg-red-50';
    } else if (warningLower.includes('warning') || warningLower.includes('предупреждение')) {
      return 'border-yellow-200 bg-yellow-50';
    } else {
      return 'border-blue-200 bg-blue-50';
    }
  };

  const getTextColor = (warning) => {
    const warningLower = warning.toLowerCase();
    
    if (warningLower.includes('error') || warningLower.includes('ошибка')) {
      return 'text-red-800';
    } else if (warningLower.includes('warning') || warningLower.includes('предупреждение')) {
      return 'text-yellow-800';
    } else {
      return 'text-blue-800';
    }
  };

  return (
    <div className="card">
      <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
        <AlertTriangle className="w-5 h-5 mr-2 text-yellow-600" />
        Предупреждения
        <span className="ml-2 text-sm font-normal text-gray-500">
          ({warnings.length} найдено)
        </span>
      </h2>

      <div className="space-y-3">
        {warnings.map((warning, index) => (
          <div
            key={index}
            className={`p-4 rounded-lg border ${getWarningColor(warning)}`}
          >
            <div className="flex items-start space-x-3">
              {getWarningIcon(warning, index)}
              <div className="flex-1">
                <p className={`text-sm font-medium ${getTextColor(warning)}`}>
                  {warning}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Дополнительная информация */}
      <div className="mt-4 p-3 bg-gray-50 rounded-lg">
        <div className="flex items-start space-x-2">
          <Info className="w-4 h-4 text-gray-500 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-gray-600">
            <p className="font-medium mb-1">О предупреждениях:</p>
            <ul className="list-disc list-inside space-y-1 text-xs">
              <li>Красные предупреждения указывают на критические проблемы</li>
              <li>Желтые предупреждения требуют внимания</li>
              <li>Синие предупреждения содержат полезную информацию</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Warnings;
