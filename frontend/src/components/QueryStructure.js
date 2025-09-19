import React, { useState } from 'react';
import { Database, Table, Key, ChevronDown, ChevronRight, Eye, EyeOff } from 'lucide-react';

const QueryStructure = ({ query }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!query || !query.trim()) {
    return null;
  }

  // Простой парсер SQL для извлечения структуры запроса
  const parseQueryStructure = (sqlQuery) => {
    const structure = {
      tables: [],
      fields: [],
      joins: [],
      hasWhere: false,
      hasGroupBy: false,
      hasOrderBy: false,
      hasLimit: false
    };

    const query = sqlQuery.toLowerCase().trim();

    // Извлекаем таблицы из FROM и JOIN
    const fromMatch = query.match(/from\s+([^,\s]+(?:\s+[^,\s]+)*)/g);
    if (fromMatch) {
      fromMatch.forEach(match => {
        const table = match.replace(/from\s+/i, '').trim();
        if (table && !structure.tables.includes(table)) {
          structure.tables.push(table);
        }
      });
    }

    // Извлекаем JOIN'ы
    const joinMatches = query.match(/(?:inner\s+|left\s+|right\s+|full\s+)?join\s+([^\s]+)/gi);
    if (joinMatches) {
      joinMatches.forEach(match => {
        const table = match.replace(/(?:inner\s+|left\s+|right\s+|full\s+)?join\s+/i, '').trim();
        if (table && !structure.tables.includes(table)) {
          structure.tables.push(table);
        }
        structure.joins.push(match.trim());
      });
    }

    // Извлекаем поля из SELECT
    const selectMatch = query.match(/select\s+(.*?)\s+from/i);
    if (selectMatch) {
      const fieldsStr = selectMatch[1];
      if (fieldsStr !== '*') {
        const fields = fieldsStr.split(',').map(field => field.trim());
        structure.fields = fields.filter(field => field && !field.includes('('));
      } else {
        structure.fields = ['* (все поля)'];
      }
    }

    // Проверяем наличие различных клаузул
    structure.hasWhere = query.includes('where');
    structure.hasGroupBy = query.includes('group by');
    structure.hasOrderBy = query.includes('order by');
    structure.hasLimit = query.includes('limit');

    return structure;
  };

  const structure = parseQueryStructure(query);

  const getTableIcon = (table) => {
    if (table.includes('_')) return <Table className="w-4 h-4" />;
    return <Database className="w-4 h-4" />;
  };

  const getJoinType = (join) => {
    if (join.toLowerCase().includes('inner')) return 'INNER JOIN';
    if (join.toLowerCase().includes('left')) return 'LEFT JOIN';
    if (join.toLowerCase().includes('right')) return 'RIGHT JOIN';
    if (join.toLowerCase().includes('full')) return 'FULL JOIN';
    return 'JOIN';
  };

  return (
    <div className="card">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50 rounded-lg transition-colors"
      >
        <div className="flex items-center">
          <Database className="w-5 h-5 mr-2 text-blue-600" />
          <h2 className="text-xl font-semibold text-gray-900">
            Структура запроса
          </h2>
        </div>
        <div className="flex items-center">
          {isExpanded ? (
            <>
              <EyeOff className="w-4 h-4 mr-2 text-gray-500" />
              <ChevronDown className="w-5 h-5 text-gray-500" />
            </>
          ) : (
            <>
              <Eye className="w-4 h-4 mr-2 text-gray-500" />
              <ChevronRight className="w-5 h-5 text-gray-500" />
            </>
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 space-y-4">
          {/* Таблицы */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
              <Database className="w-4 h-4 mr-1" />
              Используемые таблицы ({structure.tables.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {structure.tables.map((table, index) => (
                <div
                  key={index}
                  className="flex items-center p-2 bg-blue-50 border border-blue-200 rounded-lg"
                >
                  {getTableIcon(table)}
                  <span className="ml-2 text-sm font-mono text-blue-800">
                    {table}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Поля */}
          {structure.fields.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Key className="w-4 h-4 mr-1" />
                Выбранные поля ({structure.fields.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {structure.fields.slice(0, 10).map((field, index) => (
                  <div
                    key={index}
                    className="flex items-center p-2 bg-green-50 border border-green-200 rounded-lg"
                  >
                    <Key className="w-4 h-4 text-green-600" />
                    <span className="ml-2 text-sm font-mono text-green-800">
                      {field}
                    </span>
                  </div>
                ))}
                {structure.fields.length > 10 && (
                  <div className="col-span-full text-sm text-gray-500 italic">
                    ... и еще {structure.fields.length - 10} полей
                  </div>
                )}
              </div>
            </div>
          )}

          {/* JOIN'ы */}
          {structure.joins.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                <Table className="w-4 h-4 mr-1" />
                Соединения таблиц ({structure.joins.length})
              </h3>
              <div className="space-y-2">
                {structure.joins.map((join, index) => (
                  <div
                    key={index}
                    className="flex items-center p-2 bg-purple-50 border border-purple-200 rounded-lg"
                  >
                    <Table className="w-4 h-4 text-purple-600" />
                    <span className="ml-2 text-sm font-mono text-purple-800">
                      {getJoinType(join)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Клаузулы */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-2">
              Используемые клаузулы
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { name: 'WHERE', present: structure.hasWhere, color: 'yellow' },
                { name: 'GROUP BY', present: structure.hasGroupBy, color: 'orange' },
                { name: 'ORDER BY', present: structure.hasOrderBy, color: 'red' },
                { name: 'LIMIT', present: structure.hasLimit, color: 'indigo' }
              ].map((clause) => (
                <div
                  key={clause.name}
                  className={`p-2 rounded-lg border text-center text-sm font-medium ${
                    clause.present
                      ? `bg-${clause.color}-50 border-${clause.color}-200 text-${clause.color}-800`
                      : 'bg-gray-50 border-gray-200 text-gray-500'
                  }`}
                >
                  {clause.name}
                  {clause.present && (
                    <div className="text-xs mt-1">✓</div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Статистика */}
          <div className="pt-2 border-t border-gray-200">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="text-center">
                <div className="font-semibold text-blue-600">{structure.tables.length}</div>
                <div className="text-gray-500">Таблиц</div>
              </div>
              <div className="text-center">
                <div className="font-semibold text-green-600">{structure.fields.length}</div>
                <div className="text-gray-500">Полей</div>
              </div>
              <div className="text-center">
                <div className="font-semibold text-purple-600">{structure.joins.length}</div>
                <div className="text-gray-500">JOIN'ов</div>
              </div>
              <div className="text-center">
                <div className="font-semibold text-orange-600">
                  {[structure.hasWhere, structure.hasGroupBy, structure.hasOrderBy, structure.hasLimit].filter(Boolean).length}
                </div>
                <div className="text-gray-500">Клаузул</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QueryStructure;
