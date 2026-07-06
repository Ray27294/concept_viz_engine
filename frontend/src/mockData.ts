import type { TableMetadata } from './types';

export const MOCK_MONDIAL_DATA: TableMetadata[] = [
  {
    table_name: "country",
    columns: [
      { name: "name", type: "VARCHAR", semantic_type: "lexical" },
      { name: "code", type: "VARCHAR", semantic_type: "lexical" },
      { name: "capital", type: "VARCHAR", semantic_type: "lexical" },
      { name: "population", type: "INT", semantic_type: "scalar" },
      { name: "area", type: "FLOAT", semantic_type: "scalar" },
      { name: "gdp", type: "NUMERIC", semantic_type: "scalar" }
    ]
  },
  {
    table_name: "city",
    columns: [
      { name: "name", type: "VARCHAR", semantic_type: "lexical" },
      { name: "country", type: "VARCHAR", semantic_type: "lexical" },
      { name: "population", type: "INT", semantic_type: "scalar" },
      { name: "longitude", type: "NUMERIC", semantic_type: "scalar" },
      { name: "latitude", type: "NUMERIC", semantic_type: "scalar" }
    ]
  }
];