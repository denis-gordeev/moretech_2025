import React from 'react';
import { Cpu, MemoryStick, HardDrive, TrendingUp } from 'lucide-react';

const ResourceMetrics = ({ resourceMetrics }) => {
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

  return (
    <div className="card">
      <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
        <TrendingUp className="w-5 h-5 mr-2" />
        Метрики ресурсов
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* CPU Usage */}
        <div className={`p-4 rounded-lg ${getCpuColor(resourceMetrics.cpu_usage)}`}>
          <div className="flex items-center">
            <Cpu className="w-5 h-5 mr-2" />
            <div>
              <p className="text-sm font-medium">Использование CPU</p>
              <p className="text-2xl font-bold">
                {resourceMetrics.cpu_usage.toFixed(1)}%
              </p>
            </div>
          </div>
          <div className="mt-2">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-current h-2 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(resourceMetrics.cpu_usage, 100)}%` }}
              ></div>
            </div>
          </div>
        </div>

        {/* Memory Usage */}
        <div className={`p-4 rounded-lg ${getMemoryColor(resourceMetrics.memory_usage)}`}>
          <div className="flex items-center">
            <MemoryStick className="w-5 h-5 mr-2" />
            <div>
              <p className="text-sm font-medium">Использование памяти</p>
              <p className="text-2xl font-bold">
                {resourceMetrics.memory_usage.toFixed(1)} MB
              </p>
            </div>
          </div>
        </div>

        {/* I/O Operations */}
        <div className={`p-4 rounded-lg ${getIOColor(resourceMetrics.io_operations)}`}>
          <div className="flex items-center">
            <HardDrive className="w-5 h-5 mr-2" />
            <div>
              <p className="text-sm font-medium">I/O операции</p>
              <p className="text-2xl font-bold">
                {resourceMetrics.io_operations}
              </p>
            </div>
          </div>
        </div>

        {/* Disk Reads */}
        <div className="bg-blue-50 p-4 rounded-lg">
          <div className="flex items-center">
            <HardDrive className="w-5 h-5 text-blue-600 mr-2" />
            <div>
              <p className="text-sm text-blue-600 font-medium">Чтения с диска</p>
              <p className="text-2xl font-bold text-blue-900">
                {resourceMetrics.disk_reads}
              </p>
            </div>
          </div>
        </div>

        {/* Disk Writes */}
        <div className="bg-purple-50 p-4 rounded-lg">
          <div className="flex items-center">
            <HardDrive className="w-5 h-5 text-purple-600 mr-2" />
            <div>
              <p className="text-sm text-purple-600 font-medium">Записи на диск</p>
              <p className="text-2xl font-bold text-purple-900">
                {resourceMetrics.disk_writes}
              </p>
            </div>
          </div>
        </div>

        {/* Total I/O */}
        <div className="bg-gray-50 p-4 rounded-lg">
          <div className="flex items-center">
            <TrendingUp className="w-5 h-5 text-gray-600 mr-2" />
            <div>
              <p className="text-sm text-gray-600 font-medium">Общий I/O</p>
              <p className="text-2xl font-bold text-gray-900">
                {resourceMetrics.disk_reads + resourceMetrics.disk_writes}
              </p>
            </div>
          </div>
        </div>
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
