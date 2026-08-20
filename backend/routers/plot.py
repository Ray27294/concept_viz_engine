from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
from sqlalchemy import text
from plotnine import ggplot, aes, geom_col, geom_bar, geom_histogram, geom_line, geom_density, geom_map, geom_point, geom_boxplot, geom_violin, geom_pointrange, geom_tile, geom_bin2d, scale_y_log10, theme_minimal, theme_void, labs, theme, element_text, scale_x_log10, scale_fill_continuous
from ninejs import interactive, to_html
from database import engine
from services.metadata_service import extract_database_metadata
import plotly.express as px
import plotly.graph_objects as go

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

class DimensionLookup(BaseModel):
    local_column: str          # column in the current table (e.g., country)
    target_table: str          # target parent table (e.g., country)
    target_join_key: str       # primary key of the target table (e.g., code)
    target_display_col: str    # candidate key/display column of the target table (e.g., name)

class PlotRequest(BaseModel):
    table_name: str
    selected_columns: List[str]
    geom: str
    stat: str
    limit_method: str = "top"
    limit_count: int = 30
    log_scale: bool = False
    chart_name: str = ""
    filter_column: Optional[str] = None
    filter_operator: Optional[str] = None
    filter_value: Optional[float] = None
    x_axis_col: Optional[str] = None
    lookups: Optional[List[DimensionLookup]] = []
    group_others: bool = False

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

    # Apply data filtering
    if request.filter_column and request.filter_operator and request.filter_value is not None:
        col = request.filter_column
        val = request.filter_value
        op = request.filter_operator
        
        if col in df.columns:
            if op == ">": df = df[df[col] > val]
            elif op == ">=": df = df[df[col] >= val]
            elif op == "<": df = df[df[col] < val]
            elif op == "<=": df = df[df[col] <= val]
            elif op == "==": df = df[df[col] == val]
            elif op == "!=": df = df[df[col] != val]
            
            if df.empty:
                raise HTTPException(status_code=400, detail=f"No data remaining after applying filter: {col} {op} {val}")

    # Apply alternative key replacement
    if request.lookups:
        try:
            for lk in request.lookups:
                # Find the primary key and the display column in the target table
                lookup_query = f'SELECT "{lk.target_join_key}", "{lk.target_display_col}" AS "_display" FROM public."{lk.target_table}"'
                df_lookup = pd.read_sql_query(lookup_query, engine)
                
                # Perform a left join
                df = df.merge(df_lookup, left_on=lk.local_column, right_on=lk.target_join_key, how="left")
                
                # replace the local foreign key with the display column
                df[lk.local_column] = df["_display"].fillna(df[lk.local_column])
                
                # Cleanup temporary columns
                cols_to_drop = ["_display"]
                if lk.target_join_key != lk.local_column and lk.target_join_key in df.columns:
                    cols_to_drop.append(lk.target_join_key)
                df = df.drop(columns=cols_to_drop, errors='ignore')
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed during dimension lookup: {str(e)}")

    # identify scalar
    scalar_cols = []
    discrete_cols = []
    for col_name in request.selected_columns:
        col_meta = next((c for c in table_meta.columns if c.name == col_name), None)
        if col_meta and col_meta.semantic_type == "scalar":
            scalar_cols.append(col_name)
        elif col_meta and col_meta.semantic_type == "discrete":
            discrete_cols.append(col_name)

    try:
        # ==========================================
        # Plotly engine
        # ==========================================
        if request.geom in ["treemap", "sankey", "sunburst"]:
            limit = request.limit_count
            if request.geom in ["treemap", "sunburst"]:
                chart_title_name = "Tree Map" if request.geom == "treemap" else "Sunburst Chart"
                if len(discrete_cols) == 0 or not scalar_cols:
                    raise HTTPException(status_code=400, detail="Tree Map requires at least one categorical (discrete) column for hierarchy and one scalar for size.")
                
                # parent node is foreign key, child node is the primary key
                parent_col = discrete_cols[0]
                child_col = pk_names[0] if pk_names else columns_to_fetch[0]
                val_col = scalar_cols[0]

                if df[parent_col].nunique() > limit:
                    if request.limit_method == "top":
                        top_parents = df.groupby(parent_col)[val_col].sum().nlargest(limit).index.tolist()
                    elif request.limit_method == "bottom":
                        top_parents = df.groupby(parent_col)[val_col].sum().nsmallest(limit).index.tolist()
                    elif request.limit_method == "random":
                        import random
                        all_parents = df[parent_col].dropna().unique().tolist()
                        top_parents = random.sample(all_parents, min(limit, len(all_parents)))
                    elif request.limit_method == "distributed":
                        sorted_parents = df.groupby(parent_col)[val_col].sum().sort_values(ascending=False).index.tolist()
                        indices = np.linspace(0, len(sorted_parents) - 1, limit, dtype=int)
                        top_parents = [sorted_parents[i] for i in indices]
                    else:
                        top_parents = df.groupby(parent_col)[val_col].sum().nlargest(limit).index.tolist()
                    
                    df = df[df[parent_col].isin(top_parents)]
                
                if request.geom == "treemap":
                    fig = px.treemap(df, path=[parent_col, child_col], values=val_col, 
                                     title=f"{chart_title_name} of {val_col} (Hierarchy: {parent_col} -> {child_col})")
                    func_name = "px.treemap"
                else:
                    fig = px.sunburst(df, path=[parent_col, child_col], values=val_col, 
                                      title=f"{chart_title_name} of {val_col} (Hierarchy: {parent_col} -> {child_col})")
                    func_name = "px.sunburst"
                if request.log_scale:
                    fig.update_traces(marker=dict(colors=np.log10(df[val_col] + 1), colorscale='Viridis'))

                code_snippet = f'''
import plotly.express as px

# prepare data and filtering as needed
# df = pd.read_sql_query(...)

fig = {func_name}(df, 
                 path=['{parent_col}', '{child_col}'], 
                 values='{val_col}',
                 title='Tree Map of {val_col}')
fig.show()'''

            elif request.geom == "sankey":
                dims = pk_names + [c for c in discrete_cols if c not in pk_names]
                if len(dims) < 2:
                    raise HTTPException(status_code=400, detail="Sankey Diagram requires at least two categorical dimensions for source and target.")
                
                source_col = dims[0]
                target_col = dims[1]
                val_col = scalar_cols[0] if scalar_cols else None

                def get_sampled_nodes(col_name):
                    if request.limit_method == "top":
                        return df[col_name].value_counts().nlargest(limit).index.tolist()
                    elif request.limit_method == "bottom":
                        return df[col_name].value_counts().nsmallest(limit).index.tolist()
                    elif request.limit_method == "random":
                        import random
                        all_nodes = df[col_name].dropna().unique().tolist()
                        return random.sample(all_nodes, min(limit, len(all_nodes)))
                    else:
                        return df[col_name].value_counts().nlargest(limit).index.tolist()

                if df[source_col].nunique() > limit:
                    top_src = get_sampled_nodes(source_col)
                    df = df[df[source_col].isin(top_src)]
                if df[target_col].nunique() > limit:
                    top_tgt = get_sampled_nodes(target_col)
                    df = df[df[target_col].isin(top_tgt)]
                
                all_nodes = list(pd.unique(df[[source_col, target_col]].values.ravel('K')))
                node_map = {node: i for i, node in enumerate(all_nodes)}
                
                source_indices = df[source_col].map(node_map).tolist()
                target_indices = df[target_col].map(node_map).tolist()
                values = df[val_col].tolist() if val_col else [1] * len(df)
                
                palette = px.colors.qualitative.Plotly             
                def hex_to_rgba(hex_code, opacity):
                    hex_code = hex_code.lstrip('#')
                    r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
                    return f"rgba({r}, {g}, {b}, {opacity})"
                node_colors = [hex_to_rgba(palette[i % len(palette)], 0.85) for i in range(len(all_nodes))]
                link_colors = [hex_to_rgba(palette[src % len(palette)], 0.35) for src in source_indices]
                fig = go.Figure(data=[go.Sankey(
                    node = dict(pad=5, thickness=10, line=dict(color="black", width=0.5), label=all_nodes, color=node_colors),
                    link = dict(source=source_indices, target=target_indices, value=values, color=link_colors)
                )])
                fig.update_layout(title_text=f"Sankey Flow: {source_col} to {target_col}", font_size=12)

                code_snippet = f'''
import plotly.graph_objects as go
import pandas as pd

dims = pk_names + [c for c in lexical_cols if c not in pk_names]
source_col = dims[0]
target_col = dims[1]
val_col = scalar_cols[0] if scalar_cols else None
all_nodes = list(pd.unique(df[['{source_col}', '{target_col}']].values.ravel('K')))
node_map = {{node: i for i, node in enumerate(all_nodes)}}

source_indices = df['{source_col}'].map(node_map).tolist()
target_indices = df['{target_col}'].map(node_map).tolist()
values = df['{val_col}'].tolist() if '{val_col}' != 'None' else [1] * len(df)

palette = px.colors.qualitative.Plotly
def hex_to_rgba(hex_code, opacity):
    hex_code = hex_code.lstrip('#')
    r, g, b = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({{r}}, {{g}}, {{b}}, {{opacity}})"
node_colors = [hex_to_rgba(palette[i % len(palette)], 0.85) for i in range(len(all_nodes))]
link_colors = [hex_to_rgba(palette[src % len(palette)], 0.35) for src in source_indices]

fig = go.Figure(data=[go.Sankey(
    node = dict(label=all_nodes, pad=5, thickness=10, color=node_colors),
    link = dict(source=source_indices, target=target_indices, value=values, color=link_colors)
)])
fig.show()'''

            html_string = fig.to_html(full_html=False, include_plotlyjs='cdn')
            return {"html": html_string, "code": code_snippet}
            
        elif request.geom == "wordcloud":
            limit = request.limit_count
            import io
            import base64
            from wordcloud import WordCloud
            
            word_col = request.x_axis_col if request.x_axis_col else (pk_names[0] if pk_names else columns_to_fetch[0])
            
            if not scalar_cols:
                raise HTTPException(status_code=400, detail="Word Cloud requires at least one scalar column to define word frequencies (sizes).")
            freq_col = scalar_cols[0]
            
            if df[word_col].nunique() > limit:
                if request.limit_method == "top":
                    top_words = df.groupby(word_col)[freq_col].sum().nlargest(limit).index.tolist()
                elif request.limit_method == "bottom":
                    top_words = df.groupby(word_col)[freq_col].sum().nsmallest(limit).index.tolist()
                elif request.limit_method == "random":
                    import random
                    all_words = df[word_col].dropna().unique().tolist()
                    top_words = random.sample(all_words, min(limit, len(all_words)))
                else:
                    top_words = df.groupby(word_col)[freq_col].sum().nlargest(limit).index.tolist()
                df = df[df[word_col].isin(top_words)]
            
            freq_dict = dict(zip(df[word_col].astype(str), df[freq_col]))
            
            wc = WordCloud(
                width=900, 
                height=700, 
                background_color='white', 
                colormap='prism',
                max_words=limit,
                contour_width=0,
                prefer_horizontal=0.8
            )
            wc.generate_from_frequencies(freq_dict)
            
            img_io = io.BytesIO()
            wc.to_image().save(img_io, format='PNG')
            img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            
            html_string = f'''
            <div style="display: flex; justify-content: center; align-items: center; width: 100%; height: 100%; background-color: #ffffff; overflow: hidden;">
                <img src="data:image/png;base64,{img_base64}" style="max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);" />
            </div>
            '''
            
            code_snippet = f'''
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# data preparation and Top-{limit} sampling
# df = pd.read_sql_query(...)
freq_dict = dict(zip(df['{word_col}'].astype(str), df['{freq_col}']))

wc = WordCloud(
width=900, height=500, 
background_color='white', 
colormap='prism',
max_words={limit},
prefer_horizontal=0.8
)
wc.generate_from_frequencies(freq_dict)
'''

            return {"html": html_string, "code": code_snippet}

        # ==========================================
        # Plotnine (ggplot) engine
        # ==========================================
        gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))

        if request.stat in ["bin", "density"]:
            group_col = discrete_cols[0] if discrete_cols else None
            if group_col:
                unique_count = df[group_col].nunique()
                if unique_count > 10:
                    top_categories = df[group_col].value_counts().nlargest(9).index.tolist()
                    df[group_col] = df[group_col].apply(lambda x: x if x in top_categories else 'Other')
                    cats = top_categories + ['Other']
                    df[group_col] = pd.Categorical(df[group_col], categories=cats, ordered=True)

        # Bar Charts, including grouped and stacked bar charts
        if request.geom == "col" and request.stat == "identity":
            y_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]
            is_weak_entity_bar = ("Grouped" in request.chart_name or "Stacked" in request.chart_name)

            if is_weak_entity_bar and len(pk_names) > 1:
                entity_cols = pk_names[:-1]
                time_col = pk_names[-1]
                
                x_col = "Entity_Group"
                df[x_col] = df[entity_cols].astype(str).agg(', '.join, axis=1)
                x_display_name = " + ".join(entity_cols)
                
                group_col = time_col
                df[group_col] = df[group_col].astype(str)
                
                title_prefix = ""
                if df[x_col].nunique() > 5:
                    top_entities = df.groupby(x_col)[y_col].max().nlargest(5).index.tolist()
                    df = df[df[x_col].isin(top_entities)]
                    title_prefix = "Top 5 "

                df = df.sort_values(by=[x_col, group_col])
                
                gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))
                
                mapping = aes(x=x_col, y=y_col, fill=group_col, tooltip=group_col, hover_group=group_col)
                
                if "Stacked" in request.chart_name:
                    gg = gg + mapping + geom_col(position="stack", alpha=0.9) + labs(title=f"{title_prefix}Stacked Bar: {y_col} by {x_display_name}", fill=time_col, x=x_display_name)
                else:
                    gg = gg + mapping + geom_col(position="dodge", alpha=0.9) + labs(title=f"{title_prefix}Grouped Bar: {y_col} by {x_display_name}", fill=time_col, x=x_display_name)

                if request.log_scale:
                    gg = gg + scale_y_log10() + labs(y=f"Log-scaled {y_col}")

            else:
                x_col = request.x_axis_col if request.x_axis_col else (pk_names[0] if pk_names else columns_to_fetch[0])
                title_prefix = ""
                if len(df) > request.limit_count:
                    if request.limit_method == "top":
                        top_entities = df.sort_values(by=y_col, ascending=False)[x_col].head(request.limit_count).tolist()
                        title_prefix = f"Top {request.limit_count} "
                    elif request.limit_method == "bottom":
                        top_entities = df.sort_values(by=y_col, ascending=True)[x_col].head(request.limit_count).tolist()
                        title_prefix = f"Bottom {request.limit_count} "
                    elif request.limit_method == "random":
                        top_entities = df[x_col].sample(n=request.limit_count).tolist()
                        title_prefix = f"Random Sample ({request.limit_count}) "
                    elif request.limit_method == "distributed":
                        df_sorted = df.sort_values(by=y_col, ascending=False)
                        indices = np.linspace(0, len(df_sorted) - 1, request.limit_count, dtype=int)
                        top_entities = df_sorted.iloc[indices][x_col].tolist()
                        title_prefix = f"Distributed Sample ({request.limit_count}) "
                    else:
                        top_entities = df.sort_values(by=y_col, ascending=False)[x_col].head(request.limit_count).tolist()
                        title_prefix = f"Top {request.limit_count} "

                    if request.group_others:
                        df[x_col] = df[x_col].apply(lambda x: x if x in top_entities else 'Other')
                        df = df.groupby(x_col, as_index=False).agg({y_col: 'sum'})
                        
                        cats = ['Other'] + [e for e in top_entities if e in df[x_col].values]
                        df[x_col] = pd.Categorical(df[x_col], categories=cats[::-1], ordered=True)
                        title_prefix += "(with Others) "
                    else:
                        df = df[df[x_col].isin(top_entities)]
                        df[x_col] = pd.Categorical(df[x_col], categories=top_entities[::-1], ordered=True)

                gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))
            
                mapping = aes(x=x_col, y=y_col, tooltip=y_col, hover_group=x_col)
                gg = gg + mapping + geom_col(fill="#1890ff", alpha=0.8) + labs(title=f"{title_prefix}{y_col} by {x_col}") + theme(figure_size=(10, 8))
                if request.log_scale:
                    gg = gg + scale_y_log10() + labs(y=f"Log-scaled {y_col}")

        # Histogram
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

        # Frequency Polygon
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

        # Density Plot
        elif request.geom == "density" and request.stat == "density":
            x_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]
            if group_col:
                mapping = aes(x=x_col, fill=group_col)
                gg = gg + mapping + geom_density(alpha=0.5) + labs(title=f"Density Plot of {x_col} by {group_col}")
            else:
                mapping = aes(x=x_col)       
                gg = gg + mapping + geom_density(fill="#722ed1", alpha=0.6, color="#531dab") + labs(title=f"Density Plot of {x_col}")
            if request.log_scale:
                gg = gg + scale_x_log10() + labs(x=f"Log-scaled {x_col}")

        # Choropleth Map
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

        # Scatter Diagram and Bubble Chart
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

        # Line Chart
        elif request.geom == "line" and request.stat == "identity":
            y_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]
            group_col = "Entity_Group"
            x_col = pk_names[-1]
            entity_cols = pk_names[:-1]  # All primary key columns except the last one for grouping
            df[group_col] = df[entity_cols].astype(str).agg(', '.join, axis=1)
            group_display_name = " + ".join(entity_cols)

            title_prefix = ""

            if group_col and df[group_col].nunique() > request.limit_count:
                if request.limit_method == "top":
                    top_groups = df.groupby(group_col)[y_col].max().nlargest(request.limit_count).index.tolist()
                    title_prefix = f"Top {request.limit_count} "
                elif request.limit_method == "bottom":
                    top_groups = df.groupby(group_col)[y_col].max().nsmallest(request.limit_count).index.tolist()
                    title_prefix = f"Bottom {request.limit_count} "
                elif request.limit_method == "random":
                    import random
                    all_groups = df[group_col].dropna().unique().tolist()
                    top_groups = random.sample(all_groups, min(request.limit_count, len(all_groups)))
                    title_prefix = f"Random {request.limit_count} "
                elif request.limit_method == "distributed":
                    sorted_groups = df.groupby(group_col)[y_col].max().sort_values(ascending=False).index.tolist()
                    indices = np.linspace(0, len(sorted_groups) - 1, request.limit_count, dtype=int)
                    top_groups = [sorted_groups[i] for i in indices]
                    title_prefix = f"Distributed {request.limit_count} "
                else:
                    top_groups = df.groupby(group_col)[y_col].max().nlargest(request.limit_count).index.tolist()

                if getattr(request, "group_others", False):
                    df[group_col] = df[group_col].apply(lambda x: x if x in top_groups else 'Other')
                    df = df.groupby([x_col, group_col], as_index=False)[y_col].sum()
                    
                    cats = [g for g in top_groups if g in df[group_col].values] + ['Other']
                    df[group_col] = pd.Categorical(df[group_col], categories=cats, ordered=True)
                    title_prefix += "(with Others) "
                else:
                    df = df[df[group_col].isin(top_groups)]

            df = df.sort_values(by=[group_col, x_col] if group_col else [x_col])

            gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))

            from plotnine import scale_color_manual
            if group_col:
                mapping = aes(x=x_col, y=y_col, color=group_col, group=group_col, tooltip=group_col, hover_group=group_col)
                gg = gg + mapping + geom_line(size=1) + geom_point(size=2, alpha=0.8) + labs(title=f"{title_prefix}Trend of {y_col} by {group_display_name}", color="Entity")
                distinct_colors = [
                    '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4', 
                    '#46f0f0', '#f032e6', '#9a6324', '#fabebe', '#008080', 
                    '#e6beff', '#bcf60c', '#fffac8', '#800000', '#aaffc3', 
                    '#808000', '#ffd8b1', '#000075', '#808080', '#1f77b4'
                ]
                color_count = df[group_col].nunique()
                colors_to_use = (distinct_colors * (color_count // len(distinct_colors) + 1))[:color_count]
                
                gg = gg + scale_color_manual(values=colors_to_use)
            else:
                mapping = aes(x=x_col, y=y_col, tooltip=x_col)
                gg = gg + mapping + geom_line(color="#1890ff", size=1) + geom_point(color="#1890ff", size=2) + labs(title=f"Trend of {y_col}")
            
            if request.log_scale:
                gg = gg + scale_y_log10() + labs(y=f"Log-scaled {y_col}")

        # Boxplot, Violin Plot, Point Range
        elif request.geom in ["boxplot", "violin", "pointrange"]:
            y_col = scalar_cols[0] if scalar_cols else request.selected_columns[0]
            
            if len(pk_names) >= 2:
                entity_cols = pk_names[:-1]
                x_col = "Entity_Group"
                df[x_col] = df[entity_cols].astype(str).agg(', '.join, axis=1)
                x_display_name = " + ".join(entity_cols)
            elif discrete_cols:
                x_col = discrete_cols[0]
                x_display_name = x_col
            else:
                x_col = pk_names[0] if pk_names else columns_to_fetch[0]
                x_display_name = x_col

            title_prefix = ""
            if df[x_col].nunique() > request.limit_count:
                if request.limit_method == "top":
                    top_entities = df.groupby(x_col)[y_col].max().nlargest(request.limit_count).index.tolist()
                    title_prefix = f"Top {request.limit_count} "
                elif request.limit_method == "bottom":
                    top_entities = df.groupby(x_col)[y_col].max().nsmallest(request.limit_count).index.tolist()
                    title_prefix = f"Bottom {request.limit_count} "
                elif request.limit_method == "random":
                    import random
                    all_entities = df[x_col].dropna().unique().tolist()
                    top_entities = random.sample(all_entities, min(request.limit_count, len(all_entities)))
                    title_prefix = f"Random {request.limit_count} "
                elif request.limit_method == "distributed":
                    sorted_entities = df.groupby(x_col)[y_col].max().sort_values(ascending=False).index.tolist()
                    indices = np.linspace(0, len(sorted_entities) - 1, request.limit_count, dtype=int)
                    top_entities = [sorted_entities[i] for i in indices]
                    title_prefix = f"Distributed {request.limit_count} "
                else:
                    top_entities = df.groupby(x_col)[y_col].max().nlargest(request.limit_count).index.tolist()

                if request.group_others:
                    df[x_col] = df[x_col].apply(lambda x: x if x in top_entities else 'Other')
                    title_prefix += "(with Others) "
                else:
                    df = df[df[x_col].isin(top_entities)]

            is_ascending = True if request.limit_method == "bottom" else False
            
            if request.group_others and df[x_col].nunique() > request.limit_count:
                non_other_df = df[df[x_col] != 'Other']
                if not non_other_df.empty:
                    ordered_cats = non_other_df.groupby(x_col)[y_col].max().sort_values(ascending=is_ascending).index.tolist()
                else:
                    ordered_cats = []
                ordered_cats.append('Other')
            else:
                ordered_cats = df.groupby(x_col)[y_col].max().sort_values(ascending=is_ascending).index.tolist()
                
            df[x_col] = pd.Categorical(df[x_col], categories=ordered_cats, ordered=True)
            df = df.sort_values(by=[x_col])
            
            gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))

            if request.geom == "pointrange":
                mapping = aes(x=x_col, y=y_col, color=x_col)
                gg = (gg + mapping 
                      + geom_pointrange(stat="summary", fun_y=np.mean, fun_ymin=np.min, fun_ymax=np.max, size=1, alpha=0.8) 
                      + labs(title=f"{title_prefix}Point Range of {y_col} by {x_display_name}", color=x_display_name, x=x_display_name))

            else:
                mapping = aes(x=x_col, y=y_col, fill=x_col)
                if request.geom == "boxplot":
                    gg = gg + mapping + geom_boxplot(alpha=0.8, outlier_color="red") + labs(title=f"{title_prefix}Boxplot of {y_col} by {x_display_name}", fill=x_display_name, x=x_display_name)
                elif request.geom == "violin":
                    gg = gg + mapping + geom_violin(alpha=0.8, draw_quantiles=[0.25, 0.5, 0.75], scale="width") + labs(title=f"{title_prefix}Violin Plot of {y_col} by {x_display_name}", fill=x_display_name, x=x_display_name)
            
            if request.log_scale:
                gg = gg + scale_y_log10() + labs(y=f"Log-scaled {y_col}")

        # Heatmap Matrix
        elif request.geom == "tile" and request.stat == "identity":
            if len(discrete_cols) + len(pk_names) < 2:
                raise HTTPException(status_code=400, detail="Heatmap Matrix requires at least two categorical columns (discrete or primary key) to define the axes.")
                
            dims = pk_names + [c for c in discrete_cols if c not in pk_names]
            x_col = dims[0]
            y_col = dims[1]
            
            remaining_discretes = [c for c in discrete_cols if c not in [x_col, y_col]]
            
            is_fill_scalar = False
            if scalar_cols:
                fill_col = scalar_cols[0]
                is_fill_scalar = True
            elif remaining_discretes:
                fill_col = remaining_discretes[0]
            else:
                fill_col = None
            
            limit = request.limit_count 
            
            def get_sampled_entities(col_name):
                if request.limit_method == "top":
                    return df[col_name].value_counts().nlargest(limit).index.tolist()
                elif request.limit_method == "bottom":
                    return df[col_name].value_counts().nsmallest(limit).index.tolist()
                elif request.limit_method == "random":
                    import random
                    all_entities = df[col_name].dropna().unique().tolist()
                    return random.sample(all_entities, min(limit, len(all_entities)))
                else:
                    return df[col_name].value_counts().nlargest(limit).index.tolist()

            if df[x_col].nunique() > limit:
                top_x = get_sampled_entities(x_col)
                df = df[df[x_col].isin(top_x)]    
            if df[y_col].nunique() > limit:
                top_y = get_sampled_entities(y_col)
                df = df[df[y_col].isin(top_y)]
                
            gg = ggplot(df) + theme_minimal() + theme(axis_text_x=element_text(rotation=45, hjust=1))
            
            if fill_col:
                mapping = aes(x=x_col, y=y_col, fill=fill_col, tooltip=fill_col)
                gg = gg + mapping + geom_tile(color="white", size=0.5) + labs(title=f"Heatmap: {fill_col} between {x_col} and {y_col}")
                if request.log_scale and is_fill_scalar:
                    gg = gg + scale_fill_continuous(trans='log10') + labs(fill=f"Log {fill_col}")
            else:
                mapping = aes(x=x_col, y=y_col, tooltip=x_col)
                gg = gg + mapping + geom_tile(fill="#1890ff", color="white", size=0.5) + labs(title=f"Relationship Matrix: {x_col} and {y_col}")

        # 2D Binning
        elif request.geom == "tile" and request.stat == "bin_2d":
            if len(scalar_cols) < 2:
                raise HTTPException(status_code=400, detail="2D Binning requires at least two scalar columns to define the axes.")
                
            x_col = scalar_cols[0]
            y_col = scalar_cols[1]
            
            mapping = aes(x=x_col, y=y_col)
            
            gg = ggplot(df) + theme_minimal()
            gg = gg + mapping + geom_bin2d(bins=20) + labs(title=f"2D Density Binning of {y_col} vs {x_col}")
            
            if request.log_scale:
                gg = gg + scale_x_log10() + scale_y_log10() + labs(x=f"Log-scaled {x_col}", y=f"Log-scaled {y_col}")
        
        else:
            raise ValueError(f"Currently not supported: geom={request.geom}, stat={request.stat}")

        # generate ggplot code
        c_x = locals().get('x_col', '...')
        c_y = locals().get('y_col', '...')
        c_group = locals().get('group_col', None)
        c_fill = locals().get('fill_col', None)
        
        aes_elements = []
        if c_x != '...': aes_elements.append(f'x="{c_x}"')
        
        if request.stat != "bin" and request.geom != "density":
            if c_y != '...': aes_elements.append(f'y="{c_y}"')
        
        if request.geom in ["col", "boxplot", "violin", "tile", "map", "histogram", "density"]:
            if c_fill: 
                aes_elements.append(f'fill="{c_fill}"')
            elif c_group: 
                aes_elements.append(f'fill="{c_group}"')
            elif request.geom == "map": 
                aes_elements.append(f'fill="{c_y}"')
        elif request.geom in ["line", "pointrange"]:
            if c_group: 
                aes_elements.append(f'color="{c_group}"')
                
        if request.geom == "point" and request.stat == "identity":
            if len(scalar_cols) == 3:
                aes_elements.append(f'color="{scalar_cols[2]}"')
                aes_elements.append(f'size="{scalar_cols[2]}"')
            elif len(scalar_cols) >= 4:
                aes_elements.append(f'size="{scalar_cols[2]}"')
                aes_elements.append(f'color="{scalar_cols[3]}"')

        aes_str = ", ".join(aes_elements)
        
        geom_str = f"geom_{request.geom}()"
        
        if request.geom == "col":
            if "Stacked" in request.chart_name: 
                geom_str = 'geom_col(position="stack", alpha=0.9)'
            elif "Grouped" in request.chart_name: 
                geom_str = 'geom_col(position="dodge", alpha=0.9)'
            else: 
                geom_str = 'geom_col(fill="#1890ff", alpha=0.8)'
                
        elif request.geom == "bar" and request.stat == "bin":
            if c_group:
                geom_str = 'geom_histogram(bins=30, alpha=0.7, position="identity")'
            else:
                geom_str = 'geom_histogram(bins=30, fill="#52c41a", alpha=0.8, color="green")'
                
        elif request.geom == "line" and request.stat == "bin":
            if c_group:
                geom_str = 'geom_line(stat="bin", bins=30, size=1.2)'
            else:
                geom_str = 'geom_line(stat="bin", bins=30, color="#fa8c16", size=1.2)'
                
        elif request.geom == "density" and request.stat == "density":
            if c_group:
                geom_str = 'geom_density(alpha=0.5)'
            else:
                geom_str = 'geom_density(fill="#722ed1", alpha=0.6, color="#531dab")'
                
        elif request.geom == "point":
            geom_str = 'geom_point(alpha=0.7)'
            
        elif request.geom == "boxplot":
            geom_str = 'geom_boxplot(alpha=0.8, outlier_color="red")'
            
        elif request.geom == "violin":
            geom_str = 'geom_violin(alpha=0.8, draw_quantiles=[0.25, 0.5, 0.75], scale="width")'
            
        elif request.geom == "pointrange":
            geom_str = 'geom_pointrange(stat="summary", fun_y=np.mean, fun_ymin=np.min, fun_ymax=np.max, size=1, alpha=0.8)'
            
        elif request.geom == "tile":
            if request.stat == "bin_2d":
                geom_str = 'geom_bin2d(bins=20)'
            else:
                geom_str = 'geom_tile(color="white", size=0.5)'
                
        elif request.geom == "map":
            geom_str = 'geom_map(color="black", size=0.2)'
            
        scale_str = ""
        if request.log_scale:
            if request.geom == "map" or (request.geom == "tile" and request.stat == "identity"):
                scale_str = "\n    + scale_fill_continuous(trans='log10')"
            elif request.geom == "point" or request.stat == "bin_2d":
                scale_str = "\n    + scale_x_log10()\n    + scale_y_log10()"
            elif request.geom in ["bar", "line", "density"] and request.stat in ["bin", "density"]:
                scale_str = "\n    + scale_x_log10()"
            elif request.geom == "col" and "Bar" in request.chart_name and "Grouped" not in request.chart_name and "Stacked" not in request.chart_name:
                scale_str = "\n    + scale_y_log10()"
            else:
                scale_str = "\n    + scale_y_log10()"

        filter_code_str = ""
        if request.filter_column and request.filter_operator and request.filter_value is not None:
            filter_code_str = f'# Apply filter\ndf = df[df["{request.filter_column}"] {request.filter_operator} {request.filter_value}]\n\n'

        lookup_code_str = ""
        if request.lookups:
            lookup_code_str += "# Apply alternative key replacement\n"
            for lk in request.lookups:
                lookup_code_str += f"df_{lk.target_table} = pd.read_sql_query('SELECT \"{lk.target_join_key}\", \"{lk.target_display_col}\" AS \"_display\" FROM \"{lk.target_table}\"', engine)\n"
                lookup_code_str += f"df = df.merge(df_{lk.target_table}, left_on='{lk.local_column}', right_on='{lk.target_join_key}', how='left')\n"
                lookup_code_str += f"df['{lk.local_column}'] = df['_display'].fillna(df['{lk.local_column}'])\n"
            lookup_code_str += "\n"

        group_others_code_str = ""
        if request.group_others and request.limit_count > 0:
            group_others_code_str += f"# Group remaining data\n"
            group_others_code_str += f"top_entities = df['{c_x}'].head({request.limit_count}).tolist()\n"
            group_others_code_str += f"df['{c_x}'] = df['{c_x}'].apply(lambda x: x if x in top_entities else 'Other')\n"
            if request.geom == "col":
                group_others_code_str += f"df = df.groupby('{c_x}', as_index=False).agg({{{c_y}: 'sum'}})\n"
            group_others_code_str += "\n"

        code_snippet = f'''
import pandas as pd
from plotnine import *

# prepare data and apply sampling as needed
# df = pd.read_sql_query("SELECT ... FROM country", engine)

{filter_code_str}{lookup_code_str}{group_others_code_str}gg = (
    ggplot(df)
    + aes({aes_str})
    + {geom_str}{scale_str}
    + theme_{"void" if request.geom == "map" else "minimal"}()
    + theme(axis_text_x=element_text(rotation=45, hjust=1))
)

print(gg)'''
        # generate HTML string for the plot
        html_string = interactive(gg) + to_html()
        
        return {"html": html_string, "code": code_snippet}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate plot: {str(e)}")