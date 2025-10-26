import streamlit as st
import pandas as pd
import random
import re

# --- 데이터 로드 및 전처리 함수 ---
def load_and_preprocess_data():
    """두 개의 CSV 파일을 로드하고 전처리하여 하나의 메뉴 DataFrame을 반환합니다."""
    
    # 1. 베이커리 메뉴 로드
    try:
        df_bakery = pd.read_csv("Bakery_menu.csv")
        df_bakery.columns = df_bakery.columns.str.strip().str.lower()
        # 'category', 'name', 'price', 'tags' 컬럼이 필요합니다.
        df_bakery['Category'] = '베이커리' # 구분을 위해 명시적으로 '베이커리'로 통일
        df_bakery = df_bakery.rename(columns={'name': 'Name', 'price': 'Price', 'tags': 'Hashtags'})
        df_bakery = df_bakery[['Category', 'Name', 'Price', 'Hashtags']].copy()
    except FileNotFoundError:
        st.error("⚠️ 'Bakery_menu.csv' 파일을 찾을 수 없습니다. 임시 베이커리 데이터를 사용합니다.")
        df_bakery = pd.DataFrame({
            'Category': ['베이커리', '베이커리', '베이커리'],
            'Name': ['크로와상', '소금빵', '에그타르트'],
            'Price': [3500, 3200, 4000],
            'Hashtags': ['#버터#고소한', '#짭짤한#인기', '#달콤한']
        })

    # 2. 음료 메뉴 로드
    try:
        df_drink = pd.read_csv("Drink_menu.csv")
        df_drink.columns = df_drink.columns.str.strip().str.lower()
        df_drink = df_drink.rename(columns={'name': 'Name', 'price': 'Price', 'tags': 'Hashtags'})
        df_drink['Category'] = '음료' # 구분을 위해 명시적으로 '음료'로 통일
        df_drink = df_drink[['Category', 'Name', 'Price', 'Hashtags']].copy()
    except FileNotFoundError:
        st.error("⚠️ 'Drink_menu.csv' 파일을 찾을 수 없습니다. 임시 음료 데이터를 사용합니다.")
        df_drink = pd.DataFrame({
            'Category': ['음료', '음료', '음료'],
            'Name': ['아메리카노', '카페 라떼', '녹차'],
            'Price': [4000, 5000, 4500],
            'Hashtags': ['#깔끔#가벼운', '#부드러운#우유', '#전통#건강']
        })

    # 3. 데이터 통합
    df_menu = pd.concat([df_bakery, df_drink], ignore_index=True)
    
    # 4. 해시태그 전처리 (쉼표, 공백 제거 후 리스트로 변환)
    def clean_tags(tags):
        if pd.isna(tags):
            return []
        # '#', ',', 공백으로 분리하고, 빈 문자열/공백 제거 후 고유값 리스트 반환
        tags_list = re.split(r'[#,\s]+', str(tags).strip())
        return [tag.strip() for tag in tags_list if tag.strip()]

    df_menu['Tag_List'] = df_menu['Hashtags'].apply(clean_tags)
    
    # 5. 사용 가능한 모든 해시태그 추출 (중복 제거)
    all_tags = sorted(list(set(tag for sublist in df_menu['Tag_List'] for tag in sublist if tag)))

    return df_menu, all_tags

# 데이터 로드 및 전처리
df_menu, all_tags = load_and_preprocess_data()

# --- AI 메뉴 추천 함수 ---
def recommend_menu(budget, selected_tags, df_menu):
    """
    예산과 해시태그를 고려하여 음료와 베이커리 조합 3세트를 추천합니다.
    """
    
    # 1. 필터링된 메뉴 목록 생성
    # 선택된 태그가 하나라도 포함된 메뉴만 필터링
    if selected_tags:
        filtered_menu = df_menu[df_menu['Tag_List'].apply(lambda x: any(tag in selected_tags for tag in x))]
    else:
        filtered_menu = df_menu.copy() # 태그 선택이 없으면 전체 메뉴 사용

    # '베이커리'는 빵, 샌드위치, 디저트, 샐러드 등 모든 '음료 외' 항목을 포함합니다.
    # 하지만 사용자의 요구사항에 따라 '음료'와 '베이커리'를 따로 추천해야 하므로,
    # 여기서는 '음료' (df_drink에서 온 것)와 '베이커리/빵' (df_bakery에서 온 것)으로 구분합니다.
    drinks = filtered_menu[filtered_menu['Category'] == '음료']
    # '베이커리' 카테고리를 가진 모든 메뉴를 '베이커리류'로 간주합니다. (샌드위치, 샐러드 등 포함)
    bakeries = filtered_menu[filtered_menu['Category'] == '베이커리'] 

    recommendations = []
    
    # 2. 가능한 조합 찾기 (최대 3세트)
    
    if drinks.empty or bakeries.empty:
        return recommendations
        
    attempts = 0
    max_attempts = 150 # 무한 루프 방지

    while len(recommendations) < 3 and attempts < max_attempts:
        attempts += 1
        
        # 무작위로 음료와 베이커리 하나씩 선택
        try:
            drink = drinks.sample(1, replace=True).iloc[0]
            bakery = bakeries.sample(1, replace=True).iloc[0]
        except ValueError:
            # 메뉴가 1개뿐일 때 sample(1, replace=True) 오류 방지
            if len(drinks) == 1: drink = drinks.iloc[0]
            if len(bakeries) == 1: bakery = bakeries.iloc[0]
        
        total_price = drink['Price'] + bakery['Price']
        
        # 3. 예산 조건 확인 및 중복 방지
        current_set = {
            'drink_name': drink['Name'], 
            'bakery_name': bakery['Name'],
            'total_price': total_price
        }

        is_duplicate = any(
            rec['drink_name'] == current_set['drink_name'] and 
            rec['bakery_name'] == current_set['bakery_name'] 
            for rec in recommendations
        )

        if total_price <= budget and not is_duplicate:
            recommendations.append(current_set)

    return recommendations

# --- Streamlit 앱 구성 ---
st.set_page_config(layout="wide")

# 사이드바 (메뉴 추천 설정)
with st.sidebar:
    st.header("✨ AI 메뉴 추천 시스템 설정")
    st.subheader("예산 설정")
    # 예산 입력 위젯
    budget = st.slider(
        "💰 최대 예산을 설정해주세요 (원)", 
        min_value=5000, 
        max_value=30000, 
        value=10000, 
        step=500
    )

    st.subheader("선호 해시태그 선택 (최대 3개)")
    
    # 해시태그 선택 위젯
    selected_tags = st.multiselect(
        "📌 선호하는 키워드를 선택하세요:",
        options=all_tags,
        default=[],
        max_selections=3,
        help="메뉴의 특징을 나타내는 키워드를 최대 3개까지 선택할 수 있습니다."
    )
    
    st.markdown("---")
    # 버튼 추가 (없어도 자동 실행되지만, 사용자 경험을 위해 추가)
    st.button("🔄 추천 새로고침", type="primary")

# 메인 화면 구성
st.title("🤖 AI 베이커리 메뉴 추천 시스템")

# 탭 구성
tab1, tab2 = st.tabs(["AI 메뉴 추천", "메뉴판"])

with tab1:
    st.header("AI 메뉴 추천 결과")
    st.info(f"선택 예산: **{budget:,}원** | 선택 태그: **{', '.join(selected_tags) if selected_tags else '없음'}**")

    # 추천 실행 및 결과 표시
    recommendations = recommend_menu(budget, selected_tags, df_menu)

    if recommendations:
        st.subheader(f"✅ 예산 **{budget:,}원** 안에서 가능한 조합 **{len(recommendations)}세트**를 추천합니다!")
        
        # 추천 결과를 컬럼으로 나누어 표시
        cols = st.columns(len(recommendations))
        
        for i, rec in enumerate(recommendations):
            # 추천된 메뉴 정보를 데이터프레임에서 다시 찾습니다.
            drink_info = df_menu[(df_menu['Name'] == rec['drink_name']) & (df_menu['Category'] == '음료')].iloc[0]
            bakery_info = df_menu[(df_menu['Name'] == rec['bakery_name']) & (df_menu['Category'] == '베이커리')].iloc[0]

            with cols[i]:
                st.markdown(f"### 🍰 추천 세트 #{i+1}")
                st.metric(
                    label="총 가격", 
                    value=f"{rec['total_price']:,}원", 
                    delta=f"{budget - rec['total_price']:,}원 남음"
                )
                st.markdown("---")
                
                # 음료 추천 표시
                st.markdown(f"#### ☕ **음료 추천**")
                st.markdown(f"**{drink_info['Name']}** ({drink_info['Price']:,}원)")
                st.caption(f"태그: {drink_info['Hashtags']}")
                
                # 베이커리 추천 표시
                st.markdown(f"#### 🍞 **베이커리 추천**")
                st.markdown(f"**{bakery_info['Name']}** ({bakery_info['Price']:,}원)")
                st.caption(f"태그: {bakery_info['Hashtags']}")
                
    else:
        # 추천 실패 메시지
        st.warning("😭 해당 조건(예산/태그)에 맞는 조합을 찾을 수 없거나, 메뉴판에 메뉴가 충분하지 않습니다. 예산이나 해시태그를 조정해보세요.")


with tab2:
    st.header("📜 메뉴판")
    st.markdown("베이커리의 전체 메뉴판을 확인하세요.")

    # 메뉴판 사진 표시
    try:
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            st.image("menu_board_1.png", caption="메뉴판 (음료/베이커리 1)")
        with col_img2:
            st.image("menu_board_2.png", caption="메뉴판 (음료/베이커리 2)")
    except FileNotFoundError:
        st.error("⚠️ 메뉴판 이미지 파일(menu_board_1.png, menu_board_2.png)을 찾을 수 없습니다. 파일을 확인해주세요.")
        
    st.markdown("---")
    
    # 전체 메뉴표 데이터프레임으로 표시
    st.subheader("전체 메뉴 리스트")
    st.dataframe(df_menu[['Category', 'Name', 'Price', 'Hashtags']].rename(columns={
        'Category': '구분', 
        'Name': '메뉴명', 
        'Price': '가격 (원)',
        'Hashtags': '태그'
    }), use_container_width=True, hide_index=True)


# --- 앱 실행 방법 ---
# 1. 위의 코드를 'app.py'로 저장합니다.
# 2. 'Bakery_menu.csv', 'Drink_menu.csv', 'menu_board_1.png', 'menu_board_2.png' 파일을 'app.py'와 같은 폴더에 둡니다.
# 3. 터미널/명령 프롬프트에서 다음 명령어를 실행합니다:
#    streamlit run app.py