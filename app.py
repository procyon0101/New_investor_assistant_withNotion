import streamlit as st
import os
import requests
import google.generativeai as genai  # 라마인덱스 대신 가벼운 공식 SDK 사용

# --- UI 및 설정 ---
st.set_page_config(page_title="나만의 투자 비서", page_icon="📈")
st.title("📈 나의 비판적 투자 파트너 (Light)")

with st.sidebar:
    st.header("⚙️ 설정")
    gemini_key = st.text_input("Gemini API Key", type="password")
    notion_token = st.text_input("Notion Token", type="password")
    database_id = st.text_input("Notion DB ID")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 노션 데이터 가져오기 함수 ---
def get_notion_data(db_id, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    # 필터링: 세부유형 = 주식전략
    query_url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload = {"filter": {"property": "세부유형", "select": {"equals": "주식전략"}}}
    res = requests.post(query_url, headers=headers, json=payload)
    
    if res.status_code != 200:
        return f"노션 연결 실패: {res.text}"

    pages = res.json().get("results", [])
    all_text = ""
    for page in pages:
        page_id = page["id"]
        # 페이지 본문 읽기
        block_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        block_res = requests.get(block_url, headers=headers)
        blocks = block_res.json().get("results", [])
        for block in blocks:
            if block["type"] == "paragraph":
                rich_texts = block["paragraph"]["rich_text"]
                all_text += "".join([t["plain_text"] for t in rich_texts]) + "\n"
    return all_text

# --- 메인 로직 ---
if gemini_key and notion_token and database_id:
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel('models/gemini-1.5-pro')

    # 채팅 기록 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("메시지를 입력하세요."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("노션 데이터를 분석하며 비판적 검토 중..."):
                context_data = get_notion_data(database_id, notion_token)
    
    # 💡 데이터가 없을 경우에 대한 방어 로직 추가
                if not context_data or "실패" in context_data:
                    st.warning("⚠️ 노션에서 '주식전략'으로 태깅된 데이터를 가져오지 못했습니다. 일반적인 지식으로 대답합니다.")
                    context_data = "등록된 투자 원칙 데이터가 없습니다."

                system_instruction = (
                    f"너는 비판적 투자 파트너다. 아래의 데이터를 바탕으로 대답하라.\n"
                    f"데이터: {context_data}\n\n"
                    "지침: 상충되는 원칙이 있으면 쟁점화하고, 내 논리의 맹점을 지적하라."
                )
    
    # ... 나머지 코드 동일     
                response = model.generate_content([system_instruction, prompt])
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
else:
    st.info("👈 사이드바 정보를 입력해 주세요.")




