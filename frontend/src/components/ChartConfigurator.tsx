import React, { useState, useMemo, useEffect } from 'react';
import { Card, Select, Typography, Space, Row, Col, Tag, Alert, Button, message, Spin, Switch } from 'antd';
import { fetchChartHtml } from '../services/api';
import type { RecommendationResponse } from '../types';

const { Title, Text } = Typography;

interface ChartConfiguratorProps {
  tableName: string;
  columns: string[];
  recommendations: RecommendationResponse;
}

export const ChartConfigurator: React.FC<ChartConfiguratorProps> = ({ tableName, columns, recommendations }) => {
  const [selectedGeom, setSelectedGeom] = useState<string | null>(null);
  const [selectedStat, setSelectedStat] = useState<string | null>(null);
  const [limitMethod, setLimitMethod] = useState<string>('top');
  const [logScale, setLogScale] = useState<boolean>(false);

  const [chartHtml, setChartHtml] = useState<string | null>(null);
  const [isDrawing, setIsDrawing] = useState<boolean>(false);

  // When the user selects a new table or columns, reset the Geom and Stat selections to null
  useEffect(() => {
    setSelectedGeom(null);
    setSelectedStat(null);
    setLogScale(false);
    setChartHtml(null);
  }, [recommendations]);

  // If the user has selected a Stat, find out which Geoms are valid
  const allowedGeoms = useMemo(() => {
    if (!selectedStat) return recommendations.available_geoms;
    return recommendations.valid_combinations
      .filter(combo => combo.stat === selectedStat)
      .map(combo => combo.geom);
  }, [selectedStat, recommendations]);

  // If the user has selected a Geom, find out which Stats are valid
  const allowedStats = useMemo(() => {
    if (!selectedGeom) return recommendations.available_stats;
    return recommendations.valid_combinations
      .filter(combo => combo.geom === selectedGeom)
      .map(combo => combo.stat);
  }, [selectedGeom, recommendations]);

  // If the user has selected both a Geom and a Stat, find the corresponding chart name
  const matchedChartName = useMemo(() => {
    if (selectedGeom && selectedStat) {
      const match = recommendations.valid_combinations.find(
        c => c.geom === selectedGeom && c.stat === selectedStat
      );
      return match ? match.chart_name : null;
    }
    return null;
  }, [selectedGeom, selectedStat, recommendations]);

  // Dropdown menus for Geom and Stat, with disabled options based on the current selection
  const geomOptions = recommendations.available_geoms.map(geom => ({
    label: `geom_${geom}`,
    value: geom,
    disabled: !allowedGeoms.includes(geom)
  }));

  const statOptions = recommendations.available_stats.map(stat => ({
    label: `stat_${stat}`,
    value: stat,
    disabled: !allowedStats.includes(stat)
  }));

  const handleGeneratePlot = async () => {
    if (!selectedGeom || !selectedStat) return;
    setIsDrawing(true);
    try {
      const res = await fetchChartHtml({
        table_name: tableName,
        selected_columns: columns,
        geom: selectedGeom,
        stat: selectedStat,
        limit_method: limitMethod,
        log_scale: logScale
      });
      setChartHtml(res.html);
      message.success("Plot generated successfully!");
    } catch (error) {
      message.error("Failed to generate plot. Please check the backend server.");
    } finally {
      setIsDrawing(false);
    }
  };

  return (
    <>
    <Card 
      title={<Title level={5} style={{ margin: 0 }}>Grammar of Graphics</Title>} 
      style={{ boxShadow: '0 4px 12px rgba(0,0,0,0.05)', borderRadius: '8px', marginTop: '20px' }}
      extra={<Tag color="purple">Pattern: {recommendations.pattern}</Tag>}
    >
      <Row gutter={24}>
        {/* Geom selection */}
        <Col span={12}>
          <Text strong style={{ display: 'block', marginBottom: '8px' }}>Geometry (Geom)</Text>
          <Select
            allowClear
            style={{ width: '100%' }}
            placeholder="Please select a Geom..."
            value={selectedGeom}
            onChange={(val) => setSelectedGeom(val)}
            options={geomOptions}
          />
        </Col>

        {/* Stat selection */}
        <Col span={12}>
          <Text strong style={{ display: 'block', marginBottom: '8px' }}>Statistical Transform (Stat)</Text>
          <Select
            allowClear
            style={{ width: '100%' }}
            placeholder="Please select a Stat..."
            value={selectedStat}
            onChange={(val) => setSelectedStat(val)}
            options={statOptions}
          />
        </Col>
      </Row>

      {matchedChartName && (
          <div style={{ marginTop: '20px', padding: '16px', backgroundColor: '#fafafa', borderRadius: '8px', border: '1px solid #e8e8e8' }}>
            <Row gutter={24}>
              {/* If it's a bar chart, show sampling method options */}
              <Col span={12}>
                {matchedChartName === "Bar Chart" ? (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text strong>Sampling Method</Text>
                    <Select 
                      value={limitMethod}
                      onChange={setLimitMethod}
                      style={{ width: '100%' }}
                      options={[
                        { label: 'Top 30', value: 'top' },
                        { label: 'Bottom 30', value: 'bottom' },
                        { label: 'Random 30', value: 'random' },
                        { label: 'Distributed 30', value: 'distributed' }
                      ]}
                    />
                  </Space>
                ) : (
                  <Text type="secondary">Current chart does not require row truncation</Text>
                )}
              </Col>

              {/* Scale toggle */}
              <Col span={12}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text strong>Data Axis Scaling</Text>
                  <Space style={{ marginTop: '4px' }}>
                    <Switch checked={logScale} onChange={setLogScale} />
                    <Text>Enable Log10 Scale</Text>
                  </Space>
                </Space>
              </Col>
            </Row>
          </div>
        )}

      {/* Bottom feedback area: Show chart name suggestion after user makes valid selections */}
      <div style={{ marginTop: '20px', minHeight: '40px' }}>
        {matchedChartName ? (
          <Alert 
            message={
              <Space>
                <span>Chart matched successfully:</span>
                <Text strong style={{ fontSize: '16px' }}>{matchedChartName}</Text>
              </Space>
            } 
            type="success" 
            showIcon 
          />
        ) : (selectedGeom || selectedStat) ? (
          <Alert message="Please select both a Geometry and a Statistical Transform to see the matched chart." type="info" showIcon />
        ) : null}
        <Button type="primary" disabled={!matchedChartName} loading={isDrawing} onClick={handleGeneratePlot}>
            Generate Plot
        </Button>
      </div>
    </Card>

    {chartHtml && (
        <Card style={{ marginTop: '20px', borderRadius: '8px', padding: 0, overflow: 'hidden' }}>
          <iframe 
            title="Interactive Chart"
            srcDoc={chartHtml} 
            sandbox="allow-scripts"
            style={{ width: '100%', height: '500px', border: 'none', display: 'block' }} 
          />
        </Card>
    )}
    </>
  );
};