import React from 'react';
import MetricTooltip from './MetricTooltip';

const LLMMetrics = ({ metrics }) => {
  if (!metrics) return null;

  // Захардкоженные описания для всех возможных полей
  const metricDescriptions = {
    cpu_usage: "Ожидаемое использование CPU в процентах. Высокие значения указывают на вычислительно сложные операции (сортировка, агрегация, сложные JOIN).",
    memory_usage: "Ожидаемое использование памяти в мегабайтах. Включает буферы, хеш-таблицы, временные структуры данных и рабочие области.",
    io_operations: "Общее количество операций ввода-вывода. Включает чтение с диска, запись на диск и сетевые операции.",
    disk_reads: "Количество операций чтения с диска. Высокие значения указывают на необходимость оптимизации индексов или кэширования.",
    disk_writes: "Количество операций записи на диск. Важно для DML операций (INSERT, UPDATE, DELETE) и временных файлов.",
    disk_io: "Общий объем дисковых операций в мегабайтах. Сумма всех операций чтения и записи. Влияет на время выполнения запроса.",
    network_io: "Объем сетевого трафика в килобайтах. Важно для распределенных запросов, репликации и внешних соединений.",
    execution_time: "Ожидаемое время выполнения запроса в миллисекундах. Основано на анализе плана выполнения и статистике таблиц.",
    rows_processed: "Ожидаемое количество строк, которые будут обработаны при выполнении запроса. Включает все промежуточные результаты.",
    index_usage: "Процент использования индексов (0-100). Высокие значения указывают на эффективное использование индексов для ускорения запросов.",
    cache_hit_ratio: "Ожидаемый процент попаданий в кэш буферов (0-100). Высокие значения улучшают производительность, низкие указывают на нехватку памяти.",
    lock_contention: "Уровень конкуренции за блокировки (0-100). Высокие значения могут замедлить выполнение DML операций и указывают на необходимость оптимизации."
  };

  // Функция для отображения метрики с правильным форматированием
  const renderMetric = (key, label, unit = '') => {
    const value = metrics[key];
    if (value === undefined || value === null) return null;
    
    return (
      <MetricTooltip
        key={key}
        label={label}
        value={`${value}${unit}`}
        description={metricDescriptions[key] || `Описание для ${label}`}
      />
    );
  };

  return (
    <div className="card">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Метрики производительности</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {renderMetric('cpu_usage', 'CPU Usage', '%')}
        {renderMetric('memory_usage', 'Memory Usage', ' MB')}
        {renderMetric('io_operations', 'I/O Operations', '')}
        {renderMetric('disk_reads', 'Disk Reads', '')}
        {renderMetric('disk_writes', 'Disk Writes', '')}
        {renderMetric('disk_io', 'Disk I/O', ' MB')}
        {renderMetric('network_io', 'Network I/O', ' KB')}
        {renderMetric('execution_time', 'Execution Time', ' ms')}
        {renderMetric('rows_processed', 'Rows Processed', '')}
        {renderMetric('index_usage', 'Index Usage', '%')}
        {renderMetric('cache_hit_ratio', 'Cache Hit Ratio', '%')}
        {renderMetric('lock_contention', 'Lock Contention', '%')}
      </div>
    </div>
  );
};

export default LLMMetrics;
