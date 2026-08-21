import { Typography, Layout, Row, Col, message, Spin } from 'antd';
import { DataSelector } from './components/DataSelector';
import { DataPreview } from './components/DataPreview';
import { ChartConfigurator } from './components/ChartConfigurator';
import { useEffect, useState } from 'react';
import { fetchRecommendations } from './services/api';
import { DatabaseConnector } from './components/DatabaseConnector';
import type { RecommendationResponse } from './types';

const { Title, Paragraph, Text } = Typography;
const { Content } = Layout;

function App() {
  const [isDbConnected, setIsDbConnected] = useState<boolean>(false);
  const [analysisConfig, setAnalysisConfig] = useState<{table: string, cols: string[], scalarCols: string[]} | null>(null);

  const [recommendations, setRecommendations] = useState<RecommendationResponse | null>(null);
  const [isRecommending, setIsRecommending] = useState<boolean>(false);

  const handleAnalyze = (tableName: string, columns: string[], scalarColumns: string[]) => {
    setAnalysisConfig({ table: tableName, cols: columns, scalarCols: scalarColumns });
  };

  useEffect(() => {
    if (analysisConfig) {
      const getRecommendations = async () => {
        setIsRecommending(true);
        try {
          const res = await fetchRecommendations({
            table_name: analysisConfig.table,
            selected_columns: analysisConfig.cols
          });
          setRecommendations(res);
        } catch (error) {
          console.error("Failed to fetch recommendations:", error);
          message.error('Failed to fetch recommendations. Please check the backend server.');
        } finally {
          setIsRecommending(false);
        }
      };

      getRecommendations();
    }
  }, [analysisConfig]);

  if (!isDbConnected) {
    return <DatabaseConnector onConnected={() => setIsDbConnected(true)} />;
  }
  
  return (
    <Layout style={{ minHeight: '100vh', backgroundColor: '#f0f2f5' }}>
      <Content style={{ padding: '40px 50px', maxWidth: '1400px', margin: '0 auto', width: '100%' }}>

        <div style={{ marginBottom: '40px', textAlign: 'center' }}>
          <Title level={2}>📊 Concept Viz Engine</Title>
        </div>

        <Row gutter={24}>
          <Col xs={24} lg={8}>
            <DataSelector onAnalyze={handleAnalyze} />
          </Col>
          
          <Col xs={24} lg={16}>
            {!analysisConfig ? (
               <div style={{ height: '100%', minHeight: '300px', backgroundColor: '#fff', borderRadius: '8px', border: '1px dashed #d9d9d9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                 <Typography.Text type="secondary">👈 Please select a table and columns to visualise...</Typography.Text>
               </div>
            ) : (
               <DataPreview tableName={analysisConfig.table} columns={analysisConfig.cols} />
            )}
          </Col>
        </Row>

        {analysisConfig && (
          <Row gutter={24} style={{ marginTop: '24px' }}>
            <Col span={24}>
              <Spin spinning={isRecommending} description="Waiting for recommendation engine feedback...">
                {recommendations ? (
                  <ChartConfigurator tableName={analysisConfig.table} columns={analysisConfig.cols} scalarColumns={analysisConfig.scalarCols} recommendations={recommendations} />
                ) : (
                  <div style={{ padding: '40px', textAlign: 'center', backgroundColor: '#fff', borderRadius: '8px' }}>
                    <Text type="secondary">Waiting for recommendation engine feedback...</Text>
                  </div>
                )}
              </Spin>
            </Col>
          </Row>
        )}

      </Content>
    </Layout>
  );
};

export default App;
