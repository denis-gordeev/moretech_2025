import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const queryAnalyzerAPI = {
  // Health check
  healthCheck: () => api.get('/health'),
  
  // Analyze query
  analyzeQuery: (query, databaseProfileId = null, databaseUrl = null) => 
    api.post('/analyze', { 
      query, 
      database_profile_id: databaseProfileId,
      database_url: databaseUrl 
    }),
  
  // Get database info
  getDatabaseInfo: () => api.get('/database/info'),
  
  // Test database connection
  testDatabaseConnection: (config) => api.post('/database/test', config),
  
  // Get example queries
  getExampleQueries: () => api.get('/examples'),
  
  // LLM Models
  getAvailableModels: () => api.get('/models'),
  switchModel: (modelName) => api.post('/models/switch', null, {
    params: { model_name: modelName }
  }),
};

export default api;
