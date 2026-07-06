import { Typography, Layout, Row, Col } from 'antd';
import { DataSelector } from './components/DataSelector';

const { Title, Paragraph } = Typography;
const { Content } = Layout;

function App() {
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
            <DataSelector />
          </Col>
          
          <Col xs={24} md={14} lg={16}>
            <div style={{ 
              height: '100%', 
              minHeight: '400px', 
              backgroundColor: '#fff', 
              borderRadius: '8px', 
              border: '1px dashed #d9d9d9',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Typography.Text type="secondary">
                👈 Select a table and columns to visualise
              </Typography.Text>
            </div>
          </Col>
        </Row>

      </Content>
    </Layout>
  );
};

export default App;
