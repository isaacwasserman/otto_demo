import dotenv
import pandas as pd
import streamlit as st
from waii_sdk_py import WAII
from waii_sdk_py.chat import ChatRequest
from auth_functions import user_logged_in
from ui_utils import render_message, render_sidebar_tips, render_placeholder_image, render_auth_form, render_account_panel

# Define constants
WAII_API_KEY = st.secrets["WAII_API_KEY"]
WAII_API_URL = st.secrets["WAII_API_URL"]
SNOWFLAKE_WAREHOUSE = st.secrets["SNOWFLAKE_WAREHOUSE"]
SNOWFLAKE_DATABASE = st.secrets["SNOWFLAKE_DATABASE"]
SNOWFLAKE_ACCOUNT = st.secrets["SNOWFLAKE_ACCOUNT"]
SNOWFLAKE_USER = st.secrets["SNOWFLAKE_USER"]

# Configure page
st.set_page_config(page_title="Chat with Otto", page_icon="🎱")
st.logo("virsec_logo.svg")
st.title("Meet OTTO")

# Initialize user state
if "user_info" not in st.session_state:
    st.session_state.user_info = {}


def update_user_info():
    st.session_state.user_domain = st.session_state.user_info["users"][0]["email"].split("@")[1].lower()
    st.session_state.tenant_name = st.secrets["TENANTS_BY_DOMAIN"][st.session_state.user_domain]["NAME"]
    st.session_state.tenant_id = st.secrets["TENANTS_BY_DOMAIN"][st.session_state.user_domain]["TENANT_ID"]


def initialize_waii():
    waii_db_connection = f"snowflake://{SNOWFLAKE_USER}@{SNOWFLAKE_ACCOUNT}/{SNOWFLAKE_DATABASE}?role=waii_{st.session_state.tenant_id}_role&warehouse={SNOWFLAKE_WAREHOUSE}"
    WAII.initialize(url=WAII_API_URL, api_key=WAII_API_KEY)
    WAII.Database.activate_connection(waii_db_connection)


def initialize_message_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "prev_response_uuid" not in st.session_state:
        st.session_state.prev_response_uuid = None

    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None


def ask(question):
    user_message = {"name": "user", "text": question}
    render_message(user_message, persist=True)
    response = WAII.Chat.chat_message(ChatRequest(ask=question, parent_uuid=st.session_state.prev_response_uuid))
    st.session_state.prev_response_uuid = response.chat_uuid
    ai_message = {
        "name": "Otto",
        "text": response.response,
        "sql": response.response_data.query.query if response.response_data.query else None,
        "data": pd.DataFrame(response.response_data.data.rows) if response.response_data.data else None,
        "chart": response.response_data.chart.chart_spec.plot if response.response_data.chart else None,
    }
    render_message(ai_message, persist=True)


if not user_logged_in():
    render_auth_form()
else:
    update_user_info()
    render_sidebar_tips()
    render_account_panel()
    initialize_waii()
    initialize_message_state()

    # If no messages exist, render placeholder image
    if not st.session_state.messages and not st.session_state.pending_prompt:
        render_placeholder_image()

    # Render pre-existing messages
    for message in st.session_state.messages:
        render_message(message, persist=False)

    # If a question is asked, save it to session state and rerun to flush the placeholder image
    if prompt := st.chat_input("Ask me anything..."):
        st.session_state.pending_prompt = prompt
        st.rerun()

    # If a pending prompt exists, ask it and clear the pending prompt
    if st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None
        ask(prompt)
