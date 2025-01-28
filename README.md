# 🎥 Youtube Video AI AGENT

A powerful video analysis tool that uses Google's Gemini 2.0 Flash model to provide detailed insights and analysis of YouTube videos.

## ✨ Features

- 🎬 **YouTube Video Support**
  - Direct video download from YouTube URLs
  - Supports videos up to 50 minutes long
  - Handles videos up to 2GB in size
  - Multiple video format support (MP4, MOV, WebM, 3GPP)

- 🤖 **AI-Powered Analysis**
  - Powered by Gemini 2.0 Flash experimental model
  - Comprehensive video content analysis
  - Natural language interaction
  - Detailed scene-by-scene breakdown
  - Audio and visual element analysis

- 💡 **Smart Features**
  - Real-time download progress tracking
  - Automatic video quality optimization
  - Intelligent error handling
  - Rate limit handling with auto-retry
  - Suggested questions for analysis

- 🎨 **Modern UI**
  - Clean and intuitive interface
  - Video player integration
  - Chat-like interaction
  - Progress indicators
  - Responsive design

## 🚀 Getting Started

### Prerequisites

```bash
- Python 3.8 or higher
- pip (Python package manager)
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Video-Summarizer-AI-Agent.git
cd Video-Summarizer-AI-Agent
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the project root with:
```env
GOOGLE_API_KEY=your_gemini_api_key
YOUTUBE_API_KEY=your_youtube_api_key
```

### Running the App

```bash
python -m streamlit run app.py
```

The app will be available at `http://localhost:8502`

## 🎯 Usage

1. **Enter YouTube URL**
   - Paste any YouTube video URL in the input field
   - Supported formats: 
     - https://youtube.com/watch?v=...
     - https://youtu.be/...

2. **Wait for Download**
   - Progress bar shows download status
   - Video will be processed automatically

3. **Ask Questions**
   - Use suggested questions or ask your own
   - AI will analyze the video content
   - Get detailed responses about the video

## 📝 Example Questions

- What is this video about? Give me a detailed summary.
- What are the main topics or points discussed?
- How many people are in the video and what are they doing?
- What is the setting/location of the video?
- What are the key visual elements or scenes?

## ⚠️ Limitations

- Maximum video length: 50 minutes (with audio)
- Maximum file size: 2GB
- Supported formats: MP4, MOV, WebM, 3GPP
- Internet connection required
- Rate limits may apply

## 🔧 Troubleshooting

If you encounter issues:

1. Check video length (should be under 50 minutes)
2. Verify file size (under 2GB)
3. Ensure stable internet connection
4. Try a different video format
5. Wait a few minutes and retry

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google Gemini 2.0 Flash for AI capabilities
- Streamlit for the web interface
- yt-dlp for video downloading
- OpenCV for video processing
