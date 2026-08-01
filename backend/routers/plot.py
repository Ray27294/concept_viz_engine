from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
from sqlalchemy import text
from plotnine import ggplot, aes, geom_col, geom_bar, geom_histogram, geom_line, geom_density, geom_map, geom_point, scale_y_log10, theme_minimal, theme_void, labs, theme, element_text, scale_x_log10, scale_fill_continuous
from ninejs import interactive, to_html
from database import engine
from services.metadata_service import extract_database_metadata

router = APIRouter(prefix="/plot", tags=["Plotting"])

_world_map_cache = None  # Cache for the world map data to avoid reloading it multiple times

def get_world_map():
    global _world_map_cache
    if _world_map_cache is None:
        try:
            import geopandas as gpd
            url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
            _world_map_cache = gpd.read_file(url)
            _world_map_cache.rename(columns={"ADMIN": "name"}, inplace=True)
        except ImportError:
            raise HTTPException(status_code=500, detail="Geopandas is required for map plotting. Please install geopandas.")
    return _world_map_cache.copy()

class PlotRequest(BaseModel):
    table_name: str
    selected_columns: List[str]
    geom: str
    stat: str
    limit_method: str = "top"
    log_scale: bool = False

@router.post("/generate")
def generate_plot(request: PlotRequest):
    # To fetch the table metadata and add primary key
    metadata = extract_database_metadata(engine)
    table_meta = next((t for t in metadata if t.table_name == request.table_name), None)
    
    if not table_meta:
        raise HTTPException(status_code=404, detail="Failed to find table metadata for the specified table name.")

    pk_names = [col.name for col in table_meta.primary_key.columns] if table_meta.primary_key else []
    
    columns_to_fetch = list(set(request.selected_columns).union(pk_names))

    if request.geom == "map":
        if any(c.name.lower() == 'name' for c in table_meta.columns) and 'name' not in columns_to_fetch:
            columns_to_fetch.append('name')

    # extract the data from the database
    safe_cols = ", ".join([f'"{c}"' for c in columns_to_fetch])
    safe_table = f'"{request.table_name}"'
    
    where_clause = " AND ".join([f'"{c}" IS NOT NULL' for c in request.selected_columns])
    
    query = f"SELECT {safe_cols} FROM public.{safe_table}"
    if where_clause:
        query += f" WHERE {where_clause}"
    
    try:
        df = pd.read_sql_query(query, engine)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Data source is empty, cannot generate plot")

    # identify scalar
    scalar_cols = []
    lexical_cols = []
    for col_name in request.selected_columns:
        col_meta = next((c for c in table_meta.columns if c.name == col_name), None)
        if col_meta and col_meta.semantic_type == "scalar":
            scalar_cols.append(col_name)
        elif col_meta and col_meta.semantic_type == "lexical":
            lexical_cols.append(col_name)

    # build the plot using plotnine
    try:
        gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))

        group_col = lexical_cols[0] if lexical_cols else None
        if group_col:
            unique_count = df[group_col].nunique()
            if unique_count > 10:
                top_categories = df[group_col].value_counts().nlargest(9).index.tolist()
                df[group_col] = df[group_col].apply(lambda x: x if x in top_categories else 'Other')
                cats = top_categories + ['Other']
                df[group_col] = pd.Categorical(df[group_col], categories=cats, ordered=True)

        if request.geom == "col" and request.stat == "identity":
            x_col = pk_names[0] if pk_names else columns_to_fetch[0]
            y_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]

            title_prefix = ""
            if len(df) > 30:
                if request.limit_method == "top":
                    df = df.sort_values(by=y_col, ascending=False).head(30)
                    title_prefix = "Top 30 "
                elif request.limit_method == "bottom":
                    df = df.sort_values(by=y_col, ascending=True).head(30)
                    title_prefix = "Bottom 30 "
                elif request.limit_method == "random":
                    df = df.sample(n=30)
                    title_prefix = "Random Sample (30) "
                elif request.limit_method == "distributed":
                    df_sorted = df.sort_values(by=y_col, ascending=False)
                    indices = np.linspace(0, len(df_sorted) - 1, 30, dtype=int)
                    df = df_sorted.iloc[indices]
                    title_prefix = "Distributed Sample (30) "
                    df[x_col] = pd.Categorical(df[x_col], categories=df[x_col].tolist()[::-1], ordered=True)

            gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))
            
            mapping = aes(x=x_col, y=y_col, tooltip=y_col, hover_group=x_col)
            gg = gg + mapping + geom_col(fill="#1890ff", alpha=0.8) + labs(title=f"{title_prefix}{y_col} by {x_col}") + theme(figure_size=(10, 8))
            if request.log_scale:
                gg = gg + scale_y_log10() + labs(y=f"Log-scaled {y_col}")

        elif request.geom == "bar" and request.stat == "bin":
            x_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]
            if group_col:
                mapping = aes(x=x_col, fill=group_col)
                gg = gg + mapping + geom_histogram(bins=30, alpha=0.7, position="identity") + labs(title=f"Distribution of {x_col} by {group_col}")
            else:
                mapping = aes(x=x_col)       
                gg = gg + mapping + geom_histogram(bins=30, fill="#52c41a", alpha=0.8, color="green") + labs(title=f"Distribution of {x_col}")
            if request.log_scale:
                gg = gg + scale_x_log10() + labs(x=f"Log-scaled {x_col}")

        elif request.geom == "line" and request.stat == "bin":
            x_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]
            if group_col:
                mapping = aes(x=x_col, color=group_col)
                gg = gg + mapping + geom_line(stat="bin", bins=30, size=1.2) + labs(title=f"Frequency Polygon of {x_col} by {group_col}")
            else:
                mapping = aes(x=x_col)       
                gg = gg + mapping + geom_line(stat="bin", bins=30, color="#fa8c16", size=1.2) + labs(title=f"Frequency Polygon of {x_col}")
            if request.log_scale:
                gg = gg + scale_x_log10() + labs(x=f"Log-scaled {x_col}")

        elif request.geom == "area" and request.stat == "density":
            x_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]
            if group_col:
                mapping = aes(x=x_col, fill=group_col)
                gg = gg + mapping + geom_density(alpha=0.5) + labs(title=f"Density Plot of {x_col} by {group_col}")
            else:
                mapping = aes(x=x_col)       
                gg = gg + mapping + geom_density(fill="#722ed1", alpha=0.6, color="#531dab") + labs(title=f"Density Plot of {x_col}")
            if request.log_scale:
                gg = gg + scale_x_log10() + labs(x=f"Log-scaled {x_col}")

        elif request.geom == "map" and request.stat == "identity":
            x_col = pk_names[0] if pk_names else columns_to_fetch[0]
            y_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]

            world = get_world_map()

            join_col = "name" if "name" in df.columns else x_col

            COUNTRY_NAME_MAPPING = {
                "United States": "United States of America",
                "Congo": "Republic of the Congo",
                "Congo, Dem.Rep.": "Democratic Republic of the Congo",
                "Tanzania": "United Republic of Tanzania",
                "Somalia": "Somalia",
                "Somaliland": "Somaliland" 
            }
            if join_col in df.columns:
                df[join_col] = df[join_col].replace(COUNTRY_NAME_MAPPING)

            df_map = world.merge(df, how="inner", left_on="name", right_on=join_col)
            if df_map.empty:
                raise HTTPException(status_code=400, detail="No matching countries found for the map plot. Ensure that the 'name' column in your data matches country names in the world map.")

            gg = ggplot(df_map) + theme_void()

            mapping = aes(fill=y_col, tooltip=join_col, hover_group=join_col)
            gg = gg + mapping + geom_map(color="black", size=0.2) + labs(title=f"Choropleth Map of {y_col}") + theme(figure_size=(10, 8))
            if request.log_scale:
                gg = gg + scale_fill_continuous(trans='log10') + labs(fill=f"Log-scaled {y_col}")

        elif request.geom == "point" and request.stat == "identity":
            x_col = scalar_cols[0]
            y_col = scalar_cols[1]
            label_col = pk_names[0] if pk_names else x_col

            aes_args = {
                "x": x_col,
                "y": y_col,
                "tooltip": label_col,
                "hover_group": label_col
            }

            if len(scalar_cols) == 3:
                aes_args["color"] = scalar_cols[2]
                aes_args["size"] = scalar_cols[2]
                title = f"Bubble Chart: {y_col} vs {x_col} (Color & Size: {scalar_cols[2]})"
            elif len(scalar_cols) >= 4:
                aes_args["size"] = scalar_cols[2]
                aes_args["color"] = scalar_cols[3]
                title = f"Bubble Chart: {y_col} vs {x_col}"
            else:
                title = f"Scatter Diagram: {y_col} vs {x_col}"

            mapping = aes(**aes_args)
            gg = gg + mapping + geom_point(alpha=0.7) + labs(title=title)

            if request.log_scale:
                gg = gg + scale_x_log10() + scale_y_log10() + labs(x=f"Log-scaled {x_col}", y=f"Log-scaled {y_col}")

        elif request.geom == "line" and request.stat == "identity":
            y_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]
            group_col = "Entity_Group"
            x_col = pk_names[-1]
            entity_cols = pk_names[:-1]  # All primary key columns except the last one for grouping
            df[group_col] = df[entity_cols].astype(str).agg(', '.join, axis=1)
            group_display_name = " + ".join(entity_cols)

            title_prefix = ""

            if group_col and df[group_col].nunique() > 10:
                if request.limit_method == "top":
                    top_groups = df.groupby(group_col)[y_col].max().nlargest(10).index.tolist()
                    title_prefix = "Top 10 "
                elif request.limit_method == "bottom":
                    top_groups = df.groupby(group_col)[y_col].max().nsmallest(10).index.tolist()
                    title_prefix = "Bottom 10 "
                elif request.limit_method == "random":
                    import random
                    all_groups = df[group_col].dropna().unique().tolist()
                    top_groups = random.sample(all_groups, min(10, len(all_groups)))
                    title_prefix = "Random 10 "
                elif request.limit_method == "distributed":
                    sorted_groups = df.groupby(group_col)[y_col].max().sort_values(ascending=False).index.tolist()
                    indices = np.linspace(0, len(sorted_groups) - 1, 10, dtype=int)
                    top_groups = [sorted_groups[i] for i in indices]
                    title_prefix = "Distributed 10 "
                else:
                    top_groups = df.groupby(group_col)[y_col].max().nlargest(10).index.tolist()
                    
                df = df[df[group_col].isin(top_groups)]

            df = df.sort_values(by=[group_col, x_col] if group_col else [x_col])

            gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))
            
            if group_col:
                mapping = aes(x=x_col, y=y_col, color=group_col, group=group_col, tooltip=y_col, hover_group=group_col)
                gg = gg + mapping + geom_line(size=1) + geom_point(size=2, alpha=0.8) + labs(title=f"{title_prefix}Trend of {y_col} by {group_display_name}", color="Entity")
            else:
                mapping = aes(x=x_col, y=y_col, tooltip=x_col)
                gg = gg + mapping + geom_line(color="#1890ff", size=1) + geom_point(color="#1890ff", size=2) + labs(title=f"Trend of {y_col}")
            
            if request.log_scale:
                gg = gg + scale_y_log10() + labs(y=f"Log-scaled {y_col}")
        
        else:
            raise ValueError(f"Currently not supported: geom={request.geom}, stat={request.stat}")

        # generate HTML string for the plot
        html_string = interactive(gg) + to_html()
        
        return {"html": html_string}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate plot: {str(e)}")