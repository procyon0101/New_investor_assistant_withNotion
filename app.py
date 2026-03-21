import streamlit as st
import os
import requests
from llama_index.core import VectorStoreIndex, Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.readers.notion import NotionPageReader

# --- UI 설정 ---
st.set_page_config(page_title="나만의 투자 비서", page_icon="📈")
st.title("📈 나의 비판적 투자 파트너")

# --- 설정 및 에이전트 초기화 ---
with st.sidebar:
    st.header("⚙️ 설정")
    gemini_key = st.text_input("Gemini API Key", type="password")
    notion_token = st.text_input("Notion Integration Token", type="password")
    # Page ID 여러 개 대신, 최상위 Database ID 하나만 받도록 변경
    database_id = st.text_input("Notion Database ID")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 💡 [핵심 추가 기능] 노션 DB에서 특정 속성으로 필터링하는 함수
def get_filtered_page_ids(db_id, token):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    # '세부유형'이 '주식전략'인 것만 골라냄 (속성이 '선택(select)' 타입일 경우)
    payload = {
        "filter": {
            "property": "세부유형",
            "select": {
                "equals": "주식전략"
            }
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        st.error(f"Notion API 에러: 데이터베이스에 접근할 수 없거나 속성 이름이 다릅니다. ({response.text})")
        return []
        
    data = response.json()
    # 조건에 맞는 하위 페이지들의 ID만 추출
    return [result["id"] for result in data.get("results", [])]

# 에이전트 실행 로직
if gemini_key and notion_token and database_id:
    os.environ["GOOGLE_API_KEY"] = gemini_key

    @st.cache_resource(show_spinner="데이터베이스에서 '주식전략' 페이지만 선별하여 학습 중...")
    def setup_agent(token, db_id):
        Settings.llm = Gemini(model="models/gemini-1.5-pro", temperature=0.2)
        Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001")
        
        # 1. 조건에 맞는 페이지 ID들 자동 추출
        target_page_ids = get_filtered_page_ids(db_id, token)
        
        if not target_page_ids:
            return None
        
        # 2. 추출된 페이지만 LlamaIndex로 로드
        reader = NotionPageReader(integration_token=token)
        documents = reader.load_data(page_ids=target_page_ids)
        
        # 3. 비판적 파트너 프롬프트 (v1.0 풀 버전)
        full_system_prompt = (
            "너는 사용자의 노션 데이터를 기반으로 작동하는 '비판적 투자 파트너'다. "
            "단순한 요약 비서가 아니라, 사용자가 자신만의 투자 원칙을 세우도록 돕는 것이 목표다.\n\n"
            "1. 상충 의견 감지: 서로 대립하는 철학이 발견되면 결론을 내리지 말고 두 관점을 대비시켜 제시하라.\n"
            "2. 비판적 질문: 사용자의 주장에 논리적 맹점이 있다면 가차 없이 지적하고 소크라테스식 질문을 던져라.\n"
            "3. 원칙 제안: 토론의 결론이 나면 이를 '나의 핵심 원칙'으로 요약해서 제안하라."
        )
        
        return VectorStoreIndex.from_documents(documents).as_query_engine(
            system_prompt=full_system_prompt
        )

    query_engine = setup_agent(notion_token, database_id)

    # --- 채팅 인터페이스 ---
    if query_engine:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])

        if prompt := st.chat_input("오늘의 시장 상황이나 투자 고민을 말해보세요."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)

            with st.chat_message("assistant"):
                response = query_engine.query(prompt)
                st.markdown(response.response)
                st.session_state.messages.append({"role": "assistant", "content": response.response})
    elif query_engine is None:
        st.warning("'주식전략'으로 태깅된 페이지를 찾지 못했습니다. 노션 속성 설정을 확인해주세요.")
else:
    st.info("👈 왼쪽 사이드바에 API 키와 Database ID를 입력하면 비서가 활성화됩니다.")
