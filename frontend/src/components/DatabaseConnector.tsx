import React, { useState } from 'react';
import { Card, Form, Input, Button, Typography, message } from 'antd';
import { DatabaseOutlined, LockOutlined, UserOutlined, GlobalOutlined, CodeOutlined } from '@ant-design/icons';
import { connectDatabase, type DBConnectionParams } from '../services/api';

const { Title, Text } = Typography;

interface DatabaseConnectorProps {
  onConnected: () => void;
}

export const DatabaseConnector: React.FC<DatabaseConnectorProps> = ({ onConnected }) => {
  const [loading, setLoading] = useState(false);

  const handleConnect = async (values: DBConnectionParams) => {
    setLoading(true);
    try {
      await connectDatabase(values);
      message.success(`Successfully connected to ${values.database}!`);
      onConnected();
    } catch (error: any) {
      message.error(error.message || 'Database connection failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)'
    }}>
      <Card 
        style={{ 
          width: 450, 
          boxShadow: '0 20px 40px rgba(0,0,0,0.1)', 
          borderRadius: '16px',
          padding: '20px' 
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
          <Title level={2} style={{ margin: 0 }}>📊 Concept Viz</Title>
          <Text type="secondary">Connect to your PostgreSQL Database</Text>
        </div>

        <Form layout="vertical" onFinish={handleConnect} initialValues={{ port: '5432' }}>
          
          <Form.Item name="host" rules={[{ required: true, message: 'Host is required' }]}>
            <Input prefix={<GlobalOutlined />} placeholder="Host" size="large" />
          </Form.Item>

          <Form.Item name="port" rules={[{ required: true, message: 'Port is required' }]}>
            <Input prefix={<CodeOutlined />} placeholder="Port (Default: 5432)" size="large" />
          </Form.Item>

          <Form.Item name="database" rules={[{ required: true, message: 'Database name is required' }]}>
            <Input prefix={<DatabaseOutlined />} placeholder="Database Name" size="large" />
          </Form.Item>

          <Form.Item name="username" rules={[{ required: true, message: 'Username is required' }]}>
            <Input prefix={<UserOutlined />} placeholder="Username" size="large" />
          </Form.Item>

          <Form.Item name="password">
            <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
          </Form.Item>

          <Form.Item style={{ marginTop: '30px' }}>
            <Button type="primary" htmlType="submit" size="large" block loading={loading} style={{ height: '48px', fontSize: '16px' }}>
              Connect
            </Button>
          </Form.Item>

        </Form>
      </Card>
    </div>
  );
};