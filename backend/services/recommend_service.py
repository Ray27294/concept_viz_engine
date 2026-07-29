from typing import List
from schemas import TableMetadata, ChartCombination, RecommendationResponse

GEO_NAMES = {"country", "city", "state", "county", "province"}

def _get_attributes_info(table: TableMetadata, selected_col_names: List[str]):
    """Analyse the selected columns of a table to determine the number of scalar and lexical attributes, 
    and whether it contains geographic fields."""
    pk_names = {col.name for col in table.primary_key.columns} if table.primary_key else set()
    fk_names = {col.name for fk in table.foreign_keys for col in fk.source.columns}
    key_names = pk_names | fk_names
    
    final_selected = set(selected_col_names).union(pk_names)
    
    attributes = [
        c for c in table.columns 
        if c.name in final_selected and c.name not in key_names
    ]
    
    num_scalars = sum(1 for a in attributes if a.semantic_type == "scalar")
    num_lexical = sum(1 for a in attributes if a.semantic_type == "lexical")
    
    is_geo = table.table_name.lower() in GEO_NAMES or any(k.lower() in GEO_NAMES for k in key_names)
    
    return num_scalars, num_lexical, is_geo

def recommend_components(
    table: TableMetadata, 
    selected_col_names: List[str], 
    pattern: str, 
    is_complete: bool = False
) -> RecommendationResponse:
    
    num_scalars, num_lexical, is_geo = _get_attributes_info(table, selected_col_names)
    combinations: List[ChartCombination] = []

    if "Basic Entity" in pattern:
        if num_scalars == 1:
            combinations.append(ChartCombination(chart_name="Bar Chart", geom="col", stat="identity"))
            combinations.append(ChartCombination(chart_name="Histogram", geom="bar", stat="bin"))
            combinations.append(ChartCombination(chart_name="Frequency Polygon", geom="line", stat="bin"))
            combinations.append(ChartCombination(chart_name="Density Plot", geom="area", stat="density"))
            if is_geo:
                combinations.append(ChartCombination(chart_name="Choropleth Map", geom="map", stat="identity"))
        if num_scalars == 1 and num_lexical == 1:
            combinations.append(ChartCombination(chart_name="Histogram", geom="bar", stat="bin"))
            combinations.append(ChartCombination(chart_name="Frequency Polygon", geom="line", stat="bin"))
            combinations.append(ChartCombination(chart_name="Density Plot", geom="area", stat="density"))
        if num_scalars in [2, 3] and num_lexical == 0:
            combinations.append(ChartCombination(chart_name="Scatter Diagram", geom="point", stat="identity"))
        if num_scalars in [3, 4] and num_lexical == 0:
            combinations.append(ChartCombination(chart_name="Bubble Chart", geom="point", stat="identity"))

    elif "Weak Entity" in pattern:
        if num_scalars == 1:
            combinations.append(ChartCombination(chart_name="Line Chart", geom="line", stat="identity"))
            combinations.append(ChartCombination(chart_name="Grouped Bar", geom="col", stat="identity")) # pos="dodge"
            combinations.append(ChartCombination(chart_name="Boxplot", geom="boxplot", stat="boxplot"))
            combinations.append(ChartCombination(chart_name="Violin Plot", geom="violin", stat="ydensity"))
            combinations.append(ChartCombination(chart_name="Point Range", geom="pointrange", stat="summary"))
            if is_complete:
                combinations.append(ChartCombination(chart_name="Stacked Bar", geom="col", stat="identity")) # pos="stack"
        if num_scalars in [1, 2]:
            combinations.append(ChartCombination(chart_name="Line Chart", geom="line", stat="identity"))

    elif "One-to-Many" in pattern:
        if num_scalars == 1:
            combinations.append(ChartCombination(chart_name="Boxplot", geom="boxplot", stat="boxplot"))
            combinations.append(ChartCombination(chart_name="Violin Plot", geom="violin", stat="ydensity"))
            combinations.append(ChartCombination(chart_name="Point Range", geom="pointrange", stat="summary"))

    elif "Many-to-Many" in pattern:
        if num_scalars == 1 or num_lexical == 1:
            combinations.append(ChartCombination(chart_name="Heatmap Matrix", geom="tile", stat="identity"))
        if num_scalars == 2:
            combinations.append(ChartCombination(chart_name="2D Binning", geom="tile", stat="bin_2d"))

    available_geoms = list({c.geom for c in combinations})
    available_stats = list({c.stat for c in combinations})

    return RecommendationResponse(
        pattern=pattern,
        available_geoms=available_geoms,
        available_stats=available_stats,
        valid_combinations=combinations
    )