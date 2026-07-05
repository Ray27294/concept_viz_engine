import { Button, Typography, Layout } from 'antd';

const { Title, Paragraph } = Typography;
const { Content } = Layout;

function App() {
  return (
    <Layout style={{ minHeight: '100vh', backgroundColor: '#f5f5f5' }}>
      <Content style={{ padding: '50px', maxWidth: '800px', margin: '0 auto' }}>
        <Title level={2}>📊 Concept Viz Engine</Title>
        <Paragraph>
          Ant Design is a popular React UI library that provides a set of high-quality components.
        </Paragraph>
        <Button type="primary" size="large">
          Launch! 🚀
        </Button>
      </Content>
    </Layout>
  );
};

export default App;
