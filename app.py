import streamlit as st
import pandas as pd
import random
import re
# itertools.combinations 사용을 중단하여 로딩 문제를 해결합니다.
# from itertools import combinations 

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
            df = df[['Category', 'Name', 'Price', 'Hashtags']].reset_index(drop=True) 
            return df
        except FileNotFoundError:
            # 임시 데이터 (메뉴 개수를 충분히 확보)
            if category_name == '베이커리':
                return pd.DataFrame({
                    'Category': ['베이커리'] * 10,
                    'Name': ['크로와상', '소금빵', '에그타르트', '샌드위치', '마들렌', '치즈 베이글', '초코 스콘', '팥빙수(1인)', '치아바타', '잠봉 샌드위치'],
                    'Price': [3500, 3200, 4000, 6000, 2500, 3500, 4200, 6000, 4500, 8500],
                    'Hashtags': ['#버터#고소한', '#짭짤한#인기', '#달콤한', '#든든한', '#작은', '#치즈#고소한', '#달콤한#초코', '#달콤한', '#담백한', '#든든한']
                })
            else:
                return pd.DataFrame({
                    'Category': ['음료'] * 6,
                    'Name': ['아메리카노', '카페 라떼', '녹차', '오렌지 주스', '바닐라 라떼', '흑임자 라떼'],
                    'Price': [4000, 5000, 4500, 5500, 5500, 6000],
                    'Hashtags': ['#깔끔#가벼운', '#부드러운#우유', '#전통#건강', '#상큼한', '#달콤한#디저트용', '#고소한']
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

# --- 점수 기반 필터링 및 추천 함수 ---
def get_scored_menu(df, selected_tags):
    """메뉴와 선택된 태그 간의 일치 점수를 계산하여 새 컬럼에 추가하고 정렬합니다."""
    df_copy = df.copy() 
    if not selected_tags:
        df_copy['Score'] = 1 
    else:
        df_copy['Score'] = df_copy['Tag_List'].apply(lambda x: len(set(x) & set(selected_tags)))
    
    return df_copy.sort_values(by=['Score', 'Price'], ascending=[False, True]).reset_index(drop=True)

# 딕셔너리로 변환할 때 사용할 컬럼 목록
COLS_TO_DICT = ['Category', 'Name', 'Price', 'Hashtags', 'Score']

def recommend_menu(person_count, budget, is_unlimited_budget, selected_tags, bakery_count, df_drinks, df_bakeries):
    
    total_budget = float('inf') if is_unlimited_budget else (budget * person_count)
    
    scored_drinks = get_scored_menu(df_drinks, selected_tags)
    scored_bakeries = get_scored_menu(df_bakeries, selected_tags)

    if scored_drinks.empty or scored_bakeries.empty or len(scored_drinks) < person_count:
        return []
        
    recommendations = []
    
    attempts = 0
    max_attempts = 300 

    # 베이커리 풀 설정: 점수가 높은 상위 메뉴를 사용 (최소 10개)
    n_bakeries_pool = max(10, bakery_count, int(len(scored_bakeries) * 0.7)) 
    bakeries_pool = scored_bakeries.head(n_bakeries_pool)

    if len(bakeries_pool) < bakery_count:
        return []

    while len(recommendations) < 3 and attempts < max_attempts:
        attempts += 1
        
        # 1. 음료 선택 (점수가 높은 메뉴를 우선적으로 선택)
        n_drinks = max(5, int(len(scored_drinks) * 0.7)) 
        drinks_pool = scored_drinks.head(n_drinks)
        
        selected_drinks_df = drinks_pool.sample(person_count, replace=True)
        drink_set = selected_drinks_df[COLS_TO_DICT].to_dict('records')
        total_drink_price = selected_drinks_df['Price'].sum()
        drink_score = selected_drinks_df['Score'].sum()
        
        remaining_budget = total_budget - total_drink_price
        
        # 2. 베이커리 선택 (무작위 샘플링 기반으로 복잡도 감소)
        bakery_set = []
        total_bakery_price = 0
        bakery_score = 0
        
        # 예산이 충분한 메뉴만 필터링 (무제한 예산이 아니면서 남은 예산보다 가격이 비싼 메뉴 제외)
        if not is_unlimited_budget:
            # 베이커리 풀을 예산에 맞춰 필터링
            affordable_pool = bakeries_pool[bakeries_pool['Price'] <= remaining_budget].copy()
            
            # 남은 예산으로 최소한의 베이커리(가장 싼 메뉴 * bakery_count)도 못 살 경우 조합 불가
            if affordable_pool.empty:
                continue

            # 샘플링을 위해 affordable_pool을 사용
            current_pool = affordable_pool
        else:
            current_pool = bakeries_pool.copy()

        # 베이커리 개수만큼 무작위 샘플링 (중복 제거)
        if len(current_pool) >= bakery_count:
            try:
                # 점수 높은 메뉴를 우선적으로 샘플링하도록, 가중치를 점수에 비례하게 적용
                weights = current_pool['Score'].apply(lambda x: x if x > 0 else 0.1)
                
                selected_bakeries = current_pool.sample(
                    n=bakery_count, 
                    replace=False, # 중복 선택 방지
                    weights=weights
                )
                
                bakery_set = selected_bakeries[COLS_TO_DICT].to_dict('records')
                total_bakery_price = selected_bakeries['Price'].sum()
                bakery_score = selected_bakeries['Score'].sum()

                # 최종 예산 확인 (샘플링 후 합산된 가격이 예산을 초과할 수 있으므로)
                if not is_unlimited_budget and total_bakery_price > remaining_budget:
                    # 예산 초과 시 조합 실패로 간주하고 다음 시도로 넘어감
                    continue
                    
            except ValueError:
                 # weights가 모두 0이거나 기타 샘플링 오류 시
                 continue
        else:
            # 베이커리 풀 크기가 필요한 개수보다 작으면 조합 불가
            continue
        
        
        # 3. 최종 추천 리스트에 추가
        if bakery_set:
            total_price = total_drink_price + total_bakery_price
            total_score = drink_score + bakery_score
            
            drink_names_sorted = sorted([item['Name'] for item in drink_set])
            bakery_names_sorted = sorted([item['Name'] for item in bakery_set])
            set_key = (tuple(drink_names_sorted), tuple(bakery_names_sorted))
            
            is_duplicate = any(rec['key'] == set_key for rec in recommendations)

            if not is_duplicate:
                recommendations.append({
                    'key': set_key, 
                    'drink_set': drink_set,
                    'bakery_set': bakery_set,
                    'total_price': total_price,
                    'score': total_score 
                })

    recommendations.sort(key=lambda x: x['score'], reverse=True)
    return recommendations


# --- Streamlit 앱 구성 (변경 없음) ---
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
    
    bakery_count = st.slider(
        "🍞 베이커리 개수를 선택해주세요", 
        min_value=1, 
        max_value=4, 
        value=2
    )

    is_unlimited_budget = st.checkbox("💸 예산 상관없음 (무제한)", value=False)
    
    if 'total_budget' not in st.session_state: st.session_state['total_budget'] = 0

    budget_value = 8000
    if not is_unlimited_budget:
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
        budget_display = "무제
