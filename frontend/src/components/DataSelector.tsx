import React, { useState, useMemo, useEffect } from 'react';
import { Card, Select, Button, Typography, Space, Tag, Spin, message } from 'antd';
import { fetchMetadata } from '../services/api';
import type { TableMetadata } from '../types';

const { Title, Text } = Typography;

interface DataSelectorProps {
  onAnalyze: (tableName: string, columns: string[]) => void;
}

export const DataSelector: React.FC<DataSelectorProps> = ({ onAnalyze }) => {
  const [selectedTable, setSelectedTable] = useState<string | undefined>(undefined);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);

  const [metadata, setMetadata] = useState<TableMetadata[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        // request FastAPI
        const data = await fetchMetadata();
        setMetadata(data);
      } catch (error) {
        console.error("failed to fetch metadata:", error);
        message.error("failed to connect to the backend. Please ensure the FastAPI server is running and accessible.");
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);
  
  // 1. Find the current table's data based on the selected table name
  const currentTableData = useMemo(() => {
    return metadata.find(t => t.table_name === selectedTable);
  }, [selectedTable, metadata]);

  // 2. When the user switches tables, trigger this action
  const handleTableChange = (value: string) => {
    setSelectedTable(value);
    setSelectedColumns([]); // When switching tables, clear the columns selected from the previous table
  };

  // 3. When the user clicks the submit button
  const handleSubmit = () => {
    if (selectedTable && selectedColumns.length > 0) {
      onAnalyze(selectedTable, selectedColumns);
    }
    console.log("Data to be sent to the backend:", {
      table_name: selectedTable,
      selected_columns: selectedColumns
    });
    alert("Data has been recorded in the console (F12)! We will send it to the backend shortly.");
  };

  // ==========================================
  // UI Rendering
  // ==========================================
  return (
    <Card 
      title={<Title level={4} style={{ margin: 0 }}>🗄️ Data Selector</Title>} 
      style={{ boxShadow: '0 4px 12px rgba(0,0,0,0.05)', borderRadius: '8px' }}
    >
      <Spin spinning={isLoading} description="Loading metadata..."></Spin>
      <Space vertical size="large" style={{ width: '100%' }}>
        
        {/* Table Selection */}
        <div>
          <Text strong style={{ display: 'block', marginBottom: '8px' }}>1. Select Table</Text>
          <Select
            style={{ width: '100%' }}
            placeholder="Please select a table from the database..."
            value={selectedTable}
            onChange={handleTableChange}
            showSearch
            options={metadata.map(table => ({
              label: `📊 ${table.table_name}`,
              value: table.table_name
            }))}
          />
        </div>

        {/* Column Selection (only shown after a table is selected) */}
        {selectedTable && (
          <div>
            <Text strong style={{ display: 'block', marginBottom: '8px' }}>2. Select Columns</Text>
            <Select
              mode="multiple" // Allow multiple selections
              allowClear
              style={{ width: '100%' }}
              placeholder="Please select the columns you want to visualise (multiple selection supported)..."
              value={selectedColumns}
              onChange={(values) => setSelectedColumns(values)}
              options={currentTableData?.columns.map(col => ({
                label: (
                  <Space>
                    <span>{col.name}</span>
                    <Tag color={col.semantic_type === 'scalar' ? 'blue' : 'green'}>
                      {col.semantic_type}
                    </Tag>
                  </Space>
                ),
                value: col.name
              }))}
            />
          </div>
        )}

        {/* Bottom Buttons */}
        <Button 
          type="primary" 
          size="large" 
          disabled={!selectedTable || selectedColumns.length === 0}
          onClick={handleSubmit}
          style={{ width: '100%', marginTop: '10px' }}
        >
          Analyze Selected Dimensions 🚀
        </Button>

      </Space>
    </Card>
  );
};