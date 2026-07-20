import React, { useEffect, useState } from 'react';
import { Card, Table, Typography, message } from 'antd';
import { fetchDataPreview } from '../services/api';

const { Title, Text } = Typography;

interface DataPreviewProps {
  tableName: string;
  columns: string[];
}

export const DataPreview: React.FC<DataPreviewProps> = ({ tableName, columns }) => {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    // As soon as the tableName or columns change, fetch the data preview
    const loadPreview = async () => {
      setLoading(true);
      try {
        const result = await fetchDataPreview({
          table_name: tableName,
          selected_columns: columns,
          limit: 5 // Only fetch the first 5 rows
        });
        
        // Add a unique key to each row, which is a requirement for React to render lists
        const rowsWithKey = result.rows.map((row, index) => ({
          key: index,
          ...row
        }));
        
        setData(rowsWithKey);
      } catch (error) {
        message.error('Failed to fetch data preview. Please check the backend server.');
      } finally {
        setLoading(false);
      }
    };

    if (tableName && columns.length > 0) {
      loadPreview();
    }
  }, [tableName, columns]); // Dependency items: these values change, triggering the request

  // Construct the header format needed by Ant Design Table
  const tableColumns = columns.map(col => ({
    title: col,
    dataIndex: col, // Key name in the data
    key: col,
  }));

  return (
    <Card 
      title={<Title level={5} style={{ margin: 0 }}>Data Preview (Top 5 Rows)</Title>} 
      style={{ boxShadow: '0 4px 12px rgba(0,0,0,0.05)', borderRadius: '8px', marginBottom: '20px' }}
    >
      <Text type="secondary" style={{ display: 'block', marginBottom: '16px' }}>
        Current Selection: <Text strong>{tableName}</Text> Table
      </Text>
      
      <Table 
        columns={tableColumns} 
        dataSource={data} 
        loading={loading}
        pagination={false} // Only 5 rows, no need for pagination
        size="small"
        bordered
      />
    </Card>
  );
};