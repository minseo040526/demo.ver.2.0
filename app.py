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
            df.columns = df.columns.str.strip().str.lower()
            df = df.rename(columns={'name': 'Name', 'price': 'Price', 'tags': 'Hashtags'}, errors='ignore')
            df['Category'] = category_name
            # 필요한 컬럼만 선택하고, 인덱스를 0부터 재설정 (안정성 확보)
            df = df[['Category', 'Name', 'Price', 'Hashtags']].reset_index(drop=True) 
            return df
        except FileNotFoundError:
            # 임시 데이터는 이전과 동일하게 유지
            if category_name == '베이커리':
                return pd.DataFrame({
                    'Category': ['베이커리', '베이커리', '베이커리', '베이커리'],
                    'Name': ['크로와상', '소금빵', '에그타르트', '샌드위치'],
                    'Price': [3500, 3200, 4000, 6000],
                    'Hashtags': ['#버터#고소한', '#짭짤한#인기', '#달콤한', '#든든한']
                })
            else:
                return pd.DataFrame({
                    'Category': ['음료', '음료', '음료', '음료'],
                    'Name': ['아메리카노', '카페 라떼', '녹차', '오렌지 주스'],
                    'Price': [4000, 5000, 4500, 5500],
                    'Hashtags': ['#깔끔#가벼운', '#부드러운#우유', '#전통#건강', '#상큼한']
                })

    df_bakery = load_data("Bakery_menu.csv", '베이커리')
    df_drink = load_data("Drink_menu.csv", '음료')

    df_menu = pd.concat([df_bakery, df_drink], ignore_index=True)
    
    def clean_tags(tags):
        if pd.isna(tags): return []
        tags_list = re.split(r'[#,\s]+', str(tags).strip())
        return [tag.strip() for tag in tags_list if tag.strip()]

    df_menu['Tag_List'] = df_menu['Hashtags'].apply(clean_tags)
    all_tags = sorted(list(set(tag for sublist in df_menu['Tag_List'] for tag in sublist if tag)))

    return df_menu, all_tags

# 데이터 로드 및 전처리
df_menu, all_tags = load_and_preprocess_data()
df_drinks = df_menu[df_menu['Category'] == '음료'].copy()
df_bakeries = df_menu[df_menu['Category'] == '베이커리'].copy()

# --- AI 메뉴 추천 함수 ---
def recommend_menu(person_count, budget, is_unlimited_budget, selected_tags, df_drinks, df_bakeries):
    
    total_budget = float('inf') if is_unlimited_budget else (budget * person_count)

    # 1. 필터링된 메뉴 목록 생성
    if selected_tags:
        # 안전하게 필터링 조건을 각 데이터프레임에 직접 적용
        drinks = df_drinks[df_drinks['Tag_List'].apply(lambda x: any(tag in selected_tags for tag in x))].copy()
        bakeries = df_bakeries[df_bakeries['Tag_List'].apply(lambda x: any(tag in selected_tags for tag in x))].copy()
    else:
        drinks = df_drinks.copy() 
        bakeries = df_bakeries.copy()

    recommendations = []
    
    if drinks.empty or bakeries.empty or len(drinks) < person_count:
        return recommendations
        
    attempts = 0
    max_attempts = 300 

    while len(recommendations) < 3 and attempts < max_attempts:
        attempts += 1
        
        # 1. 음료 선택 (인원수만큼)
        selected_drinks_df = drinks.sample(person_count, replace=True)
        drink_set = selected_drinks_df.to_dict('records')
        total_drink_price = selected_drinks_df['Price'].sum()
        
        remaining_budget = total_budget - total_drink_price
        
        bakery_set = []
        total_bakery_price = 0
        
        # 2. 베이커리 개수 결정 (1개 또는 2개)
        # 2개 구매가 가능한지 판단할 때, 베이커리 목록이 충분히 있는지 확인
        can_afford_two = (len(bakeries) >= 2) and (remaining_budget >= (bakeries['Price'].nsmallest(2).sum()))

        if (is_unlimited_budget or can_afford_two) and random.random() < 0.5: 
            # 2-1. 2개 베이커리 조합 시도
            
            # 베이커리 데이터프레임의 인덱스 리스트를 사용
            bakery_indices = list(bakeries.index)
            possible_pairs = []
            
            for i in range(len(bakery_indices)):
                for j in range(i + 1, len(bakery_indices)):
                    item1 = bakeries.loc[bakery_indices[i]]
                    item2 = bakeries.loc[bakery_indices[j]]
                    
                    if is_unlimited_budget or (item1['Price'] + item2['Price'] <= remaining_budget):
                        # 리스트에 딕셔너리로 변환된 항목 추가 (to_dict('records')와 동일한 형식)
                        possible_pairs.append([item1.to_dict(), item2.to_dict()]) 

            if possible_pairs:
                bakery_set = random.choice(possible_pairs)
                total_bakery_price = sum(item['Price'] for item in bakery_set)
                
        # 2-2. 1개 베이커리 조합 시도
        if not bakery_set:
            if is_unlimited_budget:
                affordable_bakeries = bakeries
            else:
                affordable_bakeries = bakeries[bakeries['Price'] <= remaining_budget]
                
            if not affordable_bakeries.empty:
                bakery = affordable_bakeries.sample(1).iloc[0]
                # Series를 to_dict()로 변환하여 리스트에 추가
                bakery_set = [bakery.to_dict()]
                total_bakery_price = bakery['Price']
        
        
        # 3. 최종 추천 리스트에 추가
        if bakery_set:
            total_price = total_drink_price + total_bakery_price
            
            # 고유성 체크를 위한 키 생성
            drink_names_sorted = sorted([item['Name'] for item in drink_set])
            bakery_names_sorted = sorted([item['Name'] for item in bakery_set])
            set_key = (tuple(drink_names_sorted), tuple(bakery_names_sorted))
            
            is_duplicate = any(rec['key'] == set_key for rec in recommendations)

            if (is_unlimited_budget or total_price <= total_budget) and not is_duplicate:
                recommendations.append({
                    'key': set_key, 
                    'drink_set': drink_set,
                    'bakery_set': bakery_set,
                    'total_price': total_price
                })

    return recommendations

# --- Streamlit 앱 구성 (이후 코드는 동일) ---

# Streamlit 앱 구성 부분은 이전 코드와 동일하게 유지됩니다.
st.set_page_config(layout="wide")

# 사이드바 (메뉴 추천 설정)
with st.sidebar:
    st.header("✨ AI 메뉴 추천 시스템 설정")
    
    st.subheader("인원 및 예산 설정")
    
    person_count = st.slider(
        "👨‍👩‍👧‍👦 인원수를 선택해주세요 (음료 개수)", 
        min_value=1, 
        max_value=5, 
        value=1
    )
    
    is_unlimited_budget = st.checkbox("💸 예산 상관없음 (무제한)", value=False)
    
    if 'total_budget' not in st.session_state: st.session_state['total_budget'] = 0

    # 1인당 예산 슬라이더
    budget_value = 8000
    if not is_unlimited_budget:
        # 슬라이더가 비활성화될 때 값을 유지하도록 처리
        budget = st.slider(
            "💰 1인당 예산을 설정해주세요", 
            min_value=5000, 
            max_value=15000, 
            value=budget_value, 
            step=500,
            key='budget_slider'
        )
        st.session_state['total_budget'] = budget * person_count
    else:
        # 비활성화된 슬라이더 표시 및 값 처리
        st.slider(
            "💰 1인당 예산을 설정해주세요", 
            min_value=5000, 
            max_value=15000, 
            value=budget_value, 
            step=500,
            disabled=True
        )
        st.session_state['total_budget'] = "무제한"
        budget = 0 
    
    # 레이블 업데이트
    budget_display_label = f" (총 예산: {st.session_state['total_budget']:,}원)" if st.session_state['total_budget'] != "무제한" else " (총 예산: 무제한)"
    st.markdown(f"1인당 예산 설정: **{budget_value:,}원**" + budget_display_label)
    
    
    st.subheader("선호 해시태그 선택 (최대 3개)")
    
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
    
    if is_unlimited_budget:
        budget_display = "무제한"
    else:
        budget_display = f"{st.session_state['total_budget']:,}원 (1인당 {budget:,}원)"
        
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
                    remaining_budget = st.session_state['total_budget'] - rec['total_price']
                    st.metric(
                        label="총 가격", 
                        value=f"{rec['total_price']:,}원", 
                        delta=f"{remaining_budget:,}원 남음"
                    )
                st.markdown("---")
                
                # 음료 추천 표시
                st.markdown(f"#### ☕ **음료 추천 ({person_count}개)**")
                drink_counts = pd.Series([item['Name'] for item in rec['drink_set']]).value_counts()
                for name, count in drink_counts.items():
                    original_price = df_drinks[df_drinks['Name'] == name]['Price'].iloc[0]
                    st.markdown(f"- **{name}** x{count} ({original_price:,}원)")
                    st.caption(f"  태그: {df_drinks[df_drinks['Name'] == name]['Hashtags'].iloc[0]}")
                
                # 베이커리 추천 표시
                st.markdown(f"#### 🍞 **베이커리 추천 ({len(rec['bakery_set'])}개)**")
                for item in rec['bakery_set']:
                    # 베이커리 아이템의 카테고리가 '베이커리'인지 확인 (추가 안정성 확보)
                    if item.get('Category') == '베이커리': 
                        st.markdown(f"- **{item['Name']}** ({item['Price']:,}원)")
                        st.caption(f"  태그: {item['Hashtags']}")
                    else:
                         # 디버깅용 메시지 (실제 서비스에서는 제거 가능)
                        st.warning(f"오류: 베이커리 자리에 {item.get('Category', '알 수 없는')} 메뉴 '{item['Name']}'가 추천되었습니다.")

                
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
