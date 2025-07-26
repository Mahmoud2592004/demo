import streamlit as st
import pandas as pd
import os
from PIL import Image
import plotly.express as px
from datetime import datetime

# Configure page
st.set_page_config(layout="wide", page_title="Egypt Prescription Analytics")

@st.cache_data
def load_data():
    try:
        df = pd.read_excel("output/prescription_data.xlsx")
        # Convert timestamp to datetime if it's not already
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except FileNotFoundError:
        st.error("Data file not found. Please run generate_data.py first")
        st.stop()

df = load_data()

# Sidebar filters
st.sidebar.header("Filters")

# Date range filter
min_date = df['timestamp'].min().date()
max_date = df['timestamp'].max().date()
date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Governorate and city filters
governorate = st.sidebar.selectbox(
    "Governorate", 
    sorted(df['governorate'].unique()),
    index=0
)

cities = df[df['governorate'] == governorate]['city'].unique()
city = st.sidebar.selectbox("City", sorted(cities))

# Apply filters
if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = df[
        (df['governorate'] == governorate) & 
        (df['city'] == city) &
        (df['timestamp'].dt.date >= start_date) &
        (df['timestamp'].dt.date <= end_date)
    ]
else:
    filtered_df = df[
        (df['governorate'] == governorate) & 
        (df['city'] == city)
    ]

# Dashboard Header
st.title(f"📋 Prescription Analytics: {city}, {governorate}")
st.caption(f"Date Range: {date_range[0]} to {date_range[1]}" if len(date_range) == 2 else "All Dates")

# Key Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Prescriptions", len(filtered_df))

# Calculate total drugs (sum of all drugs in all prescriptions)
if not filtered_df.empty:
    total_drugs = filtered_df['drugs'].str.split(', ').explode().count()
else:
    total_drugs = 0

col2.metric("Total Drugs Prescribed", total_drugs)
col3.metric("Average Drugs per Prescription", 
           f"{total_drugs/len(filtered_df):.1f}" if len(filtered_df) > 0 else "0")
col4.metric("Top Pharmacy", 
           filtered_df['pharmacy'].mode()[0] if len(filtered_df) > 0 else "N/A")

# Image Gallery
if not filtered_df.empty:
    st.subheader(f"Prescription Images ({len(filtered_df)} found)")
    cols = st.columns(3)  # 3-column layout

    for idx, row in filtered_df.iterrows():
        img_path = row.get('image_path', '')
        if img_path and os.path.exists(img_path):
            with cols[idx % 3]:
                try:
                    img = Image.open(img_path)
                    st.image(
                        img,
                        caption=f"""
                        Date: {row['timestamp'].strftime('%Y-%m-%d')}
                        """,
                        use_container_width=True
                    )
                    st.caption(f"""
                        **Drugs:** {row['drugs']}  
                        **Pharmacy:** {row['pharmacy']}
                    """)
                except Exception as e:
                    st.warning(f"Couldn't load image: {img_path}")
        else:
            with cols[idx % 3]:
                st.warning("Image not available")

# Analytics Section
if not filtered_df.empty:
    tab1, tab2 = st.tabs(["Drug Analysis", "Temporal Trends"])
    
    with tab1:
        st.subheader("Drug Distribution")
        
        # Calculate drug frequencies
        drug_counts = filtered_df['drugs'].str.split(', ').explode().value_counts().reset_index()
        drug_counts.columns = ['Drug', 'Count']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Unique Drugs", drug_counts.shape[0])
            fig1 = px.bar(drug_counts.head(10), 
                         x='Drug', y='Count',
                         title="Top 10 Prescribed Drugs")
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            st.metric("Most Common Combination", 
                     filtered_df['drugs'].value_counts().index[0] if not filtered_df.empty else "N/A")
            fig2 = px.pie(drug_counts, 
                         values='Count', names='Drug',
                         title="Drug Distribution")
            st.plotly_chart(fig2, use_container_width=True)
    
    with tab2:
        st.subheader("Prescription Trends Over Time")
        
        # Daily count
        daily_counts = filtered_df.set_index('timestamp').resample('D').size()
        fig3 = px.line(daily_counts, 
                      title="Daily Prescriptions",
                      labels={'value': 'Number of Prescriptions'})
        st.plotly_chart(fig3, use_container_width=True)
        
        # Weekly patterns
        filtered_df['day_of_week'] = filtered_df['timestamp'].dt.day_name()
        weekly = filtered_df['day_of_week'].value_counts()
        fig4 = px.bar(weekly, 
                     title="Prescriptions by Day of Week",
                     labels={'index': 'Day', 'value': 'Count'})
        st.plotly_chart(fig4, use_container_width=True)
else:
    st.warning("No data available for selected filters")

# Run with: streamlit run app.py