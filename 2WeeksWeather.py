import streamlit as st
import pandas as pd
import requests
import json
import os

# ページの設定
st.set_page_config(page_title="気象監視ダッシュボード 2WeeksWeather ", layout="wide")
st.title("気象監視ダッシュボード 2WeeksWeather ")

# 保存先ファイルのパス設定（プログラムと同じフォルダに作成されます）
SAVE_FILE = "selected_locations.json"

# =================================================================
# 0. お気に入りデータの読み込み・保存関数
# =================================================================
def load_saved_locations():
    """ファイルから保存されたお気に入り地域を読み込む"""
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_locations(locations):
    """お気に入り地域をファイルに保存する"""
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(locations, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"お気に入りの保存に失敗しました: {e}")

# =================================================================
# 1. 外部CSVマスターデータの読み込み（キャッシュ機能付き）
# =================================================================
@st.cache_data
def load_location_master():
    csv_path = "c:/Users/kouki/OneDrive/デスクトップ/python_code/2WeeksWeather/all_locations.csv"
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
        return df
    except FileNotFoundError:
        st.error(f"CSVファイルが見つかりません: {csv_path}")
        return pd.DataFrame({
            "都道府県": ["東京都", "大阪府"],
            "詳細エリア": ["千代田区周辺", "大阪市周辺"],
            "気象庁コード": ["130010", "270000"],
            "位置情報": ["Tokyo", "Osaka"]
        })

df_master = load_location_master()

# =================================================================
# 2. 記憶機能（session_state）の初期化（ファイルから自動読込）
# =================================================================
if "selected_locations" not in st.session_state:
    # 💡 初回起動時に保存ファイルからデータを復元する
    st.session_state.selected_locations = load_saved_locations()

# =================================================================
# 3. 都道府県 ＞ 詳細エリア の2段階絞り込み選択UI
# =================================================================
st.subheader("🔍 監視したい地域を絞り込んで追加")
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    pref_list = sorted(df_master["都道府県"].unique())
    selected_pref = st.selectbox("① 都道府県を選択", pref_list)

with col2:
    filtered_df = df_master[df_master["都道府県"] == selected_pref]
    city_options = filtered_df["詳細エリア"].unique()
    selected_city = st.selectbox("② 詳細エリアを選択", city_options)

with col3:
    target_row = filtered_df[filtered_df["詳細エリア"] == selected_city].iloc[0]
    
    st.write("") 
    st.write("") 
    if st.button("➕ 一覧に追加", use_container_width=True):
        location_id = f"【{selected_pref}】 {selected_city}"
        
        if not any(loc["id"] == location_id for loc in st.session_state.selected_locations):
            st.session_state.selected_locations.append({
                "id": location_id,
                "vc_name": target_row["位置info" if "位置info" in target_row else "位置情報"],
                "jma_code": str(target_row["気象庁コード"])
            })
            # 💡 リストが更新されたらファイルへ自動保存
            save_locations(st.session_state.selected_locations)
            st.toast(f"{selected_city} を追加保存しました！") 
            st.rerun()
        else:
            st.warning("既に一覧に追加されています。")

# =================================================================
# 4. 気象データの取得・判定関数
# =================================================================
def get_weather_data(location):
    api_key = "PQGN5H3F6UQVEHVARTSVJRZX8" 
    url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}/next14days?unitGroup=metric&elements=datetime,temp,cloudcover,precipprob,conditions&key={api_key}&contentType=json"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def get_jma_weather(code):
    try:
        jma_url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{code}.json"
        res = requests.get(jma_url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            jma_forecast = {}
            for area_data in data:
                if 'timeSeries' in area_data:
                    for ts in area_data['timeSeries']:
                        for area in ts.get('areas', []):
                            if 'pops' in area:
                                times = ts['timeDefines']
                                pops = area['pops']
                                for t, pop in zip(times, pops):
                                    dt = pd.to_datetime(t)
                                    date_str = dt.strftime("%m/%d")
                                    jma_forecast[date_str] = f"JMA:{pop}%"
            return jma_forecast
    except:
        pass
    return {}

def style_weather(val):
    try:
        main_part = val.split("|")[0].strip()
        cloud_val = int(main_part.split("雲:")[1].split("%")[0])
        rain_val = int(main_part.split("雨:")[1].split("%")[0])
        
        # 💡 ご報告いただいたカスタムカラーに更新
        if rain_val >= 50:
            return "background-color: #D64933; color: white"
        elif cloud_val <= 30:
            return "background-color: #92DCE5; color: black"
    except:
        pass
    return ""

# =================================================================
# 5. 追加された地域の全データ一括処理と表示
# =================================================================
st.write("---") 

if st.session_state.selected_locations:
    
    if st.button("🗑️ 選択一覧をすべてクリア"):
        st.session_state.selected_locations = []
        # 💡 クリアされた状態（空リスト）を保存ファイルに反映
        save_locations([])
        st.rerun()

    weather_matrix = {}
    WEEK_DAYS = ["月", "火", "水", "木", "金", "土", "日"]
    
    with st.spinner("追加されたすべての地域の最新データを収集中..."):
        for loc in st.session_state.selected_locations:
            display_id = loc["id"]
            vc_name = loc["vc_name"]
            jma_code = loc["jma_code"]
            
            vc_data = get_weather_data(vc_name)
            jma_data = get_jma_weather(jma_code)
            
            if vc_data:
                location_forecasts = {}
                for day in vc_data.get('days', []):
                    date_raw = day['datetime']
                    
                    try:
                        dt = pd.to_datetime(date_raw)
                        day_of_week = WEEK_DAYS[dt.weekday()]
                        jma_key = dt.strftime("%m/%d")
                        date_str = f"{jma_key}({day_of_week})"
                    except:
                        jma_key = date_raw.split("-")[1].zfill(2) + "/" + date_raw.split("-")[2].zfill(2)
                        date_str = jma_key
                    
                    cloud = int(day.get('cloudcover', 0))
                    vc_rain = int(day.get('precipprob', 0))
                    
                    cell_text = f"雲:{cloud}%/雨:{vc_rain}%"
                    if jma_key in jma_data:
                        cell_text += f" | {jma_data[jma_key]}"
                    
                    location_forecasts[date_str] = cell_text
                
                weather_matrix[display_id] = location_forecasts
                
    if weather_matrix:
        df = pd.DataFrame(weather_matrix).T
        st.subheader("📊 選択エリアの2週間気象比較マトリクス（青:撮影日和 / 赤:注意）")
        styled_df = df.style.map(style_weather)
        st.dataframe(styled_df, use_container_width=True)
        st.caption("※雲量30%以下は青、降水確率 50%以上は赤で表示しています。")
        st.caption("※直近2日間は気象庁の降水確率（JMA）を併記しています")
    else:
        st.warning("気象データの取得に失敗しました。APIキーまたはネットワークを確認してください。")
else:
    st.info("上のドロップダウンから地域を選び、「➕ 一覧に追加」ボタンを押してください。")
st.caption("※データは Visual Crossing API から自動取得しています。")
st.caption("ver1.1.0 irie 2026/05/25") # お気に入り保存機能追加に伴いマイナーバージョン更新