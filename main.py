import streamlit as st
from supabase import create_client, Client

# Initialize connection.
# Uses st.cache_resource to only run once.
@st.cache_resource
def init_connection():
    url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
    key = st.secrets["connections"]["supabase"]["SUPABASE_KEY"]
    return create_client(url, key)


supabase = init_connection()




st.title("Welcome to Happenly!")
Signup, Login = st.tabs(["Sign Up", "Log In"])

#sign up ui
with Signup:
    st.header("Sign Up")
    with st.form("signup"):
        s_email = st.text_input('Email')
        s_password = st.text_input('Password', type = "password")
        signed_up = st.form_submit_button('Sign Up')
#login ui
with Login:
    st.header("Login")
    with st.form("login"):
        l_email = st.text_input('Email')
        l_password = st.text_input('Password', type = "password")
        logged_in = st.form_submit_button('Login')


#registration logic
if signed_up:
    try:
        accnt = supabase.auth.sign_up({"email": s_email, "password": s_password})
        st.success("Account created! Please Verify With Your Email and Log In.")
    except Exception as e:
        st.error(f"Sign Up Failed: {e}")

#login logic
if logged_in:
    try:
        result = supabase.auth.sign_in_with_password({
            "email": l_email,
            "password": l_password
        })

        if result and result.user:

           
            st.session_state["user"] = result.user
            st.session_state["session"] = result.session

            st.switch_page("pages/events.py")

    except Exception as e:
        st.error(f"Login Failed: {e}")
