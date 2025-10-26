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
    
    # 점수 높은 순, 가격 낮은 순 정렬
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
    max_attempts = 100 
    
    DRINK_POOL_SIZE = min(20, len(scored_drinks))
    BAKERY_POOL_SIZE = min(20, len(scored_bakeries))
    
    drinks_pool = scored_drinks.head(DRINK_POOL_SIZE)
    # 베이커리 풀은 .copy()를 사용해 독립적인 DataFrame 유지
    bakeries_pool = scored_bakeries.head(BAKERY_POOL_SIZE).copy().reset_index(drop=True) 

    if len(bakeries_pool) < bakery_count:
        return []


    while len(recommendations) < 3 and attempts < max_attempts:
        attempts += 1
        
        # 1. 음료 선택 (점수 가중치 기반 샘플링)
        try:
            weights = drinks_pool['Score'].apply(lambda x: x if x > 0 else 0.1)
            selected_drinks_df = drinks_pool.sample(
                n=person_count, 
                replace=True, 
                weights=weights
            )
            
        except ValueError:
            continue

        drink_set = selected_drinks_df[COLS_TO_DICT].to_dict('records')
        total_drink_price = selected_drinks_df['Price'].sum()
        drink_score = selected_drinks_df['Score'].sum()
        
        remaining_budget = total_budget - total_drink_price
        
        # 2. 베이커리 선택 (순차적/점수 기반 선택)
        bakery_set = []
        
        current_bakery_price = 0
        current_bakery_score = 0
        current_bakery_items = []
        
        # 현재 탐색 풀: 매 반복마다 베이커리 풀의 복사본을 사용하여 메뉴 중복 선택을 방지
        temp_bakery_pool = bakeries_pool.copy()
        
        is_successful_bakery_selection = True
        
        for i in range(bakery_count):
            
            # 남은 예산으로 구매 가능한 메뉴만 필터링
            if not is_unlimited_budget:
                # 현재 남은 잔액으로 구매 가능한 메뉴
                affordable_items = temp_bakery_pool[
                    temp_bakery_pool['Price'] <= remaining_budget - current_bakery_price
                ]
            else:
                affordable_items = temp_bakery_pool

            if affordable_items.empty:
                is_successful_bakery_selection = False
                break
                
            # 가장 점수가 높은 메뉴를 선택 (가장 위에 있으므로 iloc[0])
            # 다만, 다양한 조합 생성을 위해 상위 3개 중 하나를 랜덤으로 선택
            top_affordable = affordable_items.head(3)
            
            if top_affordable.empty:
                 is_successful_bakery_selection = False
                 break
                 
            # 상위 항목 중에서 무작위로 하나 선택
            # DataFrame에서 to_dict('records')를 사용해 안정성 확보
            selected_bakery_df = top_affordable.sample(1)
            selected_bakery_dict = selected_bakery_df[COLS_TO_DICT].to_dict('records')[0]
            
            # 선택된 메뉴 정보 업데이트
            current_bakery_price += selected_bakery_dict['Price']
            current_bakery_score += selected_bakery_dict['Score']
            current_bakery_items.append(selected_bakery_dict)
            
            # 다음 선택에서 중복을 피하기 위해 풀에서 제거
            # Name을 기준으로 제거
            temp_bakery_pool = temp_bakery_pool[temp_bakery_pool['Name'] != selected_bakery_dict['Name']].reset_index(drop=True)
        
        
        if is_successful_bakery_selection and len(current_bakery_items) == bakery_count:
            bakery_set = current_bakery_items
            total_bakery_price = current_bakery_price
            bakery_score = current_bakery_score
        else:
            continue # 베이커리 선택 실패

        
        # 3. 최종 추천 리스트에 추가
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


# --- Streamlit 앱 구성 ---
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
    
    # 여기서 문자열을 닫는 따옴표("무제한")가 빠져있어 오류가 발생했을 가능성이 높습니다.
    if is_unlimited_budget:
        budget_display = "무제한" 
    else:
        budget_display = f"{st.session_state['total_budget']:,}원 (1인당 {budget:,}원)"
        
    st.info(f"선택 인원: **{person_count}명** | 총 예산: **{budget_display}** | 베이커리 개수: **{bakery_count}개** | 선택 태그: **{', '.join(selected_tags) if selected_tags else '없음'}**")

    # 추천 실행 및 결과 표시
    recommendations = recommend_menu(person_count, budget, is_unlimited_budget, selected_tags, bakery_count, df_drinks, df_bakeries)

    if recommendations:
        st.subheader(f"✅ 조건에 맞는 조합 **{len(recommendations)}세트**를 추천합니다! (점수 높은 순)")
        
        cols = st.columns(len(recommendations))
        
        for i, rec in enumerate(recommendations):
            with cols[i]:
                st.markdown(f"### 🍰 추천 세트 #{i+1}")
                st.caption(f"**총 점수: {rec['score']}**") 
                
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
                    item_info = next(item for item in rec['drink_set'] if item['Name'] == name)
                    st.markdown(f"- **{name}** x{count} ({item_info['Price']:,}원)")
                    st.caption(f"  태그: {item_info['Hashtags']} (점수: {item_info['Score']})")
                
                # 베이커리 추천 표시
                st.markdown(f"#### 🍞 **베이커리 추천 ({bakery_count}개)**")
                for item in rec['bakery_set']:
                    if item.get('Category') == '베이커리': 
                        st.markdown(f"- **{item['Name']}** ({item['Price']:,}원)")
                        st.caption(f"  태그: {item['Hashtags']} (점수: {item['Score']})")
                    
    else:
        if len(df_bakeries) < bakery_count:
            st.warning(f"😭 베이커리 메뉴판에 총 {len(df_bakeries)}개의 메뉴만 있습니다. **선택하신 베이커리 개수({bakery_count}개)보다 적습니다.** 베이커리 개수를 줄여주세요.")
        else:
            st.warning("😭 해당 조건(인원수/예산/태그/베이커리 개수)에 맞는 조합을 찾을 수 없습니다. 예산을 늘리거나, 태그를 제거하거나, 베이커리 개수를 줄여보세요.")


with tab2:
    st.header("📜 메뉴판")
    st.markdown("베이커리의 전체 메뉴판을 확인하세요.")

    # 전체 메뉴표 데이터프레임으로 표시
    st.subheader("전체 메뉴 리스트")
    st.dataframe(df_menu[['Category', 'Name', 'Price', 'Hashtags']].rename(columns={
        'Category': '구분', 
        'Name': '메뉴명', 
        'Price': '가격 (원)',
        'Hashtags': '태그'
    }), use_container_width=True, hide_index=True)
