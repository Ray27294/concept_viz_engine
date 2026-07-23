import React, { useState, useMemo, useEffect } from 'react';
import { Card, Select, Typography, Space, Row, Col, Tag, Alert } from 'antd';
import type { RecommendationResponse } from '../types';

const { Title, Text } = Typography;

interface ChartConfiguratorProps {
  recommendations: RecommendationResponse;
}

export const ChartConfigurator: React.FC<ChartConfiguratorProps> = ({ recommendations }) => {
  const [selectedGeom, setSelectedGeom] = useState<string | null>(null);
  const [selectedStat, setSelectedStat] = useState<string | null>(null);

  // When the user selects a new table or columns, reset the Geom and Stat selections to null
  useEffect(() => {
    setSelectedGeom(null);
    setSelectedStat(null);
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

  return (
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
      </div>
    </Card>
  );
};