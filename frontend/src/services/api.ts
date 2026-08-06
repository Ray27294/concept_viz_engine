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

export interface PlotRequest {
  table_name: string;
  selected_columns: string[];
  geom: string;
  stat: string;
  limit_method?: string; // Optional property for limit method
  limit_count?: number; // Optional property for limit count
  log_scale?: boolean; // Optional property for log scale
  chart_name?: string; // Optional property for chart name
}

export interface PlotResponse {
  html: string;
}

export const fetchChartHtml = async (
  requestData: PlotRequest
): Promise<PlotResponse> => {
  const response = await apiClient.post<PlotResponse>('/plot/generate', requestData);
  return response.data;
};