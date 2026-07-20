import { Typography, Layout, Row, Col } from 'antd';
import { DataSelector } from './components/DataSelector';
import { DataPreview } from './components/DataPreview';
import { useState } from 'react';

const { Title, Paragraph } = Typography;
const { Content } = Layout;

function App() {
  const [analysisConfig, setAnalysisConfig] = useState<{table: string, cols: string[]} | null>(null);

  const handleAnalyze = (tableName: string, columns: string[]) => {
    setAnalysisConfig({ table: tableName, cols: columns });
  };
  
  return (
    <Layout style={{ minHeight: '100vh', backgroundColor: '#f0f2f5' }}>
      <Content style={{ padding: '40px 50px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>

        <div style={{ marginBottom: '40px', textAlign: 'center' }}>
          <Title level={2}>📊 Concept Viz Engine</Title>
          <Paragraph type="secondary">
          </Paragraph>
        </div>

        <Row gutter={24}>
          <Col xs={24} md={10} lg={8}>
            <DataSelector onAnalyze={handleAnalyze} />
          </Col>
          
          <Col xs={24} md={14} lg={16}>
            {!analysisConfig ? (
               <div style={{ height: '400px', backgroundColor: '#fff', borderRadius: '8px', border: '1px dashed #d9d9d9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                 <Typography.Text type="secondary">👈 Please select a table and columns to visualise...</Typography.Text>
               </div>
            ) : (
               <DataPreview tableName={analysisConfig.table} columns={analysisConfig.cols} />
            )}
          </Col>
        </Row>

      </Content>
    </Layout>
  );
};

export default App;
