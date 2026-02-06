import os
import datetime
import pytz
import yfinance as yf
import google.generativeai as genai
import requests

# --- [환경변수 및 설정] ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "")
SEOUL_TZ = pytz.timezone('Asia/Seoul')

# [디스클레이머: 작은 글씨로 하단에 부착될 문구]
DISCLAIMER_TEXT = """
<br>
<hr>
<p style="font-size: 0.8em; color: #999; line-height: 1.4;">
<strong>[안내 및 면책 조항]</strong><br>
본 콘텐츠는 인공지능(AI) 모델을 활용하여 시장 데이터를 기반으로 자동 생성되었습니다.<br>
특정 종목에 대한 투자 권유가 아니며, 데이터의 지연이나 오류가 발생할 수 있습니다.<br>
투자에 대한 모든 책임은 투자자 본인에게 있습니다.<br>
내용에 오류가 있거나 저작권 문제가 발생할 경우, 관리자에게 문의하시면 즉시 삭제 또는 수정 조치하겠습니다.
</p>
"""

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """데이터 수집 로직 (기존과 동일하되 안정성 강화)"""
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

def generate_blog_post(market_data):
    if not GEMINI_API_KEY: return "Error: API Key missing."

    # [모델: 2.0 이상 우선 사용]
    models = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-3-flash-preview']
    model = None

    for m in models:
        try:
            model = genai.GenerativeModel(m)
            model.generate_content("test", generation_config={"max_output_tokens": 1})
            break
        except: continue

    if not model: return "Error: No available models."

    now = datetime.datetime.now(SEOUL_TZ)

    # [프롬프트 대수술: 가독성 및 UI/UX 고려]
    prompt = f"""
    [Role] Financial Data Analyst (Neutral, Professional, Concise)
    [Data] {market_data}
    [Topic] {FOCUS_TOPIC if FOCUS_TOPIC else 'Global Market Trends'}

    [Guidelines for UX/UI]
    1. **NO Filler Words**: Do NOT use phrases like "TheRichWay", "Report", "Senior Analyst", "Here is the analysis". Just start with the content.
    2. **Structure**: Use short paragraphs (2-3 lines max). Use <h3> for subtitles. Use Bullet points for key data.
    3. **Visuals**: Where appropriate, insert a simple Markdown Table or Mermaid Chart code for trends.
    4. **Tone**: Easy to understand for beginners, but professional data for experts.

    [Output Format - Front Matter must be exact]
    ---
    layout: single
    title: "주요 키워드로 본 오늘의 증시: {FOCUS_TOPIC if FOCUS_TOPIC else '미국 증시 브리핑'}"
    date: {now.strftime('%Y-%m-%d %H:%M:%S')}
    categories: ["경제·재테크", "미국증시"]
    published: false
    toc: true
    ---

    (Write the blog content here in Korean. Start directly with the hook.)

    ## 1. 시장 핵심 요약
    (Summary here)

    ## 2. 주요 지표 분석
    (Analysis here)

    ## 3. 투자자 관전 포인트
    (Conclusion here)
    """

    try:
        response = model.generate_content(prompt)
        content = response.text.strip()

        # Markdown 코드 블록 제거 (Front Matter 보호)
        if content.startswith("```markdown"): content = content.replace("```markdown", "", 1)
        if content.startswith("```"): content = content.replace("```", "", 1)
        if content.endswith("```"): content = content[:-3]

        # [자동 디스클레이머 부착]
        return content.strip() + DISCLAIMER_TEXT

    except Exception as e:
        return f"Error: {str(e)}"

def save_and_notify(content):
    if "Error" in content:
        print(f"❌ [API Error] 생성이 중단되었습니다. 원인: {content}")
        return

    today = datetime.datetime.now(SEOUL_TZ).strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now(SEOUL_TZ).strftime("%H%M")

    # 카테고리별 폴더 구조 생성
    category_path = "_posts/미국증시"
    os.makedirs(category_path, exist_ok=True)

    filename = f"{category_path}/{today}-market-{timestamp}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        repo = os.environ.get("GITHUB_REPOSITORY", "user/repo")
        url = f"https://github.com/{repo}/blob/main/{filename}"
        msg = f"📝 **[새로운 글 생성 완료]**\n주제: {FOCUS_TOPIC}\n\n내용 확인 후 '/publish' 하세요.\n[미리보기]({url})"
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    data = get_market_data()
    post = generate_blog_post(data)
    save_and_notify(post)