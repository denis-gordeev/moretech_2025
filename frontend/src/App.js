import React, { useState, useEffect } from 'react';
import { Database, BarChart3, AlertTriangle } from 'lucide-react';
import QueryEditor from './components/QueryEditor';
import ExecutionPlan from './components/ExecutionPlan';
import ResourceMetrics from './components/ResourceMetrics';
import Recommendations from './components/Recommendations';
import Warnings from './components/Warnings';
import HealthStatus from './components/HealthStatus';
import RewrittenQuery from './components/RewrittenQuery';
import ModelSelector from './components/ModelSelector';
import DatabaseProfiles from './components/DatabaseProfiles';
import { queryAnalyzerAPI } from './services/api';

function App() {
  const [query, setQuery] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [examples, setExamples] = useState([]);
  const [activeTab, setActiveTab] = useState('query');
  const [currentModel, setCurrentModel] = useState(null);
  const [selectedDatabase, setSelectedDatabase] = useState(null);

  // Загружаем примеры запросов при инициализации
  useEffect(() => {
    const loadExamples = async () => {
      try {
        const response = await queryAnalyzerAPI.getExampleQueries();
        setExamples(response.data.examples);
      } catch (error) {
        console.error('Failed to load examples:', error);
      }
    };
    loadExamples();
  }, []);

  const handleAnalyze = async () => {
    if (!query.trim()) {
      setError('Пожалуйста, введите SQL запрос для анализа');
      return;
    }

    setIsLoading(true);
    setError(null);
    setAnalysis(null);

    try {
      const response = await queryAnalyzerAPI.analyzeQuery(query, selectedDatabase?.id);
      setAnalysis(response.data);
      setActiveTab('results');
    } catch (error) {
      console.error('Analysis failed:', error);
      setError(
        error.response?.data?.detail || 
        'Произошла ошибка при анализе запроса. Проверьте подключение к серверу.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleQueryChange = (newQuery) => {
    setQuery(newQuery);
    setError(null);
  };

  const handleModelChange = (modelName) => {
    setCurrentModel(modelName);
    // Очищаем предыдущий анализ при смене модели
    setAnalysis(null);
    setError(null);
  };

  const tabs = [
    { id: 'query', label: 'Запрос', icon: Database },
    { id: 'results', label: 'Результаты', icon: BarChart3, disabled: !analysis },
    { id: 'health', label: 'Статус', icon: AlertTriangle },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <Database className="w-8 h-8 text-primary-600 mr-3" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  PostgreSQL Query Analyzer
                </h1>
                <p className="text-sm text-gray-500">
                  Умный анализ SQL-запросов с помощью LLM
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <ModelSelector onModelChange={handleModelChange} />
              <div className="text-sm text-gray-500">
                v1.0.0
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  disabled={tab.disabled}
                  className={`flex items-center py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600'
                      : tab.disabled
                      ? 'border-transparent text-gray-400 cursor-not-allowed'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex">
              <AlertTriangle className="w-5 h-5 text-red-600 mr-2 mt-0.5" />
              <div>
                <h3 className="text-sm font-medium text-red-800">Ошибка анализа</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Query Tab */}
        {activeTab === 'query' && (
          <div className="space-y-6">
            <DatabaseProfiles 
              onProfileSelect={setSelectedDatabase}
              selectedProfile={selectedDatabase}
            />
            
            <QueryEditor
              query={query}
              onQueryChange={handleQueryChange}
              onAnalyze={handleAnalyze}
              isLoading={isLoading}
              examples={examples}
            />
          </div>
        )}

        {/* Results Tab */}
        {activeTab === 'results' && analysis && (
          <div className="space-y-6">
            {/* Rewritten Query */}
            <RewrittenQuery 
              rewrittenQuery={analysis.rewritten_query} 
              originalQuery={analysis.query} 
            />

            {/* Execution Plan */}
            <ExecutionPlan plan={analysis.execution_plan?.plan_json} />

            {/* Resource Metrics */}
            <ResourceMetrics resourceMetrics={analysis.resource_metrics} />

            {/* Recommendations */}
            <Recommendations recommendations={analysis.recommendations} />

            {/* Warnings */}
            <Warnings warnings={analysis.warnings} />

            {/* Analysis Info */}
            <div className="card">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Информация об анализе
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium text-gray-700">Время анализа:</span>
                  <span className="ml-2 text-gray-600">
                    {new Date(analysis.analysis_timestamp).toLocaleString('ru-RU')}
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Длина запроса:</span>
                  <span className="ml-2 text-gray-600">
                    {analysis.query.length} символов
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Рекомендаций найдено:</span>
                  <span className="ml-2 text-gray-600">
                    {analysis.recommendations.length}
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Предупреждений:</span>
                  <span className="ml-2 text-gray-600">
                    {analysis.warnings.length}
                  </span>
                </div>
                <div>
                  <span className="font-medium text-gray-700">Исправленный запрос:</span>
                  <span className="ml-2 text-gray-600">
                    {analysis.rewritten_query && analysis.rewritten_query.trim() !== '' ? 'Да' : 'Нет'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Health Tab */}
        {activeTab === 'health' && (
          <div className="space-y-6">
            <HealthStatus />
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              © 2024 PostgreSQL Query Analyzer. Создано для MoreTech.
            </div>
            <div className="flex items-center space-x-4 text-sm text-gray-500">
              <span>Powered by LLM</span>
              <span>•</span>
              <span>PostgreSQL 15+</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
