import React, { useState } from 'react';
import { Database, Zap, Clock, BarChart3, ChevronDown, ChevronUp } from 'lucide-react';

const ExecutionPlan = ({ plan }) => {
  const [showDetails, setShowDetails] = useState(false);
  
  if (!plan) return null;

  // Словарь русскоязычных названий для полей
  const fieldNames = {
    'Node Type': 'Тип узла',
    'Total Cost': 'Общая стоимость',
    'Startup Cost': 'Стоимость запуска',
    'Plan Rows': 'Ожидаемые строки',
    'Plan Width': 'Ширина строки',
    'Join Type': 'Тип соединения',
    'Strategy': 'Стратегия',
    'Index Name': 'Название индекса',
    'Relation Name': 'Название таблицы',
    'Alias': 'Псевдоним',
    'Hash Cond': 'Условие хеша',
    'Index Cond': 'Условие индекса',
    'Filter': 'Фильтр',
    'Sort Key': 'Ключ сортировки',
    'Group Key': 'Ключ группировки',
    'Scan Direction': 'Направление сканирования',
    'Parallel Aware': 'Параллельный',
    'Async Capable': 'Асинхронный',
    'Inner Unique': 'Внутренняя уникальность',
    'Partial Mode': 'Режим частичной агрегации',
    'Planned Partitions': 'Запланированные партиции',
    'Parent Relationship': 'Связь с родителем',
    'Query Type': 'Тип запроса'
  };

  // Захардкоженные описания для всех возможных полей EXPLAIN
  const fieldDescriptions = {
    'Node Type': 'Тип узла плана выполнения. Определяет алгоритм обработки данных (Seq Scan, Index Scan, Hash Join, etc.).',
    'Total Cost': 'Общая стоимость выполнения узла в единицах стоимости PostgreSQL. Чем меньше, тем лучше. Основа для сравнения планов.',
    'Startup Cost': 'Стоимость запуска узла до получения первой строки. Важно для LIMIT запросов и курсоров.',
    'Plan Rows': 'Ожидаемое количество строк, которое вернет этот узел. Основано на статистике таблиц и селективности условий.',
    'Plan Width': 'Средняя ширина строки в байтах. Влияет на использование памяти и пропускную способность сети.',
    'Join Type': 'Тип соединения: Inner (внутреннее), Left (левое), Right (правое), Full (полное), Semi (полусоединение), Anti (антисоединение).',
    'Strategy': 'Стратегия агрегации: Plain (обычная), Sorted (сортированная), Hashed (хешированная). Влияет на производительность GROUP BY.',
    'Index Name': 'Название используемого индекса. Показывает, что запрос использует индекс для оптимизации доступа к данным.',
    'Relation Name': 'Название таблицы, к которой обращается узел. Основная таблица для операций сканирования.',
    'Alias': 'Псевдоним таблицы, используемый в запросе. Помогает понять, какая таблица из запроса обрабатывается.',
    'Hash Cond': 'Условие для хеш-соединения. Показывает, по каким полям происходит соединение таблиц в Hash Join.',
    'Index Cond': 'Условие для использования индекса. Показывает, какие условия WHERE применяются к индексу.',
    'Filter': 'Дополнительное условие фильтрации, применяемое после сканирования. Условия, которые не могут использовать индекс.',
    'Sort Key': 'Поля, по которым происходит сортировка. Влияет на производительность ORDER BY и может требовать дополнительной памяти.',
    'Group Key': 'Поля, по которым происходит группировка в GROUP BY. Определяет, как данные группируются для агрегации.',
    'Scan Direction': 'Направление сканирования: Forward (вперед), Backward (назад). Важно для ORDER BY и курсоров.',
    'Parallel Aware': 'Может ли узел работать в параллельном режиме для ускорения выполнения. Использует несколько процессов.',
    'Async Capable': 'Может ли узел работать асинхронно. Важно для внешних данных и удаленных соединений.',
    'Inner Unique': 'Уникальность внутренней таблицы в соединении. Влияет на выбор алгоритма соединения и производительность.',
    'Partial Mode': 'Режим частичной агрегации: Simple (простой), Partial (частичный), Finalize (финализация). Для параллельных агрегаций.',
    'Planned Partitions': 'Количество запланированных для обработки партиций. Важно для партиционированных таблиц.',
    'Parent Relationship': 'Связь с родительским узлом: Outer (внешний), Inner (внутренний). Определяет порядок обработки в соединениях.',
    'Query Type': 'Тип SQL запроса: SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER. Влияет на доступные операции оптимизации.'
  };

  // Функция для получения цвета на основе типа узла
  const getNodeTypeColor = (nodeType) => {
    switch (nodeType) {
      case 'Index Scan':
      case 'Index Only Scan':
        return 'text-green-600 bg-green-50';
      case 'Seq Scan':
        return 'text-yellow-600 bg-yellow-50';
      case 'Hash Join':
      case 'Nested Loop':
      case 'Merge Join':
        return 'text-blue-600 bg-blue-50';
      case 'Sort':
        return 'text-purple-600 bg-purple-50';
      case 'Aggregate':
        return 'text-indigo-600 bg-indigo-50';
      case 'Limit':
        return 'text-orange-600 bg-orange-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  // Функция для получения иконки на основе типа узла
  const getNodeTypeIcon = (nodeType) => {
    switch (nodeType) {
      case 'Index Scan':
      case 'Index Only Scan':
        return Zap;
      case 'Seq Scan':
        return Database;
      case 'Hash Join':
      case 'Nested Loop':
      case 'Merge Join':
        return BarChart3;
      case 'Sort':
        return BarChart3;
      case 'Aggregate':
        return BarChart3;
      case 'Limit':
        return Clock;
      default:
        return Database;
    }
  };

  // Компонент для метрики плана
  const PlanMetricCard = ({ icon: Icon, title, value, unit, color, description, isLongText = false }) => (
    <div className={`p-4 rounded-lg ${color} relative group`}>
      <div className="flex items-center">
        <Icon className="w-5 h-5 mr-2 flex-shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{title}</p>
          <p className={`font-bold ${isLongText ? 'text-sm break-all whitespace-pre-wrap' : 'text-2xl'}`}>
            {value}{unit}
          </p>
        </div>
      </div>
      {description && (
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          <div className="bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg max-w-xs">
            {description}
          </div>
        </div>
      )}
    </div>
  );

  // Функция для получения иконки и цвета для любого поля
  const getFieldIconAndColor = (key, value) => {
    switch (key) {
      case 'Node Type':
        return { icon: getNodeTypeIcon(value), color: getNodeTypeColor(value) };
      case 'Total Cost':
        return { icon: BarChart3, color: 'text-red-600 bg-red-50' };
      case 'Startup Cost':
        return { icon: Clock, color: 'text-purple-600 bg-purple-50' };
      case 'Plan Rows':
        return { icon: Database, color: 'text-blue-600 bg-blue-50' };
      case 'Plan Width':
        return { icon: BarChart3, color: 'text-indigo-600 bg-indigo-50' };
      case 'Join Type':
        return { icon: BarChart3, color: 'text-cyan-600 bg-cyan-50' };
      case 'Strategy':
        return { icon: BarChart3, color: 'text-teal-600 bg-teal-50' };
      case 'Index Name':
        return { icon: Zap, color: 'text-green-600 bg-green-50' };
      case 'Relation Name':
        return { icon: Database, color: 'text-gray-600 bg-gray-50' };
      case 'Alias':
        return { icon: Database, color: 'text-gray-500 bg-gray-50' };
      case 'Hash Cond':
        return { icon: BarChart3, color: 'text-blue-500 bg-blue-50' };
      case 'Index Cond':
        return { icon: Zap, color: 'text-green-500 bg-green-50' };
      case 'Filter':
        return { icon: BarChart3, color: 'text-yellow-500 bg-yellow-50' };
      case 'Sort Key':
        return { icon: BarChart3, color: 'text-purple-500 bg-purple-50' };
      case 'Group Key':
        return { icon: BarChart3, color: 'text-indigo-500 bg-indigo-50' };
      case 'Scan Direction':
        return { icon: BarChart3, color: 'text-orange-500 bg-orange-50' };
      case 'Parallel Aware':
        return { icon: BarChart3, color: value ? 'text-green-500 bg-green-50' : 'text-gray-500 bg-gray-50' };
      case 'Async Capable':
        return { icon: BarChart3, color: value ? 'text-blue-500 bg-blue-50' : 'text-gray-500 bg-gray-50' };
      case 'Inner Unique':
        return { icon: BarChart3, color: value ? 'text-green-500 bg-green-50' : 'text-gray-500 bg-gray-50' };
      case 'Partial Mode':
        return { icon: BarChart3, color: 'text-teal-500 bg-teal-50' };
      case 'Planned Partitions':
        return { icon: Database, color: 'text-violet-500 bg-violet-50' };
      case 'Parent Relationship':
        return { icon: BarChart3, color: 'text-slate-500 bg-slate-50' };
      case 'Query Type':
        return { icon: Database, color: 'text-emerald-500 bg-emerald-50' };
      default:
        return { icon: BarChart3, color: 'text-gray-500 bg-gray-50' };
    }
  };

  // Основные метрики для отображения в квадратиках (всегда видны)
  const getPrimaryMetrics = (node) => {
    const primaryFields = ['Node Type', 'Total Cost', 'Plan Rows', 'Startup Cost'];
    return primaryFields
      .filter(key => node[key] !== undefined && node[key] !== null)
      .map(key => {
        const { icon, color } = getFieldIconAndColor(key, node[key]);
        return {
          icon,
          title: fieldNames[key] || key,
          value: node[key],
          unit: '',
          color,
          description: fieldDescriptions[key]
        };
      });
  };

  // Дополнительные метрики (скрыты по умолчанию)
  const getSecondaryMetrics = (node) => {
    const primaryFields = ['Node Type', 'Total Cost', 'Plan Rows', 'Startup Cost'];
    return Object.entries(node)
      .filter(([key, value]) => 
        key !== 'Plans' && 
        !primaryFields.includes(key) && 
        value !== undefined && 
        value !== null
      )
      .map(([key, value]) => {
        const { icon, color } = getFieldIconAndColor(key, value);
        let displayValue = value;
        if (Array.isArray(value)) {
          displayValue = value.join(', ');
        } else if (typeof value === 'boolean') {
          displayValue = value ? 'Да' : 'Нет';
        }
        
        // Определяем, является ли значение длинным текстом
        const isLongText = typeof displayValue === 'string' && displayValue.length > 20;
        
        return {
          icon,
          title: fieldNames[key] || key,
          value: displayValue,
          unit: '',
          color,
          description: fieldDescriptions[key] || `Описание для поля ${key}`,
          isLongText
        };
      });
  };

  const renderPlanNode = (node, depth = 0) => {
    const primaryMetrics = getPrimaryMetrics(node);
    const secondaryMetrics = getSecondaryMetrics(node);
    
    return (
      <div key={depth} className="mb-4">
        <div className="bg-gray-50 p-4 rounded-lg">
          {/* Основные метрики в виде квадратиков */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            {primaryMetrics.map((metric, index) => (
              <PlanMetricCard key={index} {...metric} />
            ))}
          </div>
          
          {/* Кнопка для показа дополнительных метрик */}
          {secondaryMetrics.length > 0 && (
            <div className="mb-4">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="flex items-center px-3 py-1 text-sm font-medium text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
              >
                {showDetails ? (
                  <>
                    <ChevronUp className="w-4 h-4 mr-1" />
                    Скрыть дополнительные метрики
                  </>
                ) : (
                  <>
                    <ChevronDown className="w-4 h-4 mr-1" />
                    Показать дополнительные метрики ({secondaryMetrics.length})
                  </>
                )}
              </button>
            </div>
          )}
          
          {/* Дополнительные метрики в виде квадратиков (показываются при разворачивании) */}
          {showDetails && secondaryMetrics.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 mb-4">
              {secondaryMetrics.map((metric, index) => (
                <PlanMetricCard key={index} {...metric} />
              ))}
            </div>
          )}

          {/* Рекурсивно отображаем вложенные планы */}
          {node['Plans'] && node['Plans'].length > 0 && (
            <div className="mt-4">
              <h5 className="text-md font-medium text-gray-700 mb-2">Вложенные планы:</h5>
              {node['Plans'].map((subPlan, index) => (
                <div key={index}>
                  {renderPlanNode(subPlan, depth + 1)}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="card">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">План выполнения запроса</h2>
      <div className="space-y-2">
        {renderPlanNode(plan)}
      </div>
    </div>
  );
};

export default ExecutionPlan;