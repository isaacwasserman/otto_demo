"""Streamlit app for TrustSight AI."""

import os
import re
import dotenv
import pandas as pd
import streamlit as st
import plotly.express as px
from plotly import graph_objects as go
from waii_sdk_py import WAII
from waii_sdk_py.query import *
from waii_sdk_py.chat import *
import uuid

dotenv.load_dotenv()


NUM_SUGGESTIONS = 4
DEBUG = True
USE_WAII_CHART = True
USE_AUTOCHART = True

WAII_API_KEY = st.secrets["WAII_API_KEY"]
WAII_API_URL = st.secrets["WAII_API_URL"]
WAII_DB_CONNECTION = st.secrets["WAII_DB_CONNECTION"]
WAII.initialize(url=WAII_API_URL, api_key=WAII_API_KEY)
WAII.Database.activate_connection(WAII_DB_CONNECTION)

st.set_page_config(
    page_title="Chat with Otto",
    page_icon="🎱",
    # layout="wide",
)

st.logo("virsec_logo.svg")
st.title("TrustSight Otto")

if "state" not in st.session_state:
    st.session_state.state = None

if "messages" not in st.session_state:
    st.session_state.messages = [
        # {
        #     "name": "Otto",
        #     "text": "Here are some examples of questions I can answer:",
        #     "suggestions": [
        #         "Which of my workloads has the most critical vulnerabilities?",
        #         "Which scripts trigger the most incidents?",
        #         "Which CISA KEVs exist on my systems?",
        #         "Which operating systems am I running?",
        #     ],
        # }
    ]

if "initial_question" not in st.session_state:
    st.session_state.initial_question = st.query_params["question"] if "question" in st.query_params else None

if "prev_response_uuid" not in st.session_state:
    st.session_state.prev_response_uuid = None


def persist_state(state) -> None:
    st.session_state.state = state


def split_and_insert(text, replacements):
    # Split the text at the tokens <chart>, <data>, etc.
    tokens = re.split(r"(<chart>|<data>)", text)

    # Result list to accumulate the final output
    result = []

    # Loop through each token and add replacements as needed
    for token in tokens:
        if token in replacements:
            result.append(replacements[token])  # Insert the replacement object
        else:
            result.append(token)  # Add the regular text

    return result


def autoplot(df_, chart_type="bar"):
    df = df_.copy().infer_objects()
    if len(df.columns) == 0:
        return None
    elif len(df.columns) == 1:
        df["x"] = df.columns[0]
        df = df[["x", df.columns[0]]]
    num_rows = df.shape[0]
    if num_rows < 2:
        return None
    x_col = df.columns[0]
    # Make y column first numeric column
    y_col = None
    for col in df.columns[1:]:
        if df[col].dtype in ["int64", "float64"]:
            y_col = col
            break
    if y_col is None:
        return None
    if chart_type == "bar":
        fig = px.bar(df, x=x_col, y=y_col)
    elif chart_type == "line":
        fig = px.line(df, x=x_col, y=y_col)
    elif chart_type == "pie":
        fig = px.pie(df, values=y_col, names=x_col)
    elif chart_type == "sunburst":
        path = [x_col]
        for i in range(1, len(df.columns)):
            # Ensure column is not numeric
            if df[df.columns[i]].dtype == "object":
                path.append(df.columns[i])
        fig = px.sunburst(df, path=path, values=y_col)
    else:
        raise ValueError("Invalid chart type")
    return fig


def chart_block(df, waii_chart_spec=None):
    plots = {chart_type: autoplot(df, chart_type) for chart_type in ["bar", "pie", "line"]}

    if any(plots.values()):
        if USE_WAII_CHART:
            waii_chart_tab, bar_chart_tab, pie_chart_tab, line_chart_tab = st.tabs(
                ["Waii Chart", "Bar Chart", "Pie Chart", "Line Chart"]
            )
            with waii_chart_tab:
                if waii_chart_spec:
                    exec(waii_chart_spec, {"df": df})
        else:
            bar_chart_tab, pie_chart_tab, line_chart_tab = st.tabs(["Bar Chart", "Pie Chart", "Line Chart"])

        with bar_chart_tab:
            if plots["bar"]:
                st.plotly_chart(plots["bar"], use_container_width=True, key=f"bar_chart_{uuid.uuid4()}")
        with pie_chart_tab:
            if plots["pie"]:
                st.plotly_chart(plots["pie"], use_container_width=True, key=f"pie_chart_{uuid.uuid4()}")
        with line_chart_tab:
            if plots["line"]:
                st.plotly_chart(plots["line"], use_container_width=True, key=f"line_chart_{uuid.uuid4()}")


def ask(question):
    user_message = {"name": "user", "text": question}
    render_message(user_message, persist=True)
    # st.session_state.messages.append(user_message)
    response = WAII.Chat.chat_message(ChatRequest(ask=question, parent_uuid=st.session_state.prev_response_uuid))
    st.session_state.prev_response_uuid = response.chat_uuid
    ai_message = {
        "name": "Otto",
        "text": response.response,
        "sql": response.response_data.query.query if response.response_data.query else None,
        "data": pd.DataFrame(response.response_data.data.rows) if response.response_data.data else None,
        "chart": response.response_data.chart.chart_spec.plot if response.response_data.chart else None,
    }
    # Remove the suggestions from the previous message
    # st.session_state.messages = [msg for msg in st.session_state.messages if "suggestions" not in msg]
    # st.session_state.messages.append(ai_message)
    render_message(ai_message, persist=True)


def render_message(message, persist=False):
    if persist:
        st.session_state.messages.append(message)
    with st.chat_message(message["name"], avatar="otto_avatar.png" if message["name"] == "Otto" else None):
        replacements = {}
        df = None
        includes_chart = False
        if "sql" in message and message["sql"]:
            replacements["<sql>"] = ("sql", message["sql"])
        if "data" in message and message["data"] is not None:
            df = message["data"]
            replacements["<data>"] = ("data", df)
        if "chart" in message and message["chart"]:
            replacements["<chart>"] = ("chart", message["chart"])
        blocks = split_and_insert(message["text"], replacements)
        for block in blocks:
            if isinstance(block, str):
                st.markdown(block)
            else:
                if block[0] == "sql":
                    st.code(block[1], language="sql")
                elif block[0] == "data":
                    st.dataframe(block[1], use_container_width=True)
                elif block[0] == "chart":
                    includes_chart = True
                    chart_block(df, waii_chart_spec=(message["chart"] if "chart" in message else None))
        if not includes_chart and df is not None:
            chart_block(df, waii_chart_spec=(message["chart"] if "chart" in message else None))
        if DEBUG:
            if "sql" in message and message["sql"] and ("sql", message["sql"]) not in blocks:
                st.expander("SQL Query", expanded=False).code(message["sql"], language="sql")
            if "data" in message and message["data"] is not None:
                st.expander("Data", expanded=False).dataframe(df, use_container_width=True)
            if USE_WAII_CHART:
                if "chart" in message and message["chart"]:
                    st.expander("Waii Chart Specification", expanded=False).code(message["chart"], language="python")
        if "suggestions" in message:
            for suggestion in message["suggestions"]:
                st.button(suggestion, use_container_width=True, on_click=ask, args=(suggestion,), key=suggestion)


# Display chat messages from history on app rerun
for message in st.session_state.messages:
    render_message(message, persist=False)

if prompt := st.chat_input("Ask me anything"):
    ask(prompt)
