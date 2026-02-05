# ... (이전 import 문들은 동일)

# 환경변수 로드 부분에 추가
FOCUS_TOPIC = os.environ.get("FOCUS_TOPIC", "")

# ... (get_market_data 함수 동일)

def generate_blog_post(market_data):
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    today_date = datetime.datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')

    # 기본 프롬프트
    base_instruction = "위 데이터를 바탕으로 오늘자 미국 증시 시황을 분석해줘."

    # [NEW] 수동으로 특정 주제를 입력했을 경우 프롬프트 변경
    if FOCUS_TOPIC:
        print(f"🎯 Focus Topic Detected: {FOCUS_TOPIC}")
        base_instruction = f"위 데이터도 참고하되, 특히 **'{FOCUS_TOPIC}'** 이슈를 중점적으로 심층 분석해줘. 제목도 이 주제와 관련지어 짓고."

    prompt = f"""
    [Role] 월 방문자 100만 명의 미국 주식 파워 블로거 'The Rich Way'
    [Data] {market_data}
    [Date] {today_date}
    [Task] {base_instruction}
    [Format]
    - Front Matter 필수:
    ---
    layout: post
    title: "AI가 생성한 제목(이모지포함)"
    date: {datetime.datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')}
    categories: [미국주식]
    published: false
    ---
    - 글 구조: 서론 -> 본론(집중분석) -> 결론
    - 어조: 전문적이지만 쉽고 위트있게
    """

    response = model.generate_content(prompt)
    text = response.text.replace("```markdown", "").replace("```", "")
    return text

# ... (나머지 save_post, send_telegram_alert 함수 등은 동일)