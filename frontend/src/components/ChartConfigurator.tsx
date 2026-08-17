import React, { useState, useMemo, useEffect } from 'react';
import { Card, Select, Typography, Space, Row, Col, Tag, Alert, Button, message, Switch, InputNumber } from 'antd';
import { fetchChartHtml, fetchMetadata, type DimensionLookup } from '../services/api';
import type { RecommendationResponse, TableMetadata } from '../types';

const { Title, Text } = Typography;

interface ChartConfiguratorProps {
  tableName: string;
  columns: string[];
  scalarColumns: string[];
  recommendations: RecommendationResponse;
}

export const ChartConfigurator: React.FC<ChartConfiguratorProps> = ({ tableName, columns, scalarColumns, recommendations }) => {
  const [selectedGeom, setSelectedGeom] = useState<string | null>(null);
  const [selectedStat, setSelectedStat] = useState<string | null>(null);
  const [limitMethod, setLimitMethod] = useState<string>('top');
  const [limitCount, setLimitCount] = useState<number>(30);
  const [logScale, setLogScale] = useState<boolean>(false);

  const [chartHtml, setChartHtml] = useState<string | null>(null);
  const [chartCode, setChartCode] = useState<string | null>(null);
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [filterColumn, setFilterColumn] = useState<string | null>(null);
  const [filterOperator, setFilterOperator] = useState<string>('>');
  const [filterValue, setFilterValue] = useState<number | null>(null);
  const [xAxisCol, setXAxisCol] = useState<string | null>(null);
  const [lookups, setLookups] = useState<DimensionLookup[]>([]);
  const [dbMetadata, setDbMetadata] = useState<TableMetadata[]>([]);
  const [groupOthers, setGroupOthers] = useState<boolean>(false);

  // Metadata fetching for alternative key lookup options
  useEffect(() => {
    const loadMeta = async () => {
      try {
        const data = await fetchMetadata();
        setDbMetadata(data);
      } catch (error) {
        console.error("Failed to fetch metadata for dimension lookup options");
      }
    };
    loadMeta();
  }, []);

  // Functions to manage alternative key lookups
  const addLookup = () => {
    setLookups([...lookups, { local_column: '', target_table: '', target_join_key: '', target_display_col: '' }]);
  };
  const removeLookup = (index: number) => {
    setLookups(lookups.filter((_, i) => i !== index));
  };
  const updateLookup = (index: number, field: keyof DimensionLookup, value: string) => {
    const newLookups = [...lookups];
    newLookups[index][field] = value;
    setLookups(newLookups);
  };

  const handleTargetTableChange = (index: number, newTable: string) => {
    const newLookups = [...lookups];
    newLookups[index].target_table = newTable;
    newLookups[index].target_join_key = '';
    newLookups[index].target_display_col = '';
    setLookups(newLookups);
  };

  // When the user selects a new table or columns, reset the Geom and Stat selections to null
  useEffect(() => {
    setSelectedGeom(null);
    setSelectedStat(null);
    setLogScale(false);
    setChartHtml(null);
    setChartCode(null);
    setFilterColumn(null);
    setFilterOperator('>');
    setFilterValue(null);
    setXAxisCol(null);
    setLookups([]);
  }, [recommendations]);

  const discreteColumns = useMemo(() => {
    return columns.filter(c => !scalarColumns.includes(c));
  }, [columns, scalarColumns]);

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

  useEffect(() => {
    if (matchedChartName === "Bar Chart") {
      setLimitCount(30);
    } else if (["Line Chart", "Boxplot", "Violin Plot", "Point Range", "Grouped Bar", "Stacked Bar"].includes(matchedChartName || "")) {
      setLimitCount(10);
    }
  }, [matchedChartName]);

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
        limit_count: limitCount,
        log_scale: logScale,
        chart_name: matchedChartName || "", // Pass the matched chart name to the backend
        filter_column: filterColumn,
        filter_operator: filterOperator,
        filter_value: filterValue,
        x_axis_col: xAxisCol,
        lookups: lookups.filter(lk => lk.local_column && lk.target_table),
        group_others: groupOthers
      });
      setChartHtml(res.html);
      setChartCode(res.code || null);
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
            <Row gutter={24} style={{ marginBottom: '16px' }}>
              <Col span={24}>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text strong>Data Filter (Optional)</Text>
                  <Space.Compact style={{ width: '100%' }}>
                    <Select 
                      allowClear
                      placeholder={scalarColumns.length > 0 ? "Select Column to Filter..." : "No scalar columns to filter"}
                      value={filterColumn}
                      onChange={(val) => { setFilterColumn(val); setFilterValue(null); }}
                      style={{ width: '40%' }}
                      disabled={scalarColumns.length === 0}
                      options={scalarColumns.map(c => ({ label: `${c}`, value: c }))}
                    />
                    <Select 
                      value={filterOperator}
                      onChange={setFilterOperator}
                      style={{ width: '20%' }}
                      disabled={!filterColumn}
                      options={[
                        { label: '> Greater than', value: '>' },
                        { label: '>= Greater or equal', value: '>=' },
                        { label: '< Less than', value: '<' },
                        { label: '<= Less or equal', value: '<=' },
                        { label: '== Equal', value: '==' },
                        { label: '!= Not equal', value: '!=' },
                      ]}
                    />
                    <InputNumber 
                      placeholder="Enter value"
                      value={filterValue}
                      onChange={(val) => setFilterValue(val)}
                      style={{ width: '40%' }}
                      disabled={!filterColumn}
                    />
                  </Space.Compact>
                </Space>
              </Col>
            </Row>

            {discreteColumns.length > 0 && ["Word Cloud", "Bar Chart"].includes(matchedChartName) && (
              <Row gutter={24} style={{ marginBottom: '16px' }}>
                <Col span={24}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text strong>Alternative Key</Text>
                    <Select 
                      allowClear
                      placeholder="Default (Primary Key)"
                      value={xAxisCol}
                      onChange={setXAxisCol}
                      style={{ width: '40%' }}
                      options={discreteColumns.map(c => ({ label: `${c}`, value: c }))}
                    />
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      Select a candidate key to replace the default primary key on the axis.
                    </Text>
                  </Space>
                </Col>
              </Row>
            )}

            {discreteColumns.length > 0 && !recommendations.pattern.includes("Basic Entity") && (
              <Row gutter={24} style={{ marginBottom: '16px' }}>
                <Col span={24}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text strong>Alternative Key Lookup (Foreign Key Tracing)</Text>
                      <Button size="small" type="dashed" onClick={addLookup}>+ Add Lookup Rule</Button>
                    </div>
                    {lookups.length > 0 && (
                      <div style={{ padding: '10px', backgroundColor: '#f0f2f5', borderRadius: '6px' }}>
                        {lookups.map((lookup, index) => (
                          <Space.Compact style={{ width: '100%', marginBottom: index === lookups.length - 1 ? 0 : '8px' }} key={index}>
                            <Select 
                              placeholder="Local FK Col" 
                              value={lookup.local_column || undefined} 
                              onChange={(v) => updateLookup(index, 'local_column', v)} 
                              style={{ width: '22%' }} 
                              options={discreteColumns.map(c => ({ label: c, value: c }))} 
                            />
                            <Select 
                              placeholder="Target Table (e.g. country)" 
                              value={lookup.target_table || undefined} 
                              onChange={(v) => handleTargetTableChange(index, v)} 
                              style={{ width: '26%' }}
                              showSearch
                              options={dbMetadata.map(t => ({ label: `📊 ${t.table_name}`, value: t.table_name }))}
                            />
                            <Select 
                              placeholder="Target Join Key (e.g. code)" 
                              value={lookup.target_join_key || undefined} 
                              onChange={(v) => updateLookup(index, 'target_join_key', v)} 
                              style={{ width: '22%' }}
                              showSearch
                              disabled={!lookup.target_table}
                              options={
                                dbMetadata
                                  .find(t => t.table_name === lookup.target_table)?.columns
                                  .map(c => ({ label: c.name, value: c.name })) || []
                              }
                            />
                            <Select 
                              placeholder="Target Display Col (e.g. name)" 
                              value={lookup.target_display_col || undefined} 
                              onChange={(v) => updateLookup(index, 'target_display_col', v)} 
                              style={{ width: '26%' }}
                              showSearch
                              disabled={!lookup.target_table}
                              options={
                                dbMetadata
                                  .find(t => t.table_name === lookup.target_table)?.columns
                                  .map(c => ({ label: c.name, value: c.name })) || []
                              }
                            />
                            <Button danger onClick={() => removeLookup(index)}>X</Button>
                          </Space.Compact>
                        ))}
                      </div>
                    )}
                  </Space>
                </Col>
              </Row>
            )}

            <Row gutter={24}>
              {/* sampling method options */}
              <Col span={12}>
                {["Bar Chart", "Line Chart", "Boxplot", "Violin Plot", "Point Range", "Heatmap Matrix", "Tree Map", "Sankey Diagram", "Word Cloud"].includes(matchedChartName) ? (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text strong>Sampling Method</Text>
                    <Space.Compact style={{ width: '100%' }}>
                      <InputNumber 
                        min={0} 
                        max={100} 
                        value={limitCount} 
                        onChange={(val) => setLimitCount(val as number)} 
                        style={{ width: '80px' }}
                      />
                    <Select 
                      value={limitMethod}
                      onChange={setLimitMethod}
                      style={{ width: 'calc(100% - 80px)' }}
                      options={[
                        { label: 'Top (Highest values)', value: 'top' },
                        { label: 'Bottom (Lowest values)', value: 'bottom' },
                        { label: 'Random Sample', value: 'random' },
                        { label: 'Distributed Sample(Evenly Sampling)', value: 'distributed' }
                      ]}
                    />
                    </Space.Compact>
                    {["Bar Chart", "Line Chart", "Boxplot", "Violin Plot", "Point Range"].includes(matchedChartName || "") && (
                      <Space style={{ marginTop: '8px' }}>
                        <Switch checked={groupOthers} onChange={setGroupOthers} size="small" />
                        <Text type="secondary">Group remaining data</Text>
                      </Space>
                    )}
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

    {(chartHtml || chartCode) && (
        <Row gutter={24} style={{ marginTop: '20px', display: 'flex', alignItems: 'stretch' }}>
          {chartCode && (
            <Col xs={24} lg={8} style={{ display: 'flex', flexDirection: 'column' }}>
              <Card 
                title="ggplot Code Snippet" 
                style={{ 
                  borderRadius: '8px', 
                  flex: 1, 
                  display: 'flex', 
                  flexDirection: 'column',
                  border: '1px solid #e8e8e8'
                }}
                styles={{ body: { padding: 0, flex: 1 } }}
              >
                <pre style={{ 
                  backgroundColor: '#282c34',
                  color: '#edeef0',
                  padding: '24px', 
                  margin: 0,
                  overflowX: 'auto',
                  overflowY: 'auto',
                  fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                  fontSize: '13.5px',
                  lineHeight: '1.6',
                  height: '500px', 
                  textAlign: 'left',
                  borderBottomLeftRadius: '8px',
                  borderBottomRightRadius: '8px',
                  border: 'none'
                }}>
                  <code style={{ 
                    backgroundColor: 'transparent',
                    color: 'inherit',
                    padding: 0,
                    margin: 0,
                    border: 'none',
                    display: 'block'
                  }}>
                    {chartCode}
                  </code>
                </pre>
              </Card>
            </Col>
          )}

          {chartHtml && (
            <Col xs={24} lg={chartCode ? 16 : 24} style={{ display: 'flex', flexDirection: 'column' }}>
              <Card 
                style={{ 
                  borderRadius: '8px', 
                  overflow: 'hidden', 
                  flex: 1,
                  display: 'flex', 
                  flexDirection: 'column'
                }}
                styles={{ body: { padding: 0, flex: 1 } }}
              >
                <iframe 
                  title="Interactive Chart"
                  srcDoc={chartHtml} 
                  sandbox="allow-scripts"
                  style={{ width: '100%', height: '500px', border: 'none', display: 'block' }} 
                />
              </Card>
            </Col>
          )}

        </Row>
    )}
    </>
  );
};