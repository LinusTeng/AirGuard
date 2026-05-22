import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

st.set_page_config(page_title="AirGuard AI 智慧監測", layout="wide")

@st.cache_data(ttl=600)
def load_data():
    URL = "https://raw.githubusercontent.com/LinusTeng/AirGuard/main/airguard_all_taiwan_data.csv"
    
    # 加入雙重保險機制：先讀雲端，失敗則讀本地
    try:
        df = pd.read_csv(URL)
    except Exception as e_url:
        st.warning(f"雲端讀取異常 ({e_url})，嘗試讀取本地備份...")
        if os.path.exists("airguard_all_taiwan_data.csv"):
            df = pd.read_csv("airguard_all_taiwan_data.csv")
        else:
            st.error("❌ 雲端與本地皆無資料。請確認 GitHub Actions 是否執行成功。")
            return None

    df['publishtime'] = pd.to_datetime(df['publishtime']).dt.floor('min')
    df['pm2.5'] = pd.to_numeric(df['pm2.5'], errors='coerce')
    df = df.dropna(subset=['pm2.5', 'publishtime'])
    
    df = df.groupby(['publishtime', 'sitename', 'county'], as_index=False).agg({
        'pm2.5': 'mean', 'latitude': 'first', 'longitude': 'first', 'aqi': 'first', 'status': 'first'
    })
    return df.sort_values(['sitename', 'publishtime'])

def main():
    st.title("🛡️ AirGuard AI 智慧空品監測平台")
    st.caption("數據驅動架構：GitHub Actions ETL | 機器學習引擎：Scikit-Learn Random Forest")

    df = load_data()
    if df is None or df.empty:
        return

    st.sidebar.header("控制面板")
    view_mode = st.sidebar.radio("切換視圖", ["🌍 全台熱點地圖", "📊 AI 深度分析與預測對比"])
    
    latest_time = df['publishtime'].max()
    latest_df = df[df['publishtime'] == latest_time]

    if view_mode == "🌍 全台熱點地圖":
        st.subheader(f"📍 全台空氣品質即時分佈 ({latest_time})")
        fig_map = px.scatter_mapbox(
            latest_df, lat="latitude", lon="longitude", color="pm2.5", size="pm2.5", hover_name="sitename", 
            color_continuous_scale="Reds", size_max=18, zoom=6.2, center={"lat": 23.7, "lon": 120.9},
            mapbox_style="carto-darkmatter", height=600
        )
        fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
        st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.success("🌿 清新站點 Top 5")
            st.dataframe(latest_df.nsmallest(5, 'pm2.5')[['sitename', 'county', 'pm2.5']], hide_index=True)
        with c2:
            st.error("😷 污染站點 Top 5")
            st.dataframe(latest_df.nlargest(5, 'pm2.5')[['sitename', 'county', 'pm2.5']], hide_index=True)

    else:
        all_counties = sorted(df['county'].unique())
        sel_county = st.sidebar.selectbox("選擇縣市", all_counties, index=all_counties.index("臺中市") if "臺中市" in all_counties else 0)
        
        county_df = df[df['county'] == sel_county]
        sel_site = st.sidebar.selectbox("選擇測站", sorted(county_df['sitename'].unique()))
        
        site_df = county_df[county_df['sitename'] == sel_site].copy().sort_values('publishtime')
        
        st.subheader(f"📊 機器學習時序預測：{sel_county} - {sel_site}")
        
        # 特徵工程
        site_df['hour'] = site_df['publishtime'].dt.hour
        site_df['dayofweek'] = site_df['publishtime'].dt.dayofweek
        site_df['pm2.5_lag_1'] = site_df['pm2.5'].shift(1)
        
        ml_df = site_df.dropna(subset=['pm2.5_lag_1'])
        
        if len(ml_df) >= 15:
            features = ['hour', 'dayofweek', 'pm2.5_lag_1']
            X = ml_df[features]
            y = ml_df['pm2.5']
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
            
            rf_model = RandomForestRegressor(n_estimators=50, random_state=42)
            rf_model.fit(X_train, y_train)
            rf_preds = rf_model.predict(X_test)
            rf_mae = mean_absolute_error(y_test, rf_preds)
            
            lr_model = LinearRegression()
            lr_model.fit(X_train, y_train)
            lr_preds = lr_model.predict(X_test)
            lr_mae = mean_absolute_error(y_test, lr_preds)
            
            current_pm = site_df['pm2.5'].iloc[-1]
            next_hour = (site_df['publishtime'].iloc[-1].hour + 1) % 24
            next_dayofweek = site_df['publishtime'].iloc[-1].dayofweek
            
            future_features = pd.DataFrame([[next_hour, next_dayofweek, current_pm]], columns=features)
            rf_next_pred = rf_model.predict(future_features)[0]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("當前實測值", f"{current_pm} µg/m³")
            m2.metric("💡 AI 隨機森林預測 (下一小時)", f"{max(0, rf_next_pred):.1f} µg/m³", delta=f"{rf_next_pred-current_pm:.1f}")
            
            with m3:
                st.markdown("**🏆 模型準確度對比 (MAE)**")
                st.markdown(f"- 🤖 **隨機森林**: `{rf_mae:.2f}`")
                st.markdown(f"- 📈 **線性迴歸**: `{lr_mae:.2f}`")
            
            plot_df = ml_df.tail(len(y_test)).copy()
            plot_df['隨機森林預測'] = rf_preds
            plot_df['線性迴歸預測'] = lr_preds
            
            fig_trend = px.line(plot_df, x='publishtime', y=['pm2.5', '隨機森林預測', '線性迴歸預測'], 
                                labels={'value': 'PM2.5 (µg/m³)', 'variable': '數據來源'},
                                title="🔬 模型預測與實際測值比對")
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("📊 該測站有效數據累積中 (需至少 15 筆)...")

if __name__ == "__main__":
    main()
