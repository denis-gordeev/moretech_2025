import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
console.log('🔗 API_BASE_URL configured as:', API_BASE_URL);
console.log('🔗 process.env.REACT_APP_API_URL:', process.env.REACT_APP_API_URL);

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000, // 10 second timeout
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
  
  // Analyze query (full analysis)
  analyzeQuery: (query, databaseProfileId = null, databaseUrl = null) => 
    api.post('/analyze', { 
      query, 
      database_profile_id: databaseProfileId,
      database_url: databaseUrl 
    }),
  
  // Analyze execution plan only (fast response)
  analyzeExecutionPlan: (query, databaseProfileId = null, databaseUrl = null) => 
    api.post('/analyze/execution-plan', { 
      query, 
      database_profile_id: databaseProfileId,
      database_url: databaseUrl 
    }),
  
  // Analyze with LLM only (uses cached execution plan)
  analyzeWithLLM: (query, databaseProfileId = null, databaseUrl = null) => 
    api.post('/analyze/llm', { 
      query, 
      database_profile_id: databaseProfileId,
      database_url: databaseUrl 
    }),
  
  // Get database info
  getDatabaseInfo: () => api.get('/database/info'),
  
  // Test database connection
  testDatabaseConnection: (config) => api.post('/database/test', config),
  
  // Get example queries
  getExampleQueries: (databaseProfileId = null) => {
    const params = databaseProfileId ? { database_profile_id: databaseProfileId } : {};
    return api.get('/examples', { params });
  },
  
  // Database Profiles
  getDatabaseProfiles: () => api.get('/database/profiles'),
  createDatabaseProfile: (profile) => api.post('/database/profiles', profile),
  deleteDatabaseProfile: (profileId) => api.delete(`/database/profiles/${profileId}`),
  refreshDefaultProfile: () => api.post('/database/profiles/default'),
  
  // LLM Models
  getAvailableModels: () => api.get('/models'),
  switchModel: (modelName) => api.post('/models/switch', null, {
    params: { model_name: modelName }
  }),
};

export default api;
