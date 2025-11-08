import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt


st.title("Synapsys IQ Product Analytics Dashboard")
st.sidebar.title("Synapsys IQ Product Analytics Dashboard")

#radio-button toggle in Streamlit
import streamlit as st
import plotly.express as px

st.subheader("Top 15 ICBs by Quantity / Cost")

period = st.radio(
    "Select time period:",
    ("Latest Month", "Last 12 Months", "All Time"),
)

if period == "Latest Month":
    data = regional_latest
elif period == "Last 12 Months":
    data = regional_ytd
else:
    data = regional_alltime

fig = px.bar(
    data.head(15),
    x="QTY", y="ICB_Name",
    orientation="h",
    color="NIC",
    labels={"QTY": "Quantity", "ICB_Name": "ICB", "NIC": "Total NIC (£)"},
    title=f"Top 15 ICBs by Quantity — {period}",
)
fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=700)

st.plotly_chart(fig, use_container_width=True)