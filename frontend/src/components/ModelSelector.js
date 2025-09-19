import React, { useState, useEffect } from 'react';
import { ChevronDown, Check, Cpu } from 'lucide-react';
import { queryAnalyzerAPI } from '../services/api';

const ModelSelector = ({ onModelChange }) => {
  const [models, setModels] = useState([]);
  const [currentModel, setCurrentModel] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await queryAnalyzerAPI.getAvailableModels();
      setModels(response.data.models);
      setCurrentModel(response.data.current_model);
    } catch (error) {
      console.error('Failed to load models:', error);
      setError('Не удалось загрузить список моделей');
    } finally {
      setIsLoading(false);
    }
  };

  const handleModelSelect = async (modelName) => {
    try {
      setIsLoading(true);
      setError(null);
      await queryAnalyzerAPI.switchModel(modelName);
      setCurrentModel(modelName);
      setIsOpen(false);
      if (onModelChange) {
        onModelChange(modelName);
      }
    } catch (error) {
      console.error('Failed to switch model:', error);
      setError('Не удалось переключить модель');
    } finally {
      setIsLoading(false);
    }
  };

  const currentModelInfo = models.find(m => m.name === currentModel);

  return (
    <div className="relative">
      <div className="flex items-center space-x-2">
        <Cpu className="w-4 h-4 text-gray-500" />
        <span className="text-sm text-gray-600">Модель:</span>
      </div>
      
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          disabled={isLoading}
          className="flex items-center justify-between w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="flex items-center space-x-2">
            <span className="text-gray-900">
              {currentModelInfo ? currentModelInfo.name : 'Загрузка...'}
            </span>
            {currentModelInfo && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                {currentModelInfo.model}
              </span>
            )}
          </div>
          <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg">
            <div className="py-1">
              {models.map((model) => (
                <button
                  key={model.name}
                  onClick={() => handleModelSelect(model.name)}
                  className="flex items-center justify-between w-full px-3 py-2 text-sm text-left hover:bg-gray-50 focus:outline-none focus:bg-gray-50"
                >
                  <div className="flex items-center space-x-2">
                    <span className="text-gray-900">{model.name}</span>
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                      {model.model}
                    </span>
                  </div>
                  {model.is_current && (
                    <Check className="w-4 h-4 text-primary-600" />
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-2 text-xs text-red-600">
          {error}
        </div>
      )}
    </div>
  );
};

export default ModelSelector;
