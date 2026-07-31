from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
from sqlalchemy import text
from plotnine import ggplot, aes, geom_col, geom_bar, geom_histogram, geom_line, geom_density, scale_y_log10, theme_minimal, labs, theme, element_text, scale_x_log10
from ninejs import interactive, to_html
from database import engine
from services.metadata_service import extract_database_metadata

router = APIRouter(prefix="/plot", tags=["Plotting"])

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
        
        else:
            raise ValueError(f"Currently not supported: geom={request.geom}, stat={request.stat}")

        # generate HTML string for the plot
        html_string = interactive(gg) + to_html()
        
        return {"html": html_string}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate plot: {str(e)}")