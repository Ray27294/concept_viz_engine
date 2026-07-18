import axios from 'axios';
import type { TableMetadata, RecommendRequest, RecommendationResponse } from '../types';

const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 10000,
});

export const fetchMetadata = async (): Promise<TableMetadata[]> => {
  const response = await apiClient.get<TableMetadata[]>('/metadata');
  return response.data;
};