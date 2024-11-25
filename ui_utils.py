import re
import streamlit as st
import plotly.express as px
from auth_functions import sign_in, create_account, sign_out, reset_password


def render_auth_form():
    auth_form = st.form("auth_form")
    email = auth_form.text_input("Email")
    password = auth_form.text_input("Password", type="password")
    sign_in_button = auth_form.form_submit_button("Sign In", use_container_width=True)
    sign_up_button = auth_form.form_submit_button("Sign Up", use_container_width=True)
    password_reset_button = auth_form.form_submit_button("Forgot Password?", use_container_width=True)

    if sign_in_button:
        sign_in(email, password)

    if sign_up_button:
        create_account(email, password)

    if password_reset_button:
        reset_password(email)

    if "auth_success" in st.session_state:
        auth_form.success(st.session_state.auth_success)
    if "auth_warning" in st.session_state:
        auth_form.warning(st.session_state.auth_warning)


def render_account_panel():
    with st.sidebar.container(border=True, height=150):
        if "user_info" in st.session_state:
            st.markdown(
                f"User: `{st.session_state.user_info['users'][0]['email']}`\n\nAccount: `{st.session_state.tenant_name}`"
            )
        if st.button("Sign Out", use_container_width=True):
            sign_out()
            st.rerun()


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


def add_background_and_corner_radius(code: str) -> str:
    # Line to add the background color and corner radius
    customization_line = "fig.update_layout(paper_bgcolor='#244466', " "plot_bgcolor='#244466')\n"

    # Find the location to insert the customization line
    split_lines = code.split("\n")
    for i, line in enumerate(split_lines):
        if "st.plotly_chart(fig" in line:
            split_lines.insert(i, customization_line)
            break

    # Reassemble the modified code
    return "\n".join(split_lines)


def chart_block(df, waii_chart_spec=None):
    if waii_chart_spec:
        try:
            PLOT_BGCOLOR = "#244466"

            st.markdown(
                f"""
                <style>
                .stPlotlyChart {{
                outline: 10px solid {PLOT_BGCOLOR};
                border-radius: 5px;
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )
            modified_chart_spec = add_background_and_corner_radius(waii_chart_spec)
            exec(modified_chart_spec, {"df": df})
        except Exception as e:
            st.write(e)


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
        if "sql" in message and message["sql"] and ("sql", message["sql"]) not in blocks:
            st.expander("SQL Query", expanded=False).code(message["sql"], language="sql")
        if "data" in message and message["data"] is not None:
            st.expander("Data", expanded=False).dataframe(df, use_container_width=True)
        if "chart" in message and message["chart"]:
            st.expander("Waii Chart Specification", expanded=False).code(message["chart"], language="python")


def render_sidebar_tips():
    st.sidebar.info(
        """## Hi, I'm OTTO!
        
I'm your trusty, cybersecurity assistant, here to help you navigate your infrastructure, answer your questions, and provide actionable insights to keep your organization secure.

## Things you can ask me:
- Which vulnerabilities should I be most concerned about?
- How can I improve my security posture?
- What is my risk as a CISO?\n
        """
    )


def render_placeholder_image():
    with open("bot.svg", "rb") as f:
        bot_svg = f.read()

    # Edit bot_svg to add style
    bot_svg = bot_svg.replace(b"<svg", b'<svg style="width: 70%; height: auto; object-fit: contain;"')
    st.write(
        f"""
                <div style="width: 100%; aspect-ratio: 1 / 1; display: flex; justify-content: center; align-items: center; position: relative; overflow: hidden; opacity: 40%;">
                    {bot_svg.decode()}
                </div>
                """,
        unsafe_allow_html=True,
    )
