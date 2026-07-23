import axios from 'axios';
import type { TableMetadata, RecommendRequest, RecommendationResponse, DataPreviewRequest, DataPreviewResponse } from '../types';

const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 10000,
});

export const fetchMetadata = async (): Promise<TableMetadata[]> => {
  const response = await apiClient.get<TableMetadata[]>('/metadata');
  return response.data;
};

export const fetchDataPreview = async (
  requestData: DataPreviewRequest
): Promise<DataPreviewResponse> => {
  const response = await apiClient.post<DataPreviewResponse>('/data/preview', requestData);
  return response.data;
};

export const fetchRecommendations = async (
  requestData: RecommendRequest
): Promise<RecommendationResponse> => {
  const response = await apiClient.post<RecommendationResponse>('/recommend/', requestData);
  return response.data;
};