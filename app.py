import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import os 
from dotenv import load_dotenv

load_dotenv()

# Set page layout to wide for a cleaner dashboard look
st.set_page_config(page_title="Chinook Music Store Dashboard", layout="wide")

# 1. Fixed Database Connection URL (Changed colon to slash before DB_NAME)
DATABASE_URL = f"postgresql://{os.getenv('DB_USERNAME')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

# Optimized Data Loading with Caching
@st.cache_data  
def load_data():
    engine = create_engine(DATABASE_URL)
    query = """
    SELECT 
        i.invoice_id, 
        i.invoice_date, 
        i.billing_country,
        il.unit_price * il.quantity AS line_total,
        art.name AS artist_name
    FROM invoice i
    JOIN invoice_line il ON i.invoice_id = il.invoice_id
    JOIN track t ON il.track_id = t.track_id
    JOIN album alb ON t.album_id = alb.album_id
    JOIN artist art ON alb.artist_id = art.artist_id;
    """
    # Wrapped query in text() for SQLAlchemy 2.0 compatibility
    with engine.connect() as conn:
        df = pd.read_sql_query(text(query), con=conn)
    
    # Ensure invoice_date is datetime format
    df['invoice_date'] = pd.to_datetime(df['invoice_date'])
    
    # Cache the monthly trend string parsing inside the function to speed up reruns
    df['Month'] = df['invoice_date'].dt.to_period('M').astype(str)
    
    return df

# Load the raw dataset
try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    st.stop()

# -------------------------------------------------------------
# 2. SIDEBAR FILTERS
# -------------------------------------------------------------
st.sidebar.header("Dashboard Filters")

# Country Filter (Multi-select)
all_countries = sorted(df_raw['billing_country'].unique())
selected_countries = st.sidebar.multiselect(
    "Select Country", 
    options=all_countries, 
    default=all_countries
)

# Date Range Filter
min_date = df_raw['invoice_date'].min().date()
max_date = df_raw['invoice_date'].max().date()
selected_date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Filter the dataset based on sidebar selections
df_filtered = df_raw[df_raw['billing_country'].isin(selected_countries)]

# UI/UX Improvement: Handle temporary single-date selections gracefully
if isinstance(selected_date_range, tuple):
    if len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
        df_filtered = df_filtered[
            (df_filtered['invoice_date'].dt.date >= start_date) & 
            (df_filtered['invoice_date'].dt.date <= end_date)
        ]
    elif len(selected_date_range) == 1:
        st.sidebar.info("Please select an end date to apply the date filter.")

# -------------------------------------------------------------
# 3. MAIN DASHBOARD DISPLAY
# -------------------------------------------------------------
st.title("🎵 Chinook Digital Music Store Insights")
st.markdown("An executive interactive dashboard to explore global sales metrics.")
st.write("---")

# Key Business Metrics (KPIs) at a glance
col1, col2, col3, col4 = st.columns(4)
with col1:
    total_revenue = df_filtered['line_total'].sum()
    st.metric(label="Total Revenue", value=f"${total_revenue:,.2f}")
with col2:
    total_orders = df_filtered['invoice_id'].nunique()
    st.metric(label="Total Orders Placed", value=f"{total_orders:,}")
with col3:
    unique_artists = df_filtered['artist_name'].nunique()
    st.metric(label="Artists Sold", value=f"{unique_artists}")
with col4:
    countries_count = df_filtered['billing_country'].nunique()
    st.metric(label="Active Markets (Countries)", value=f"{countries_count}")

st.write("---")

# -------------------------------------------------------------
# 4. VISUALIZATIONS
# -------------------------------------------------------------

# Layout Row 1: Top Artists & Country Revenue
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Top 10 Artists by Revenue")
    top_10_artists = (
        df_filtered.groupby('artist_name')['line_total']
        .sum()
        .reset_index()
        .sort_values('line_total', ascending=True)
        .tail(10)
    )
    fig_artists = px.bar(
        top_10_artists, 
        x='line_total', 
        y='artist_name', 
        orientation='h',
        labels={'line_total': 'Revenue ($)', 'artist_name': 'Artist'},
        color='line_total',
        color_continuous_scale='Viridis'
    )
    fig_artists.update_layout(showlegend=False, yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_artists, use_container_width=True)

with chart_col2:
    st.subheader("Revenue by Country")
    country_revenue = (
        df_filtered.groupby('billing_country')['line_total']
        .sum()
        .reset_index()
        .sort_values('line_total', ascending=False)
    )
    fig_country = px.bar(
        country_revenue, 
        x='billing_country', 
        y='line_total',
        labels={'line_total': 'Revenue ($)', 'billing_country': 'Country'},
        color='line_total'
    )
    st.plotly_chart(fig_country, use_container_width=True)

# Layout Row 2: Monthly Revenue Trend
st.subheader("Monthly Revenue Trend")

# Streamlined: 'Month' column is now pre-processed inside load_data()
monthly_trend = df_filtered.groupby('Month')['line_total'].sum().reset_index()

fig_trend = px.line(
    monthly_trend, 
    x='Month', 
    y='line_total',
    labels={'line_total': 'Revenue ($)', 'Month': 'Timeline (Monthly)'},
    markers=True
)
fig_trend.update_traces(line_color='#FF4B4B') 
st.plotly_chart(fig_trend, use_container_width=True)

st.header("Raw Invoice Data")
st.dataframe(df_filtered, use_container_width=True)