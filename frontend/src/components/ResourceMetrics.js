import React, { useState } from 'react';
import { Cpu, MemoryStick, HardDrive, TrendingUp, Clock, Database, ChevronDown, ChevronUp } from 'lucide-react';

const ResourceMetrics = ({ resourceMetrics }) => {
  const [showAll, setShowAll] = useState(false);
  
  if (!resourceMetrics) {
    return null;
  }

  const getCpuColor = (usage) => {
    if (usage >= 80) return 'text-red-600 bg-red-50';
    if (usage >= 60) return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  const getMemoryColor = (usage) => {
    if (usage >= 1000) return 'text-red-600 bg-red-50';
    if (usage >= 500) return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  const getIOColor = (operations) => {
    if (operations >= 100) return 'text-red-600 bg-red-50';
    if (operations >= 50) return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  // Компонент для метрики с tooltip
  const MetricCard = ({ icon: Icon, title, value, unit, color, description }) => (
    <div className={`p-4 rounded-lg ${color} relative group`}>
      <div className="flex items-center">
        <Icon className="w-5 h-5 mr-2" />
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-2xl font-bold">
            {value}{unit}
          </p>
        </div>
      </div>
      {description && (
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg max-w-xs">
            {description}
          </div>
        </div>
      )}
    </div>
  );

  // Основные метрики (всегда видны)
  const primaryMetrics = [
    {
      key: 'cpu_usage',
      icon: Cpu,
      title: 'Использование CPU',
      value: resourceMetrics.cpu_usage?.toFixed(1) || 0,
      unit: '%',
      color: getCpuColor(resourceMetrics.cpu_usage || 0),
      description: 'Ожидаемое использование CPU в процентах. Высокие значения указывают на вычислительно сложные операции.'
    },
    {
      key: 'memory_usage',
      icon: MemoryStick,
      title: 'Использование памяти',
      value: resourceMetrics.memory_usage?.toFixed(1) || 0,
      unit: ' MB',
      color: getMemoryColor(resourceMetrics.memory_usage || 0),
      description: 'Ожидаемое использование памяти в мегабайтах. Включает буферы, хеш-таблицы и временные структуры данных.'
    },
    {
      key: 'execution_time',
      icon: Clock,
      title: 'Время выполнения',
      value: resourceMetrics.execution_time || 0,
      unit: ' ms',
      color: 'text-blue-600 bg-blue-50',
      description: 'Ожидаемое время выполнения запроса в миллисекундах. Основано на анализе плана выполнения.'
    }
  ];

  // Дополнительные метрики (скрыты по умолчанию)
  const secondaryMetrics = [
    {
      key: 'io_operations',
      icon: HardDrive,
      title: 'I/O операции',
      value: resourceMetrics.io_operations || 0,
      unit: '',
      color: getIOColor(resourceMetrics.io_operations || 0),
      description: 'Общее количество операций ввода-вывода. Включает чтение с диска, запись на диск и сетевые операции.'
    },
    {
      key: 'disk_reads',
      icon: Database,
      title: 'Чтения с диска',
      value: resourceMetrics.disk_reads || 0,
      unit: '',
      color: 'text-blue-600 bg-blue-50',
      description: 'Количество операций чтения с диска. Высокие значения указывают на необходимость оптимизации индексов.'
    },
    {
      key: 'disk_writes',
      icon: Database,
      title: 'Записи на диск',
      value: resourceMetrics.disk_writes || 0,
      unit: '',
      color: 'text-purple-600 bg-purple-50',
      description: 'Количество операций записи на диск. Важно для DML операций и временных файлов.'
    },
    {
      key: 'rows_processed',
      icon: TrendingUp,
      title: 'Обработано строк',
      value: resourceMetrics.rows_processed || 0,
      unit: '',
      color: 'text-green-600 bg-green-50',
      description: 'Ожидаемое количество строк, которые будут обработаны при выполнении запроса.'
    },
    {
      key: 'index_usage',
      icon: TrendingUp,
      title: 'Использование индексов',
      value: resourceMetrics.index_usage || 0,
      unit: '%',
      color: 'text-indigo-600 bg-indigo-50',
      description: 'Процент использования индексов. Высокие значения указывают на эффективное использование индексов.'
    },
    {
      key: 'cache_hit_ratio',
      icon: TrendingUp,
      title: 'Попадания в кэш',
      value: resourceMetrics.cache_hit_ratio || 0,
      unit: '%',
      color: 'text-orange-600 bg-orange-50',
      description: 'Ожидаемый процент попаданий в кэш буферов. Высокие значения улучшают производительность.'
    }
  ];

  return (
    <div className="card">
      <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
        <TrendingUp className="w-5 h-5 mr-2" />
        Метрики ресурсов
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Основные метрики */}
        {primaryMetrics.map((metric) => (
          <MetricCard key={metric.key} {...metric} />
        ))}
        
        {/* Дополнительные метрики (показываются при разворачивании) */}
        {showAll && secondaryMetrics.map((metric) => (
          <MetricCard key={metric.key} {...metric} />
        ))}
      </div>

      {/* Кнопка для разворачивания/сворачивания */}
      <div className="mt-4 flex justify-center">
        <button
          onClick={() => setShowAll(!showAll)}
          className="flex items-center px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
        >
          {showAll ? (
            <>
              <ChevronUp className="w-4 h-4 mr-1" />
              Скрыть дополнительные метрики
            </>
          ) : (
            <>
              <ChevronDown className="w-4 h-4 mr-1" />
              Показать все метрики
            </>
          )}
        </button>
      </div>

      {/* Дополнительная информация */}
      <div className="mt-4 p-3 bg-gray-50 rounded-lg">
        <p className="text-sm text-gray-600">
          <strong>Примечание:</strong> Метрики основаны на анализе плана выполнения и могут отличаться от фактических значений при выполнении запроса.
        </p>
      </div>
    </div>
  );
};

export default ResourceMetrics;
