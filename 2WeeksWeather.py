import streamlit as st
import pandas as pd
import requests
import json
import os

# ページの設定
st.set_page_config(page_title="気象監視ダッシュボード 2WeeksWeather", layout="wide")
st.title("気象監視ダッシュボード 2WeeksWeather")

# =================================================================
# 0. パス設定とお気に入り（プロジェクト）データの読み込み・保存関数
# =================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(current_dir, "selected_locations.json")

def load_all_projects():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_all_projects(projects_dict):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(projects_dict, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"プロジェクトの保存に失敗しました: {e}")

# =================================================================
# 1. 外部CSVマスターデータの読み込み
# =================================================================
@st.cache_data
def load_location_master():
    csv_path = os.path.join(current_dir, "all_locations.csv")
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
        return df
    except FileNotFoundError:
        st.error("マスターCSVファイルが見つかりません。")
        return pd.DataFrame()

df_master = load_location_master()
all_projects = load_all_projects()

if "selected_locations" not in st.session_state:
    st.session_state.selected_locations = []

# =================================================================
# 2. プロジェクトの読み込み・保存UI
# =================================================================
st.write("---")
st.subheader("📂 プロジェクト（お気に入り編成）の管理")

col_p1, col_p2 = st.columns(2)

with col_p1:
    st.markdown("**📥 保存されたプロジェクトを呼び出す**")
    project_list = list(all_projects.keys())
    if project_list:
        selected_project = st.selectbox("呼び出すプロジェクトを選択", ["（未選択）"] + project_list)
        if selected_project != "（未選択）":
            if st.button("📁 このプロジェクトを展開", use_container_width=True):
                st.session_state.selected_locations = all_projects[selected_project]
                st.toast(f"プロジェクト「{selected_project}」を読み込みました。")
                st.rerun()
    else:
        st.info("保存されたプロジェクトはまだありません。")

with col_p2:
    st.markdown("**💾 現在の一覧をプロジェクトとして保存**")
    new_project_name = st.text_input("プロジェクト名を入力", "")
    if st.button("💾 プロジェクト名をつけて保存", use_container_width=True):
        if not new_project_name.strip():
            st.error("プロジェクト名を入力してください。")
        elif not st.session_state.selected_locations:
            st.error("保存する地域が一覧にありません。")
        else:
            all_projects[new_project_name.strip()] = st.session_state.selected_locations
            save_all_projects(all_projects)
            st.toast(f"プロジェクト「{new_project_name}」として保存しました！")
            st.rerun()

# =================================================================
# 3. 都道府県 ＞ 詳細エリア の2段階絞り込み選択UI
# =================================================================
st.write("---")
st.subheader("🔍 監視したい地域を絞り込んで追加")

if not df_master.empty:
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
                st.toast(f"{selected_city} を追加しました。") 
                st.rerun()
            else:
                st.warning("既に一覧に追加されています。")
else:
    st.error("CSVマスターデータが読み込めないため、地域選択ができません。")

# =================================================================
# 4. 気象データの取得・判定関数
# =================================================================
def get_weather_data(location):
    try:
        api_key = st.secrets["vc_api_key"]
    except:
        st.error("Streamlit CloudのSecretsに 'vc_api_key' が設定されていません。")
        return None
        
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

def get_cell_style(cloud, rain):
    """HTMLテーブル用の背景色スタイル判定"""
    if rain >= 50:
        return "background-color: #D64933; color: white;"
    elif cloud <= 30:
        return "background-color: #92DCE5; color: black;"
    return "background-color: #1E2530; color: #E0E0E0;"

def style_weather_pc(val):
    """従来のPCデータフレーム用の色判定"""
    try:
        main_part = str(val).split("|")[0].strip()
        cloud_val = int(main_part.split("雲:")[1].split("%")[0])
        rain_val = int(main_part.split("雨:")[1].split("%")[0])
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
        st.rerun()

    weather_raw_matrix = {}
    WEEK_DAYS = ["月", "火", "水", "木", "金", "土", "日"]
    
    with st.spinner("最新データを収集中..."):
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
                    
                    location_forecasts[date_str] = {
                        "cloud": int(day.get('cloudcover', 0)),
                        "vc_rain": int(day.get('precipprob', 0)),
                        "jma": jma_data.get(jma_key, "")
                    }
                weather_raw_matrix[display_id] = location_forecasts
                
    if weather_raw_matrix:
        st.subheader("📊 選択エリアの2週間気象比較マトリクス")
        is_mobile_view = st.checkbox("📱 スマートフォンの場合はチェック（縦横を入れ替える）", value=False)
        
        if is_mobile_view:
            # ==========================================
            # 📱 スマホモード：HTMLを組んで完璧に3行化する
            # ==========================================
            dates = list(next(iter(weather_raw_matrix.values())).keys())
            
            # 短縮された地域名リストを生成
            short_loc_ids = []
            loc_keys = list(weather_raw_matrix.keys())
            for name in loc_keys:
                s_name = name.split("】")[-1].strip().replace("周辺", "")
                short_loc_ids.append(s_name)
            
            # 超コンパクト設計のHTMLテーブル作成
            html = """
            <div style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch;">
                <table style="width: 100%; min-width: 320px; border-collapse: collapse; font-size: 12px; font-family: sans-serif; text-align: center; line-height: 1.2;">
                    <thead>
                        <tr style="background-color: #262730; color: #FFFFFF;">
                            <th style="padding: 6px 4px; border: 1px solid #464855; min-width: 65px;">日付</th>
            """
            for s_name in short_loc_ids:
                html += f'<th style="padding: 6px 4px; border: 1px solid #464855; min-width: 85px;">{s_name}</th>'
            html += "</tr></thead><tbody>"
            
            # 行（日付）ごとにデータを埋め込む
            for date in dates:
                html += f'<tr><td style="padding: 6px 4px; border: 1px solid #464855; background-color: #262730; color: #E0E0E0; font-weight: bold;">{date}</td>'
                for loc_id in loc_keys:
                    data = weather_raw_matrix[loc_id][date]
                    cloud = data["cloud"]
                    vc_rain = data["vc_rain"]
                    jma = data["jma"] if data["jma"] else "&nbsp;"
                    
                    bg_style = get_cell_style(cloud, vc_rain)
                    
                    # 🔴 ここで明示的に<br>タグを入れ、絶対に3行に分割する
                    html += f"""
                    <td style="padding: 6px 4px; border: 1px solid #464855; {bg_style}">
                        雲:{cloud}%<br>
                        雨:{vc_rain}%<br>
                        <span style="font-size: 11px; opacity: 0.9;">{jma}</span>
                    </td>
                    """
                html += "</tr>"
            html += "</tbody></table></div>"
            
            # 完成したHTMLを画面に展開
            st.components.v1.html(html, height=650, scrolling=True)
            
        else:
            # ==========================================
            # 💻 PCモード：従来の使い慣れたデータフレーム
            # ==========================================
            formatted_matrix = {}
            for loc_id, forecasts in weather_raw_matrix.items():
                loc_formatted = {}
                for date_str, data in forecasts.items():
                    cell_text = f"雲:{data['cloud']}%/雨:{data['vc_rain']}%"
                    if data['jma']:
                        cell_text += f" | {data['jma']}"
                    loc_formatted[date_str] = cell_text
                formatted_matrix[loc_id] = loc_formatted
                
            df_base = pd.DataFrame(formatted_matrix).T
            styled_df = df_base.style.map(style_weather_pc)
            st.dataframe(styled_df, use_container_width=True)
            
        st.caption("※雲量30%以下は水色、降水確率 50%以上は赤で表示しています。")
else:
    st.info("上のドロップダウンから地域を選び、「➕ 一覧に追加」するか、保存されたプロジェクトを呼び出してください。")

st.caption("ver1.6.0 Hybrid Native-HTML Engine")
