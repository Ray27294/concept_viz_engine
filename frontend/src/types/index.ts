export interface Column {
  name: string;
  type: string;
  semantic_type: string;
}

export interface TableMetadata {
  table_name: string;
  columns: Column[];
  // Frontend does not need primary_key and foreign_keys.
}

export interface RecommendRequest {
  table_name: string;
  selected_columns: string[];
}

export interface ChartCombination {
  chart_name: string;
  geom: string;
  stat: string;
}

export interface RecommendationResponse {
  pattern: string;
  available_geoms: string[];
  available_stats: string[];
  valid_combinations: ChartCombination[];
}