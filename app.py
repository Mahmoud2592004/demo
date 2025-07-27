import streamlit as st
import pandas as pd
import os
import json
from PIL import Image
import plotly.express as px
from datetime import datetime
import numpy as np
from mlxtend.frequent_patterns import apriori, association_rules
import plotly.graph_objects as go

# Get script directory for absolute paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
ORGANIZED_IMAGES_DIR = os.path.join(SCRIPT_DIR, "organized_images")

# Configure page
st.set_page_config(layout="wide", page_title="Egypt Prescription Analytics")

# Custom CSS for elegant styling
st.markdown("""
    <style>
    .card {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .card:hover {
        transform: translateY(-5px);
    }
    .prescription-title {
        font-size: 18px;
        font-weight: bold;
        color: #2c3e50;
        margin-bottom: 10px;
    }
    .prescription-detail {
        font-size: 14px;
        color: #34495e;
        margin: 5px 0;
    }
    .drug-confirmed {
        color: #27ae60;
        font-weight: bold;
    }
    .drug-detected {
        color: #e67e22;
        font-weight: bold;
    }
    .st-expander {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
    .stPlotlyChart {
        margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    try:
        data_path = os.path.join(OUTPUT_DIR, "processed_prescriptions.xlsx")
        df = pd.read_excel(data_path)
        
        # Convert timestamp to datetime
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Parse drugs JSON
        df['drugs_parsed'] = df['drugs'].apply(lambda x: json.loads(x) if isinstance(x, str) and x.strip() != '' else [])
        
        # Update image paths to be absolute
        df['image_path'] = df['image_path'].apply(
            lambda x: os.path.join(SCRIPT_DIR, x) if isinstance(x, str) and not os.path.isabs(x) else x
        )
        
        # Filter to only include prescriptions with valid images
        df = df[df['image_path'].apply(
            lambda x: isinstance(x, str) and x.strip() != '' and os.path.exists(x)
        )]
        
        if df.empty:
            st.warning("No prescriptions with valid images found in the data.")
            st.stop()
        
        return df
    except FileNotFoundError:
        st.error("Data file not found. Please run the processing script first.")
        st.stop()
    except Exception as e:
        st.error(f"Error loading data: {e}")
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

# Show prescriptions without doctors
show_no_doctor = st.sidebar.checkbox("Show prescriptions without doctor", value=True)

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

# Filter out "Not detected" doctors if checkbox is unchecked
if not show_no_doctor:
    filtered_df = filtered_df[filtered_df['doctor_name'] != "Not detected"]

# Dashboard Header
st.title(f"📋 Prescription Analytics: {city}, {governorate}")
st.caption(f"Date Range: {date_range[0]} to {date_range[1]}" if len(date_range) == 2 else "All Dates")

# Key Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Prescriptions", len(filtered_df))

# Calculate drug metrics
if not filtered_df.empty:
    # Explode drugs list
    drug_list = filtered_df['drugs_parsed'].explode().dropna()
    
    # Calculate drug counts
    total_drugs = len(drug_list)
    
    # Calculate confirmed vs detected drugs
    confirmed_drugs = sum(1 for drug in drug_list if drug['score'] == 100)
    detected_drugs = total_drugs - confirmed_drugs
    detection_rate = detected_drugs / total_drugs * 100 if total_drugs > 0 else 0
else:
    total_drugs = 0
    confirmed_drugs = 0
    detected_drugs = 0
    detection_rate = 0

col2.metric("Total Drugs Prescribed", total_drugs)
col3.metric("Confirmed Drugs", confirmed_drugs, f"{confirmed_drugs/total_drugs*100:.1f}%" if total_drugs > 0 else "0%")
col4.metric("Detected Drugs", detected_drugs, f"{detection_rate:.1f}%" if total_drugs > 0 else "0%")

# Doctor Insights
st.subheader("Doctor Insights")
if not filtered_df.empty:
    doctor_counts = filtered_df['doctor_name'].value_counts().reset_index()
    doctor_counts.columns = ['Doctor', 'Prescription Count']
    
    if not show_no_doctor:
        doctor_counts = doctor_counts[doctor_counts['Doctor'] != "Not detected"]
    
    if not doctor_counts.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            top_doctor = doctor_counts.iloc[0]['Doctor'] if len(doctor_counts) > 0 else "N/A"
            st.metric("Top Doctor", top_doctor)
        
        with col2:
            st.metric("Unique Doctors", len(doctor_counts))
        
        fig_doctor = px.bar(
            doctor_counts.head(10), 
            x='Doctor', y='Prescription Count',
            title="Top 10 Doctors by Prescription Count"
        )
        st.plotly_chart(fig_doctor, use_container_width=True)
    else:
        st.info("No doctor data available for the selected filters.")
else:
    st.warning("No data available for the selected filters.")

# Elegant Prescription Gallery
if not filtered_df.empty:
    st.subheader(f"Prescription Gallery ({len(filtered_df)} available)")
    
    for idx, row in filtered_df.iterrows():
        img_path = row['image_path']
        with st.container():
            try:
                # Create card layout
                st.markdown('<div class="card">', unsafe_allow_html=True)
                
                # Prescription title
                st.markdown(
                    f'<div class="prescription-title">Prescription {row["prescription_id"]} ({row["timestamp"].strftime("%Y-%m-%d")})</div>',
                    unsafe_allow_html=True
                )
                
                # Image and details in columns
                col1, col2 = st.columns([2, 3])
                
                with col1:
                    if isinstance(img_path, str) and img_path.strip() != '' and os.path.exists(img_path):
                        img = Image.open(img_path)
                        st.image(img, use_container_width=True)
                    else:
                        st.warning(f"No valid image for prescription {row['prescription_id']}")
                
                with col2:
                    with st.expander("View Details"):
                        st.markdown(f'<div class="prescription-detail">🩺 <b>Doctor:</b> {row["doctor_name"]}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="prescription-detail">🏥 <b>Pharmacy:</b> {row["pharmacy"]}</div>', unsafe_allow_html=True)
                        st.markdown('<div class="prescription-detail">💊 <b>Drugs:</b></div>', unsafe_allow_html=True)
                        
                        for drug in row['drugs_parsed']:
                            if drug['score'] == 100:
                                st.markdown(
                                    f'<div class="prescription-detail drug-confirmed">&nbsp;&nbsp;- {drug["name"]} (Confirmed)</div>',
                                    unsafe_allow_html=True
                                )
                            else:
                                st.markdown(
                                    f'<div class="prescription-detail drug-detected">&nbsp;&nbsp;- {drug["name"]} (Detected: {drug["score"]:.1f}%)</div>',
                                    unsafe_allow_html=True
                                )
                
                st.markdown('</div>', unsafe_allow_html=True)
                
            except Exception as e:
                st.warning(f"Couldn't load prescription {row['prescription_id']}: {str(e)}")
else:
    st.warning("No prescriptions available for the selected filters.")

# Analytics Section
if not filtered_df.empty:
    tab1, tab2, tab3, tab4 = st.tabs(["Drug Analysis", "Detection Insights", "Temporal Trends", "Drug Co-Occurrence"])
    
    with tab1:
        st.subheader("Drug Distribution")
        
        drug_data = []
        for _, row in filtered_df.iterrows():
            for drug in row['drugs_parsed']:
                drug_data.append({
                    'Drug': drug['name'],
                    'Score': drug['score'],
                    'Type': 'Confirmed' if drug['score'] == 100 else 'Detected',
                    'Prescription': row['prescription_id']
                })
        
        drug_df = pd.DataFrame(drug_data)
        
        if not drug_df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                top_drugs = drug_df['Drug'].value_counts().head(10).reset_index()
                top_drugs.columns = ['Drug', 'Count']
                fig_top = px.bar(
                    top_drugs, 
                    x='Drug', y='Count',
                    title="Top 10 Prescribed Drugs",
                    color='Drug'
                )
                st.plotly_chart(fig_top, use_container_width=True)
            
            with col2:
                type_counts = drug_df['Type'].value_counts().reset_index()
                type_counts.columns = ['Type', 'Count']
                fig_type = px.pie(
                    type_counts, 
                    values='Count', names='Type',
                    title="Confirmed vs Detected Drugs",
                    hole=0.4
                )
                st.plotly_chart(fig_type, use_container_width=True)
            
            st.subheader("Detection Confidence")
            fig_score = px.histogram(
                drug_df[drug_df['Type'] == 'Detected'], 
                x='Score',
                nbins=20,
                title="Detected Drugs - Similarity Score Distribution",
                labels={'Score': 'Similarity Score (%)'}
            )
            st.plotly_chart(fig_score, use_container_width=True)
        else:
            st.info("No drug data available for the selected filters.")
    
    with tab2:
        st.subheader("Detection Performance Metrics")
        
        if not drug_df.empty:
            detection_rates = drug_df.groupby('Drug').agg(
                total=('Drug', 'size'),
                detected=('Type', lambda x: (x == 'Detected').sum())
            ).reset_index()
            detection_rates['detection_rate'] = detection_rates['detected'] / detection_rates['total'] * 100
            
            col1, col2 = st.columns(2)
            
            with col1:
                mean_score = drug_df[drug_df['Type'] == 'Detected']['Score'].mean()
                st.metric("Average Detection Score", 
                         f"{mean_score:.1f}%" if not np.isnan(mean_score) else "N/A",
                         "For detected drugs")
            
            with col2:
                mean_rate = detection_rates['detection_rate'].mean()
                st.metric("Detection Rate", 
                         f"{mean_rate:.1f}%" if not np.isnan(mean_rate) else "N/A",
                         "Percentage of drugs requiring detection")
            
            st.subheader("Drugs with Lowest Detection Confidence")
            low_confidence = drug_df[drug_df['Type'] == 'Detected'].sort_values('Score').head(10)
            if not low_confidence.empty:
                st.dataframe(low_confidence[['Drug', 'Score', 'Prescription']])
            else:
                st.info("No detected drugs with low confidence scores.")
            
            st.subheader("Most Commonly Detected Drugs")
            top_detected = detection_rates.sort_values('detected', ascending=False).head(10)
            if not top_detected.empty:
                fig_detected = px.bar(
                    top_detected, 
                    x='Drug', y='detected',
                    title="Top 10 Detected Drugs",
                    labels={'detected': 'Detection Count'}
                )
                st.plotly_chart(fig_detected, use_container_width=True)
            else:
                st.info("No detected drugs available.")
        else:
            st.info("No drug detection data available for the selected filters.")
    
    with tab3:
        st.subheader("Prescription Trends Over Time")
        
        daily_counts = filtered_df.set_index('timestamp').resample('D').size().reset_index()
        daily_counts.columns = ['Date', 'Count']
        
        fig_daily = px.line(
            daily_counts, 
            x='Date', y='Count',
            title="Daily Prescriptions",
            markers=True
        )
        st.plotly_chart(fig_daily, use_container_width=True)
        
        filtered_df['detection_required'] = filtered_df['drugs_parsed'].apply(
            lambda x: any(d['score'] < 100 for d in x) if x else False
        )
        detection_trends = filtered_df.groupby(
            filtered_df['timestamp'].dt.date
        )['detection_required'].mean().reset_index()
        detection_trends.columns = ['Date', 'Detection Rate']
        detection_trends['Detection Rate'] *= 100
        
        fig_detection_trend = px.line(
            detection_trends, 
            x='Date', y='Detection Rate',
            title="Daily Drug Detection Rate",
            labels={'Detection Rate': 'Detection Rate (%)'}
        )
        st.plotly_chart(fig_detection_trend, use_container_width=True)
    
    with tab4:
        st.subheader("Drugs Commonly Prescribed Together")
        
        # Prepare data for association rule mining
        drug_baskets = filtered_df['drugs_parsed'].apply(
            lambda x: [drug['name'] for drug in x] if x else []
        ).tolist()
        
        # Create a one-hot encoded DataFrame
        unique_drugs = set()
        for basket in drug_baskets:
            unique_drugs.update(basket)
        unique_drugs = sorted(unique_drugs)
        
        one_hot = pd.DataFrame(0, index=range(len(drug_baskets)), columns=unique_drugs)
        for idx, basket in enumerate(drug_baskets):
            for drug in basket:
                one_hot.loc[idx, drug] = 1
        
        # Apply Apriori algorithm
        min_support = 0.01  # Adjust based on dataset size
        frequent_itemsets = apriori(one_hot, min_support=min_support, use_colnames=True)
        
        if not frequent_itemsets.empty:
            # Generate association rules
            rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.1)
            
            if not rules.empty:
                # Prepare data for visualization
                rules['antecedents'] = rules['antecedents'].apply(lambda x: ', '.join(x))
                rules['consequents'] = rules['consequents'].apply(lambda x: ', '.join(x))
                rules_display = rules[['antecedents', 'consequents', 'support', 'confidence']].head(10)
                
                # Display table of top rules
                st.subheader("Top Drug Combinations")
                st.dataframe(
                    rules_display.rename(columns={
                        'antecedents': 'Drugs Prescribed',
                        'consequents': 'Associated Drugs',
                        'support': 'Support (%)',
                        'confidence': 'Confidence (%)'
                    }).style.format({
                        'Support (%)': '{:.2%}',
                        'Confidence (%)': '{:.2%}'
                    })
                )
                
                # Create heatmap for drug co-occurrence
                co_occurrence = one_hot.T.dot(one_hot)
                np.fill_diagonal(co_occurrence.values, 0)  # Remove self-co-occurrences
                
                fig_co = go.Figure(data=go.Heatmap(
                    z=co_occurrence.values,
                    x=co_occurrence.columns,
                    y=co_occurrence.index,
                    colorscale='Viridis',
                    text=co_occurrence.values,
                    texttemplate="%{text}",
                    textfont={"size": 10}
                ))
                fig_co.update_layout(
                    title="Drug Co-Occurrence Heatmap",
                    xaxis_title="Drug",
                    yaxis_title="Drug",
                    height=600,
                    width=800
                )
                st.plotly_chart(fig_co, use_container_width=True)
            else:
                st.info("No significant drug co-occurrences found with the current filters.")
        else:
            st.info("No frequent drug combinations found with the current filters.")
else:
    st.warning("No prescriptions available for the selected filters.")
