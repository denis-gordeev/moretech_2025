import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

// Mock the API service
jest.mock('./services/api', () => ({
  queryAnalyzerAPI: {
    healthCheck: jest.fn(),
    analyzeQuery: jest.fn(),
    getDatabaseInfo: jest.fn(),
    testDatabaseConnection: jest.fn(),
    getExampleQueries: jest.fn().mockResolvedValue({
      data: {
        examples: [
          {
            name: 'Test Query',
            query: 'SELECT * FROM users',
            description: 'Test description'
          }
        ]
      }
    })
  }
}));

test('renders PostgreSQL Query Analyzer title', () => {
  render(<App />);
  const titleElement = screen.getByText(/PostgreSQL Query Analyzer/i);
  expect(titleElement).toBeInTheDocument();
});

test('renders query editor', () => {
  render(<App />);
  const queryEditor = screen.getByPlaceholderText(/Введите SQL запрос для анализа/i);
  expect(queryEditor).toBeInTheDocument();
});

test('renders analyze button', () => {
  render(<App />);
  const analyzeButton = screen.getByText(/Анализировать запрос/i);
  expect(analyzeButton).toBeInTheDocument();
});
