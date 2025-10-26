import streamlit as st
import pandas as pd
import random
import re

# --- 데이터 로드 및 전처리 함수 ---
@st.cache_data
def load_and_preprocess_data():
    """두 개의 CSV 파일을 로드하고 전처리하여 하나의 메뉴 DataFrame을 반환합니다."""
    
    def load_data(filename, category_name):
        try:
            df = pd.read_csv(filename)
            # 모든 컬럼 이름을 소문자로, 공백 제거
            df.columns = df.columns.str.strip().str.lower()
            # 'name', 'price', 'tags' 컬럼이 필요합니다.
            df = df.rename(columns={'name': 'Name', 'price': 'Price', 'tags': 'Hashtags'}, errors='ignore')
            df['Category'] = category_name
            # 필요한 컬럼만 선택
            df = df[['Category', 'Name', 'Price', 'Hashtags']].copy()
            return df
        except FileNotFoundError:
            st.error(f"⚠️ '{filename}' 파일을 찾을 수 없습니다. 임시 {category_name} 데이터를 사용합니다.")
            if category_name == '베이커리':
                return pd.DataFrame({
                    'Category': ['베이커리', '베이커리', '베이커리', '베이커리'],
                    'Name': ['크로와상', '소금빵', '에그타르트', '샌드위치'],
                    'Price': [3500, 3200, 4000, 6000],
                    'Hashtags': ['#버터#고소한', '#짭짤한#인기', '#달콤한', '#든든한']
                })
            else: # 음료
                return pd.DataFrame({
                    'Category': ['음료', '음료', '음료', '음료'],
                    'Name': ['아메리카노', '카페 라떼', '녹차', '오렌지 주스'],
                    'Price': [4000, 5000, 4500, 5500],
                    'Hashtags': ['#깔끔#가벼운', '#부드러운#우유', '#전통#건강', '#상큼한']
                })

    df_bakery = load_data("Bakery_menu.csv", '베이커리')
    df_drink = load_data("Drink_menu.csv", '음료')

    # 1. 데이터 통합
    df_menu = pd.concat([df_bakery, df_drink], ignore_index=True)
    
    # 2. 해시태그 전처리 (쉼표, 공백 제거 후 리스트로 변환)
    def clean_tags(tags):
        if pd.isna(tags):
            return []
        tags_list = re.split(r'[#,\s]+', str(tags).strip())
        return [tag.strip() for tag in tags_list if tag.strip()]

    df_menu['Tag_List'] = df_menu['Hashtags'].apply(clean_tags)
    
    # 3. 사용 가능한 모든 해시태그 추출 (중복 제거)
    all_tags = sorted(list(set(tag for sublist in df_menu['Tag_List'] for tag in sublist if tag)))

    return df_menu, all_tags

# 데이터 로드 및 전처리
df_menu, all_tags = load_and_preprocess_data()
df_drinks = df_menu[df_menu['Category'] == '음료']
df_bakeries = df_menu[df_menu['Category'] == '베이커리']

# --- AI 메뉴 추천 함수 ---
def recommend_menu(person_count, budget, is_unlimited_budget, selected_tags, df_drinks, df_bakeries):
    """
    인원수, 예산, 해시태그를 고려하여 음료(인원수)와 베이커리(1~2개) 조합 3세트를 추천합니다.
    """
    
    # 총 예산 계산
    if is_unlimited_budget:
        total_budget = float('inf')
    else:
        total_budget = budget * person_count

    # 1. 필터링된 메뉴 목록 생성
    if selected_tags:
        filter_condition = df_menu['Tag_List'].apply(lambda x: any(tag in selected_tags for tag in x))
        drinks = df_drinks[filter_condition[df_drinks.index]].copy()
        bakeries = df_bakeries[filter_condition[df_bakeries.index]].copy()
    else:
        drinks = df_drinks.copy() 
        bakeries = df_bakeries.copy()

    recommendations = []
    
    # 예외 처리
    if drinks.empty or bakeries.empty or len(drinks) < person_count:
        return recommendations
        
    attempts = 0
    max_attempts = 300 

    while len(recommendations) < 3 and attempts < max_attempts:
        attempts += 1
        
        # 1. 음료 선택 (인원수만큼)
        # 중복된 음료를 허용하여 인원수만큼 선택
        selected_drinks_df = drinks.sample(person_count, replace=True)
        drink_set = selected_drinks_df.to_dict('records')
        total_drink_price = selected_drinks_df['Price'].sum()
        
        remaining_budget = total_budget - total_drink_price
        
        bakery_set = []
        total_bakery_price = 0
        
        # 2. 베이커리 개수 결정 (1개 또는 2개)
        
        # 남은 예산이 가장 싼 베이커리 2개보다 많을 경우 2개 추천 시도
        can_afford_two = (len(bakeries) >= 2) and (remaining_budget >= (bakeries['Price'].min() * 2))

        # 예산 무제한이거나, 2개 구매 가능하고 50% 확률 성공
        if (is_unlimited_budget or can_afford_two) and random.random() < 0.5: 
            # 2-1. 2개 베이커리 조합 시도
            
            possible_pairs = []
            bakery_list = [row for index, row in bakeries.iterrows()]
            
            # 모든 고유한 쌍을 확인
            for i in range(len(bakery_list)):
                for j in range(i + 1, len(bakery_list)):
                    item1 = bakery_list[i]
                    item2 = bakery_list[j]
                    if is_unlimited_budget or (item1['Price'] + item2['Price'] <= remaining_budget):
                        possible_pairs.append([item1, item2])

            if possible_pairs:
                bakery_set = random.choice(possible_pairs)
                total_bakery_price = sum(item['Price'] for item in bakery_set)
                
        # 2-2. 1개 베이커리 조합 시도 (2개 시도 실패 또는 처음부터 1개 시도)
        if not bakery_set:
            if is_unlimited_budget:
                affordable_bakeries = bakeries
            else:
                affordable_bakeries = bakeries[bakeries['Price'] <= remaining_budget]
                
            if not affordable_bakeries.empty:
                bakery = affordable_bakeries.sample(1).iloc[0]
                bakery_set = [bakery.to_dict()]
                total_bakery_price = bakery['Price']
        
        
        # 3. 유효한 조합일 경우 최종 추천 리스트에 추가
        if bakery_set:
            total_price = total_drink_price + total_bakery_price
            
            # 고유성 체크를 위한 키 생성: (정렬된 음료 이름 리스트, 정렬된 베이커리 이름 리스트)
            drink_names_sorted = sorted([item['Name'] for item in drink_set])
            bakery_names_sorted = sorted([item['Name'] for item in bakery_set])
            set_key = (tuple(drink_names_sorted), tuple(bakery_names_sorted))
            
            is_duplicate = any(rec['key'] == set_key for rec in recommendations)

            # 예산 무제한이거나, 총 가격이 예산 내일 경우
            if (is_unlimited_budget or total_price <= total_budget) and not is_duplicate:
                recommendations.append({
                    'key': set_key, 
                    'drink_set': drink_set,
                    'bakery_set': bakery_set,
                    'total_price': total_price
                })

    return recommendations

# --- Streamlit 앱 구성 ---
st.set_page_config(layout="wide")

# 사이드바 (메뉴 추천 설정)
with st.sidebar:
    st.header("✨ AI 메뉴 추천 시스템 설정")
    
    st.subheader("인원 및 예산 설정")
    
    # 인원수 설정
    person_count = st.slider(
        "👨‍👩‍👧‍👦 인원수를 선택해주세요 (음료 개수)", 
        min_value=1, 
        max_value=5, 
        value=1
    )
    
    # 예산 무제한 체크박스
    is_unlimited_budget = st.checkbox("💸 예산 상관없음 (무제한)", value=False)
    
    # 1인당 예산 설정
    budget_label = f"💰 1인당 예산을 설정해주세요 (총 예산: {st.session_state.get('total_budget', 0):,}원)"
    budget = st.slider(
        budget_label, 
        min_value=5000, 
        max_value=15000, 
        value=8000, 
        step=500,
        disabled=is_unlimited_budget # 무제한 체크 시 비활성화
    )
    
    # 총 예산 계산 및 상태 저장 (표시용)
    if is_unlimited_budget:
        st.session_state['total_budget'] = "무제한"
    else:
        st.session_state['total_budget'] = budget * person_count
    
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
    st.button("🔄 추천 새로고침", type="primary")

# 메인 화면 구성
st.title("🤖 AI 베이커리 메뉴 추천 시스템")

# 탭 구성
tab1, tab2 = st.tabs(["AI 메뉴 추천", "메뉴판"])

with tab1:
    st.header("AI 메뉴 추천 결과")
    
    # 정보 요약
    budget_display = "무제한" if is_unlimited_budget else f"{st.session_state['total_budget']:,}원 (1인당 {budget:,}원)"
    st.info(f"선택 인원: **{person_count}명** | 총 예산: **{budget_display}** | 선택 태그: **{', '.join(selected_tags) if selected_tags else '없음'}**")

    # 추천 실행 및 결과 표시
    recommendations = recommend_menu(person_count, budget, is_unlimited_budget, selected_tags, df_drinks, df_bakeries)

    if recommendations:
        st.subheader(f"✅ 조건에 맞는 조합 **{len(recommendations)}세트**를 추천합니다!")
        
        cols = st.columns(len(recommendations))
        
        for i, rec in enumerate(recommendations):
            with cols[i]:
                st.markdown(f"### 🍰 추천 세트 #{i+1}")
                
                # 가격 정보 표시
                if is_unlimited_budget:
                    st.markdown(f"**총 가격: {rec['total_price']:,}원**")
                else:
                    st.metric(
                        label="총 가격", 
                        value=f"{rec['total_price']:,}원", 
                        delta=f"{st.session_state['total_budget'] - rec['total_price']:,}원 남음"
                    )
                st.markdown("---")
                
                # 음료 추천 표시
                st.markdown(f"#### ☕ **음료 추천 ({person_count}개)**")
                # 음료 이름과 개수를 딕셔너리로 계산
                drink_counts = pd.Series([item['Name'] for item in rec['drink_set']]).value_counts()
                for name, count in drink_counts.items():
                    # 원래 가격을 찾아서 표시
                    original_price = df_drinks[df_drinks['Name'] == name]['Price'].iloc[0]
                    st.markdown(f"- **{name}** x{count} ({original_price:,}원)")
                    st.caption(f"  태그: {df_drinks[df_drinks['Name'] == name]['Hashtags'].iloc[0]}")
                
                # 베이커리 추천 표시
                st.markdown(f"#### 🍞 **베이커리 추천 ({len(rec['bakery_set'])}개)**")
                for item in rec['bakery_set']:
                    st.markdown(f"- **{item['Name']}** ({item['Price']:,}원)")
                    st.caption(f"  태그: {item['Hashtags']}")
                
    else:
        st.warning("😭 해당 조건(인원수/예산/태그)에 맞는 조합을 찾을 수 없거나, 메뉴판에 메뉴가 충분하지 않습니다. 조건을 조정해보세요.")


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
