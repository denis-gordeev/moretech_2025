import React, { useState, useEffect } from 'react';
import { Heart, Database, Brain, RefreshCw, CheckCircle, XCircle, Info } from 'lucide-react';
import { queryAnalyzerAPI } from '../services/api';

const HealthStatus = () => {
  const [health, setHealth] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastChecked, setLastChecked] = useState(null);

  const checkHealth = async () => {
    setIsLoading(true);
    try {
      const response = await queryAnalyzerAPI.healthCheck();
      setHealth(response.data);
      setLastChecked(new Date());
    } catch (error) {
      console.error('Health check failed:', error);
      setHealth({
        status: 'unhealthy',
        database_connected: false,
        openai_available: false,
        timestamp: new Date().toISOString()
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    // Проверяем здоровье каждые 30 секунд
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!health) {
    return (
      <div className="card">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </div>
    );
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'unhealthy':
        return 'text-red-600 bg-red-50 border-red-200';
      default:
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5" />;
      case 'unhealthy':
        return <XCircle className="w-5 h-5" />;
      default:
        return <Heart className="w-5 h-5" />;
    }
  };

  const formatLastChecked = () => {
    if (!lastChecked) return 'Никогда';
    const now = new Date();
    const diff = now - lastChecked;
    const seconds = Math.floor(diff / 1000);
    
    if (seconds < 60) return `${seconds} сек назад`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes} мин назад`;
    const hours = Math.floor(minutes / 60);
    return `${hours} ч назад`;
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900 flex items-center">
          <Heart className="w-5 h-5 mr-2" />
          Статус системы
        </h2>
        <button
          onClick={checkHealth}
          disabled={isLoading}
          className="btn btn-secondary flex items-center"
        >
          <RefreshCw className={`w-4 h-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
          Обновить
        </button>
      </div>

      {/* Общий статус */}
      <div className={`p-4 rounded-lg border ${getStatusColor(health.status)} mb-4`}>
        <div className="flex items-center">
          {getStatusIcon(health.status)}
          <div className="ml-3">
            <p className="font-medium">
              Система {health.status === 'healthy' ? 'работает' : 'не работает'}
            </p>
            <p className="text-sm opacity-75">
              Последняя проверка: {formatLastChecked()}
            </p>
          </div>
        </div>
      </div>

      {/* Детали компонентов */}
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center">
            <Database className="w-5 h-5 text-gray-600 mr-3" />
            <span className="font-medium text-gray-900">PostgreSQL</span>
          </div>
          <div className="flex items-center">
            {health.database_connected ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600" />
            )}
            <span className={`ml-2 text-sm ${
              health.database_connected ? 'text-green-600' : 'text-red-600'
            }`}>
              {health.database_connected ? 'Подключено' : 'Не подключено'}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center">
            <Brain className="w-5 h-5 text-gray-600 mr-3" />
            <span className="font-medium text-gray-900">OpenAI API</span>
          </div>
          <div className="flex items-center">
            {health.openai_available ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <XCircle className="w-5 h-5 text-red-600" />
            )}
            <span className={`ml-2 text-sm ${
              health.openai_available ? 'text-green-600' : 'text-red-600'
            }`}>
              {health.openai_available ? 'Доступно' : 'Недоступно'}
            </span>
          </div>
        </div>
      </div>

      {/* Дополнительная информация */}
      <div className="mt-4 p-3 bg-blue-50 rounded-lg">
        <div className="flex items-start space-x-2">
          <Info className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">О статусе системы:</p>
            <ul className="list-disc list-inside space-y-1 text-xs">
              <li>PostgreSQL используется для анализа планов выполнения</li>
              <li>OpenAI API обеспечивает интеллектуальные рекомендации</li>
              <li>Статус обновляется автоматически каждые 30 секунд</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HealthStatus;
