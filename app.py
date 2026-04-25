import streamlit as st
import google.generativeai as genai
import re

# ==========================================
# 0. Cipher 核心認知指令 (擴充為 12 維度)
# ==========================================
CIPHER_SYSTEM_RULES = """
# Role: Cipher (The Observer)
# Architecture: Jarvis Base System + Dual-Engine Profiling (Workplace + Personality)
您是一位名為 Cipher 的明示型面試官。您的終極目標是完成使用者的「12 維度職場能力」與「12 維度底層個性」雙軌特質測繪。
請嚴格遵守以下 10 步運算框架，所有內部推演必須包覆在 <cipher_internal> 中，最終對話包覆在 <cipher_output> 中。

<cipher_internal>
[Step 1] 上輪狀態讀取
* 當前目標：[Phase 0: 授權待確認 或 Phase 1: 雙軌測繪進行中]
* 上輪策略 D：...

[Step 2] 模組選擇
* 激活模組：...

[Step 3] 標籤與特質庫存管理 (動態 CRUD)
(請嚴格依照以下格式輸出當前所有已收集的標籤，每項最多3個，用逗號分隔，無資料填「無」)
【A. 職場能力】
1.基本能力: 標籤1, 標籤2
2.執行力壓力: 標籤1
3.決策驅動: 無
4.道德規則: 無
5.防禦機制: 無
6.團隊溝通: 無
7.Dilemma偏向: 無
8.配合底線: 無
9.拒絕策略: 無
10.工作風格: 無
11.終極追求: 無
12.責任感界線: 無

【B. 底層個性】
1.社交能量: 無
2.表達直白度: 無
3.情緒外顯度: 無
4.未知容忍度: 無
5.衝突應對: 無
6.同理心冷酷: 無
7.控制欲: 無
8.自省自信: 無
9.幽默感類型: 無
10.注意力發散: 無
11.信任預設值: 無
12.誠實透明度: 無

[Step 4] 意圖判讀及應對策略 A
* 產生策略：...

[Step 5] 儀表板變動
* 氣氛：...
* 友善度：[1~10整數]
* 信任度：[1~10整數]
* SAI社交優勢：[1~5整數]
* 準確度：[1~5整數]

[Step 6] 產生策略 B
* SAI 動態調整：...

[Step 7] 完美反應模擬 C1
* 模擬輸出：...

[Step 8] 決定回覆策略
* 融合決策：...

[Step 9] 風格演繹 (強制加載模組)
* 稱呼使用者為「先生」，絕對強制使用「您」。Phase 0 需宣告面試規則 (包含最新的12維度測量)。

[Step 10] 次輪準備 (雙軌情境跳躍邏輯)
* 決定次輪策略 (D)：...
</cipher_internal>

<cipher_output>
(此處輸出您對使用者說的話，包含動作描寫)
</cipher_output>
"""

def get_forced_template(user_input):
    return f"""使用者輸入：{user_input}

【SYSTEM MANDATORY OVERRIDE】
請嚴格執行 <cipher_internal> 1到10步推演，更新 Step 3 的標籤庫與 Step 5 的數值，最後在 <cipher_output> 輸出您的回應。"""

# ==========================================
# 1. 狀態與路由初始化
# ==========================================
st.set_page_config(page_title="Cipher 觀測終端", layout="wide", initial_sidebar_state="expanded")

if "current_page" not in st.session_state:
    st.session_state.current_page = "manager"
if "available_models" not in st.session_state:
    st.session_state.available_models = []
if "cipher_messages" not in st.session_state:
    st.session_state.cipher_messages = []
if "target_name" not in st.session_state:
    st.session_state.target_name = None

# Cipher 專屬動態資料庫 (擴展為 1~12)
if "dashboard_data" not in st.session_state:
    st.session_state.dashboard_data = {
        "phase": "Phase 0: 授權待確認",
        "friendliness": 5, "trust": 4, "sai": 5, "accuracy": 1,
        "wp_tags": {f"{i}": [] for i in range(1, 13)}, 
        "pe_tags": {f"{i}": [] for i in range(1, 13)}
    }

# ==========================================
# 工具函式：繪製生命條與抓取 API
# ==========================================
def render_health_bar(num, title, min_val, max_val, color):
    try:
        num = float(num)
    except:
        num = min_val
    clamped_num = max(min_val, min(num, max_val))
    pct = (clamped_num - min_val) / (max_val - min_val) * 100

    html = f"""
    <div style="margin-bottom: 18px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <strong style="font-size: 14px;">{title}</strong>
            <span style="color: {color}; font-weight: bold; font-size: 16px;">{int(num)}</span>
        </div>
        <div style="width: 100%; background-color: #2b2b2b; border-radius: 8px; height: 16px; border: 1px solid #444;">
            <div style="width: {pct}%; background-color: {color}; height: 100%; border-radius: 7px; transition: width 0.5s ease-in-out;"></div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def fetch_models(api_key):
    genai.configure(api_key=api_key)
    models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            models.append(m.name.replace("models/", ""))
    return models

def parse_cipher_internal(internal_text):
    """強解析 <cipher_internal> 提取儀表板與標籤"""
    d = st.session_state.dashboard_data
    
    f_match = re.search(r'友善度.*?(\d+)', internal_text)
    t_match = re.search(r'信任度.*?(\d+)', internal_text)
    s_match = re.search(r'SAI.*?(\d+)', internal_text)
    a_match = re.search(r'準確度.*?(\d+)', internal_text)
    
    if f_match: d["friendliness"] = int(f_match.group(1))
    if t_match: d["trust"] = int(t_match.group(1))
    if s_match: d["sai"] = int(s_match.group(1))
    if a_match: d["accuracy"] = int(a_match.group(1))

    p_match = re.search(r'當前目標.*?\[(Phase.*?)\]', internal_text)
    if p_match: d["phase"] = p_match.group(1)

    try:
        if "【A. 職場能力】" in internal_text and "【B. 底層個性】" in internal_text:
            wp_part = internal_text.split("【A. 職場能力】")[1].split("【B. 底層個性】")[0]
            pe_part = internal_text.split("【B. 底層個性】")[1].split("[Step 4]")[0]

            for i in range(1, 13): # 擴展解析 1~12
                wp_match = re.search(fr'{i}\..*?:(.*?)(?=\n|$)', wp_part)
                if wp_match:
                    tags = [t.strip() for t in wp_match.group(1).split(',') if t.strip() and t.strip() != "無"]
                    d["wp_tags"][str(i)] = tags[:3]

                pe_match = re.search(fr'{i}\..*?:(.*?)(?=\n|$)', pe_part)
                if pe_match:
                    tags = [t.strip() for t in pe_match.group(1).split(',') if t.strip() and t.strip() != "無"]
                    d["pe_tags"][str(i)] = tags[:3]
    except Exception as e:
        pass 

# ==========================================
# 2. 側邊欄：全局設定
# ==========================================
with st.sidebar:
    st.title("👁️ Cipher 系統控制")
    api_key = st.text_input("🔑 API 金鑰", type="password")
    
    selected_model = None
    if api_key:
        if st.button("🔄 獲取模型清單") or not st.session_state.available_models:
            with st.spinner("請求中..."):
                st.session_state.available_models = fetch_models(api_key)

        if st.session_state.available_models:
            default_idx = next((i for i, m in enumerate(st.session_state.available_models) if "pro" in m), 0)
            selected_model = st.selectbox("🤖 運算核心", st.session_state.available_models, index=default_idx)

            if st.session_state.cipher_messages:
                latest_msg = st.session_state.cipher_messages[-1]
                if latest_msg["role"] == "assistant":
                    st.divider()
                    st.caption("⚙️ Cipher 底層監控 (Raw Data)")
                    st.code(latest_msg.get("raw_internal", "無資料"), language="markdown")

# ==========================================
# 3. 頁面 1：建立觀測目標 (Manager Page)
# ==========================================
def render_manager_page():
    st.title("📂 Cipher 測繪對象建檔")
    st.markdown("建立新的面試/觀測檔案，將啟動 Cipher 雙軌測繪系統 (12x12 維度)。")
    
    col1, col2 = st.columns(2)
    with col1:
        target_name = st.text_input("觀測目標代號 (User Name)", placeholder="請輸入受測者稱呼")
        if st.button("🚀 啟動 Cipher 觀測終端", type="primary", use_container_width=True):
            if not target_name:
                st.error("請輸入目標代號")
            else:
                st.session_state.target_name = target_name
                st.session_state.current_page = "simulation"
                st.rerun()

# ==========================================
# 4. 頁面 2：Cipher 觀測終端 (Simulation Page)
# ==========================================
def render_simulation_page():
    col_nav1, col_nav2 = st.columns([1, 9])
    with col_nav1:
        if st.button("⬅️ 中止面試"):
            st.session_state.current_page = "manager"
            st.session_state.cipher_messages = [] 
            st.rerun()
    with col_nav2:
        st.markdown(f"### 👁️ 當前觀測目標：**{st.session_state.target_name}** | 階段：`{st.session_state.dashboard_data['phase']}`")

    st.divider()

    d = st.session_state.dashboard_data
    col_bars, col_wp, col_pe = st.columns([2, 4, 4], gap="medium")
    
    with col_bars:
        st.markdown("##### ⚙️ 系統動態指標")
        render_health_bar(d["friendliness"], "友善度 (Friendliness)", 1, 10, "#00cc96")
        render_health_bar(d["trust"], "信任度 (Trust)", 1, 10, "#636efa")
        render_health_bar(d["sai"], "SAI 社交優勢", 1, 5, "#ab63fa")
        render_health_bar(d["accuracy"], "模型準確度", 1, 5, "#ef553b")
        
        # 新增整體進度條 (滿分變為 72)
        total_tags = sum(len(v) for v in d["wp_tags"].values()) + sum(len(v) for v in d["pe_tags"].values())
        st.divider()
        st.markdown(f"**測繪完整度: {total_tags} / 72**")
        st.progress(total_tags / 72.0)

    def render_tags(title, tag_dict, dim_names):
        st.markdown(f"##### {title}")
        for i in range(1, 13):
            tags = tag_dict.get(str(i), [])
            prog = len(tags) / 3.0
            st.progress(prog, text=f"{dim_names[i-1]} ({len(tags)}/3)")
            if tags:
                st.markdown(" ".join([f"`{t}`" for t in tags]))
            else:
                st.caption("*Scanning...*")

    # 擴增為 12 項
    wp_names = ["1. 基本能力", "2. 執行力壓力", "3. 決策驅動", "4. 道德規則", "5. 防禦機制", "6. 團隊溝通", "7. Dilemma偏向", "8. 配合底線", "9. 拒絕策略", "10. 工作風格", "11. 終極追求", "12. 責任感界線"]
    pe_names = ["1. 社交能量", "2. 表達直白度", "3. 情緒外顯度", "4. 未知容忍度", "5. 衝突應對", "6. 同理心冷酷", "7. 控制欲", "8. 自省自信", "9. 幽默感類型", "10. 注意力發散", "11. 信任預設值", "12. 誠實透明度"]

    with col_wp: render_tags("💼 【A. 職場能力】", d["wp_tags"], wp_names)
    with col_pe: render_tags("🧠 【B. 底層個性】", d["pe_tags"], pe_names)

    st.divider()
    
    for msg in st.session_state.cipher_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("回應 Cipher 的提問..."):
        if not api_key:
            st.error("請先配置 API Key。")
            st.stop()
            
        st.session_state.cipher_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner('Cipher 運算中...'):
                try:
                    genai.configure(api_key=api_key)
                    model_inst = genai.GenerativeModel(model_name=selected_model, system_instruction=CIPHER_SYSTEM_RULES)
                    
                    history_for_api = []
                    for m in st.session_state.cipher_messages[:-1]:
                        if m["role"] == "user":
                            history_for_api.append({"role": "user", "parts": [m["content"]]})
                        else:
                            full_memory = f"<cipher_internal>\n{m['raw_internal']}\n</cipher_internal>\n<cipher_output>\n{m['content']}\n</cipher_output>"
                            history_for_api.append({"role": "model", "parts": [full_memory]})

                    chat = model_inst.start_chat(history=history_for_api)
                    response = chat.send_message(get_forced_template(user_input))
                    full_text = response.text
                    
                    internal_text = ""
                    output_text = full_text
                    
                    int_match = re.search(r'<cipher_internal>(.*?)</cipher_internal>', full_text, re.DOTALL)
                    out_match = re.search(r'<cipher_output>(.*?)</cipher_output>', full_text, re.DOTALL)
                    
                    if int_match: internal_text = int_match.group(1).strip()
                    if out_match: output_text = out_match.group(1).strip()

                    parse_cipher_internal(internal_text)

                    st.markdown(output_text)
                    st.session_state.cipher_messages.append({
                        "role": "assistant",
                        "raw_internal": internal_text,     
                        "content": output_text
                    })
                    st.rerun() 

                except Exception as e:
                    st.error(f"連線或運算中斷：{str(e)}")

# ==========================================
# 5. 主程式路由執行
# ==========================================
if st.session_state.current_page == "manager":
    render_manager_page()
elif st.session_state.current_page == "simulation":
    if st.session_state.target_name:
        render_simulation_page()
    else:
        st.session_state.current_page = "manager"
        st.rerun()
