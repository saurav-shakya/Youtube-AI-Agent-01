import os
from dotenv import load_dotenv
import streamlit as st
from langchain.llms import OpenAI
from langchain.document_loaders import YoutubeLoader
from langchain.chains.summarize import load_summarize_chain

# Load environment variables
load_dotenv()

# Set up OpenAI API key
openai_api_key = os.getenv("OPENAI_API_KEY")

def get_youtube_summary(youtube_url):
    # Load YouTube video
    loader = YoutubeLoader.from_youtube_url(youtube_url)
    transcript = loader.load()
    
    # Initialize OpenAI
    llm = OpenAI(temperature=0, openai_api_key=openai_api_key)
    
    # Create and run the summarization chain
    chain = load_summarize_chain(llm, chain_type="stuff")
    summary = chain.run(transcript)
    
    return summary

# Streamlit UI
st.title("YouTube Video Summarizer")
st.write("Enter a YouTube URL to get an AI-generated summary!")

youtube_url = st.text_input("YouTube URL:")

if st.button("Get Summary"):
    if youtube_url:
        try:
            summary = get_youtube_summary(youtube_url)
            st.write("Summary:")
            st.write(summary)
        except Exception as e:
            st.error(f"Error: {str(e)}")
    else:
        st.warning("Please enter a YouTube URL") 