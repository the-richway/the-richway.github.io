import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests
import re

# --- [환경변수 및 설정] ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "미국 증시 시황")
SEOUL_TZ = pytz.timezone('Asia/Seoul')

# [디스클레이머: 작은 글씨로 하단에 부착될 문구]
DISCLAIMER_TEXT = """
<br><br>
<hr>
<p style="text-align: center; font-size: 0.9em; color: #888; line-height: 1.6;">
    <strong>[안내 및 면책 조항]</strong><br>
    본 콘텐츠는 인공지능(AI) 모델을 활용하여 생성되었습니다.<br>
    투자의 책임은 전적으로 투자자 본인에게 있으며, 제공된 데이터는 일부 지연되거나 오류가 있을 수 있습니다.<br>
    내용에 오류가 발견되거나 저작권 문제가 발생할 경우, 관리자에게 문의 주시면 즉시 수정 또는 삭제 조치하겠습니다.
</p>
<hr>
"""

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """데이터 수집 로직"""
    tickers = {"^DJI": "다우존스", "^GSPC": "S&P500", "^IXIC": "나스닥", "^VIX": "공포지수"}
    data_str = "Recent Market Data (7 Days):\n"
    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="7d")
            if not hist.empty and len(hist) >= 2:
                close = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                change = ((close - prev) / prev) * 100
                data_str += f"- {name}: {close:.2f} ({change:+.2f}%)\n"
        except: continue
    return data_str

def get_gemini_model():
    """최신 모델 우선 선택 로직"""
    models = ['gemini-flash-latest', 'gemini-3-pro-preview', 'gemini-3-flash-preview', 'gemini-2.5-pro', 'gemini-2.5-flash-lite']
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            model.generate_content("test", generation_config={"max_output_tokens": 1})
            return model
        except: continue
    return None

def get_real_news_links():
    """
    [핵심 기능] yfinance를 통해 '실제 작동하는' 최신 뉴스 링크를 가져옵니다.
    AI가 URL을 환각(Hallucination)하는 것을 방지합니다.
    """
    news_summary = "Real News Links (Use these for Global references):\n"
    try:
        # S&P500 관련 주요 뉴스를 가져옵니다.
        ticker = yf.Ticker("^GSPC")
        news_list = ticker.news

        count = 0
        for item in news_list:
            if count >= 3: break
            title = item.get('title', 'No Title')
            link = item.get('link', '')
            publisher = item.get('publisher', 'News')
            if link:
                news_summary += f"- [{title}]({link}) (Source: {publisher})\n"
                count += 1
    except Exception as e:
        print(f"⚠️ 뉴스 수집 중 오류: {e}")
        return "News fetching failed."

    return news_summary

def generate_blog_post(market_data, news_data):
    if not GEMINI_API_KEY: return "Error: API Key missing."

    model = get_gemini_model()
    if not model: return "Error: No available models."

    now = datetime.datetime.now(SEOUL_TZ)
    date_str = now.strftime('%Y-%m-%d %H:%M:%S')

    # ---------------------------------------------------------
    # [Step 1] 전문 경제 분석가 모드
    # ---------------------------------------------------------
    prompt_analyst = f"""
    [Identity & Persona]
    You are a **Top-tier Economic Analyst**.
    Your writing style is professional, data-driven, cynical yet insightful.
    **Constraint:** Do NOT mention your name, "TheRichWay", or "Writer".

    [Input Data]
    - Market Data: {market_data}
    - Real Global News: {news_data}
    - Topic: {FOCUS_TOPIC}

    [Visual & Readability Requirements]
    1. **Markdown Tables**: MUST use tables for indices/sector comparison.
    2. **Mermaid Charts**: Include 1 simple Mermaid chart (e.g., `pie`) if applicable.
    3. **Formatting**: Use bold text for key figures.

    [Structure]
    1. **Market Pulse**: Summary Table + Comment.
    2. **Deep Dive**: Analysis of the topic.
    3. **Strategy**: Investment advice.
    4. **References** (CRITICAL):
       - Title: "## 📚 주요 참고 뉴스"
       - **Rules**:
         1. For Global news, USE THE REAL LINKS provided in 'Input Data'.
         2. For Korean news (80%), provide links to the **Main Finance Section** of major portals if specific article URLs are unknown (e.g., `[한경 글로벌마켓](https://www.hankyung.com/globalmarket)`), OR valid real links if you know them. Do NOT generate fake deep-links.
         3. Format: `- [Title](URL)`
    5. **Tags**:
       - Title: "### 🏷️ 태그"
       - Content: Generate 5 relevant hashtags (e.g., #미국증시 #S&P500 ...)

    [Language]: Korean (Natural, Professional).
    """

    draft = ""
    try:
        draft = model.generate_content(prompt_analyst).text
    except Exception as e:
        return f"Error in Step 1: {str(e)}"

    # ---------------------------------------------------------
    # [Step 2] 편집장 모드
    # ---------------------------------------------------------
    prompt_editor = f"""
    [Role] Chief Editor
    [Input Draft]
    {draft}

    [Task] Final Polish.
    1. **Link Check**: Ensure links are `[Title](URL)`.
    2. **Formatting**: Ensure Tables/Mermaid are correct.
    3. **Tags**: Ensure 5 hashtags exist at the bottom.
    4. **Front Matter**:
    ---
    layout: single
    title: "YOUR_CATCHY_TITLE"
    date: {date_str}
    categories: ["경제·재테크", "미국증시"]
    published: false
    toc: true
    ---

    [Output] Return ONLY the final Markdown content.
    """

    try:
        final_response = model.generate_content(prompt_editor).text
        content = final_response.strip()

        # Clean up
        if content.startswith("```markdown"): content = content.replace("```markdown", "", 1)
        if content.startswith("```"): content = content.replace("```", "", 1)
        if content.endswith("```"): content = content[:-3]

        return content.strip() + DISCLAIMER_TEXT

    except Exception as e:
        return f"Error in Step 2: {str(e)}"

def save_and_notify(content):
    if "Error" in content:
        print(f"❌ [API Error] {content}")
        return

    today = datetime.datetime.now(SEOUL_TZ).strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now(SEOUL_TZ).strftime("%H%M")

    category_dir = "_posts/us-stock"
    os.makedirs(category_dir, exist_ok=True)

    filename = f"{today}-market-{timestamp}.md"
    filepath = f"{category_dir}/{filename}"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 포스팅 파일 생성 완료: {filepath}")

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        repo = os.environ.get("GITHUB_REPOSITORY", "user/repo")

        # [수정] URL 생성 시 f-string 내부에 마크다운 문법이 섞이지 않도록 주의
        # 텔레그램 버튼/링크용 순수 URL
        file_url = f"[https://github.com/](https://github.com/){repo}/blob/main/{filepath}"

        # 텔레그램 메시지 (HTML 모드)
        msg = (
            f"<b>📊 [미국 증시 리포트 생성]</b>\n\n"
            f"<b>주제:</b> {FOCUS_TOPIC}\n"
            f"<b>포함:</b> 데이터 표, 실제 뉴스 링크, 태그\n\n"
            f"검토 후 발행: <code>/publish</code>\n"
            f"<a href='{file_url}'>👉 리포트 미리보기 (클릭)</a>"
        )

        try:
            # [수정] requests.post URL을 순수 문자열로 구성 (가장 중요한 수정)
            api_url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_TOKEN}/sendMessage"

            response = requests.post(
                api_url,
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
            )

            if response.status_code == 200:
                print("✅ 텔레그램 알림 전송 성공")
            else:
                print(f"❌ 텔레그램 전송 실패: {response.text}")

        except Exception as e:
            print(f"❌ 텔레그램 연결 에러: {e}")

if __name__ == "__main__":
    market_data = get_market_data()
    news_data = get_real_news_links()

    post = generate_blog_post(market_data, news_data)
    save_and_notify(post)