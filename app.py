import streamlit as st
import pandas as pd
import random
import re

# --- 데이터 로드 및 전처리 ---
@st.cache_data
def load_data(file_path):
    """메뉴 데이터 로드 및 전처리"""
    try:
        # 파일명: 'menu.csv'
        df = pd.read_csv(file_path)
        # 태그를 리스트 형태로 변환 (예: "#달콤한,#부드러운" -> ['달콤한', '부드러운'])
        df['tags_list'] = df['tags'].apply(lambda x: [re.sub(r'#', '', tag).strip() for tag in x.split(',')])
        return df
    except FileNotFoundError:
        st.error(f"⚠️ 에러: {file_path} 파일을 찾을 수 없습니다. 파일을 확인해주세요.")
        st.error("💡 'menu.csv' 파일에 '커피' 및 '음료' 카테고리를 포함하여 업데이트해야 정상적인 추천이 가능합니다.")
        return pd.DataFrame()

menu_df = load_data('menu.csv')

# 사용 가능한 모든 태그 추출 (중복 제거)
all_tags = sorted(list(set(tag for sublist in menu_df['tags_list'].dropna() for tag in sublist)))

# 초기 세션 상태 설정
if 'user_db' not in st.session_state:
    st.session_state['user_db'] = {}
if 'phone_number' not in st.session_state:
    st.session_state['phone_number'] = None
if 'page' not in st.session_state:
    st.session_state['page'] = 'home'
if 'recommended_set' not in st.session_state:
    # 세트, 음료, 베이커리 데이터를 저장할 딕셔너리
    st.session_state['recommendation_results'] = {'set': [], 'drink': pd.DataFrame(), 'bakery': pd.DataFrame()}
    
# --- 페이지 이동 함수 ---
def set_page(page_name):
    st.session_state['page'] = page_name

# --- 컴포넌트 함수 ---
def show_coupon_status():
    """현재 사용자의 쿠폰 상태 표시"""
    phone = st.session_state['phone_number']
    if phone and phone in st.session_state['user_db']:
        coupons = st.session_state['user_db'][phone]['coupons']
        st.sidebar.markdown(f"**🎫 쿠폰함**")
        st.sidebar.info(f"사용 가능한 쿠폰: **{coupons}개**")

def use_coupon_toggle():
    """쿠폰 사용 여부 체크박스 및 적용 로직"""
    if st.session_state['phone_number'] and st.session_state['user_db'][st.session_state['phone_number']]['coupons'] > 0:
        st.session_state['use_coupon'] = st.checkbox(
            '🎫 쿠폰 1개 사용 (총 주문 금액 1,000원 할인)',
            value=st.session_state.get('use_coupon', False)
        )
    else:
        st.session_state['use_coupon'] = False
        st.markdown("<p style='color:gray;'>사용 가능한 쿠폰이 없습니다.</p>", unsafe_allow_html=True)

# --- 메뉴 추천 로직 ---
def recommend_menus(df, budget, selected_tags, recommendation_count=3):
    """예산, 태그를 고려하여 메인 세트 3개, 음료/베이커리 개별 추천"""

    # 1. 태그 필터링
    if selected_tags:
        filtered_df = df[df['tags_list'].apply(lambda x: any(tag in selected_tags for tag in x))]
    else:
        filtered_df = df
        
    # 2. 메뉴 카테고리 분리
    drink_categories = ['커피', '음료', '티']
    bakery_categories = ['빵', '디저트']
    main_categories = ['샌드위치', '샐러드']
    
    drink_df = filtered_df[filtered_df['category'].isin(drink_categories)]
    bakery_df = filtered_df[filtered_df['category'].isin(bakery_categories)]
    main_menu_df = filtered_df[filtered_df['category'].isin(main_categories)]
    
    # 3. 예산 안에서 가능한 조합 3세트 추천 (메인 + 베이커리)
    set_recommendations = []
    
    # 조합 추천 시도
    attempts = 0
    
    # 메인 + 베이커리 조합 추천이 불가능할 경우 단품만 추천하도록 로직을 유지
    if not main_menu_df.empty and not bakery_df.empty:
        while len(set_recommendations) < recommendation_count and attempts < 100:
            attempts += 1
            main_item = main_menu_df.sample(1).iloc[0]
            bakery_item = bakery_df.sample(1).iloc[0]
            total_price = main_item['price'] + bakery_item['price']
            
            if total_price <= budget:
                combo = (
                    f"**{main_item['name']}** + **{bakery_item['name']}** "
                    f"(총 {total_price}원)"
                )
                combo_name = combo.split('(')[0].strip()
                if not any(combo_name in rec for rec in set_recommendations):
                    set_recommendations.append(combo)

    # 조합이 부족하거나 불가능할 경우, 예산 내의 단품 메뉴 추가
    if len(set_recommendations) < recommendation_count:
        single_items = filtered_df[filtered_df['price'] <= budget].sort_values(by='price', ascending=False)
        for _, row in single_items.head(recommendation_count - len(set_recommendations)).iterrows():
            combo = f"**{row['name']}** (단품, {row['price']}원)"
            if not any(combo in rec for rec in set_recommendations):
                set_recommendations.append(combo)

    # 4. 음료와 베이커리는 따로 추천하기 위해 필터링된 데이터프레임 반환
    return set_recommendations, drink_df.sort_values(by='price', ascending=False), bakery_df.sort_values(by='price', ascending=False)


# --- 페이지: 홈 (전화번호 입력) ---
def home_page():
    st.title("☕ AI 메뉴 추천 키오스크")
    
    st.subheader("👋 환영합니다! 전화번호를 입력해주세요.")
    
    phone_input = st.text_input(
        "📱 휴대폰 번호 (예: 01012345678)", 
        max_chars=11, 
        key='phone_input_key'
    )
    
    if st.button("시작하기", type="primary"):
        if re.match(r'^\d{10,11}$', phone_input):
            st.session_state['phone_number'] = phone_input
            
            # DB 조회 또는 신규 등록
            if phone_input not in st.session_state['user_db']:
                st.session_state['user_db'][phone_input] = {'coupons': 0, 'visits': 1}
                st.success(f"🎉 신규 고객님으로 등록되었습니다!")
            else:
                st.session_state['user_db'][phone_input]['visits'] += 1
                st.info(f"✨ {phone_input} 고객님, 다시 오셨네요! 방문 횟수: {st.session_state['user_db'][phone_input]['visits']}회")
            
            set_page('recommend')
            st.rerun()
        else:
            st.error("유효하지 않은 전화번호 형식입니다. '-' 없이 10~11자리 숫자를 입력해주세요.")

# --- 페이지: 추천 설정 및 결과 ---
def recommend_page():
    st.title("🤖 AI 맞춤 메뉴 추천")
    
    show_coupon_status()
    
    # --- 1. 설정 섹션 ---
    st.subheader("1. 예산 설정, 쿠폰 및 해시태그")
    
    col1, col2 = st.columns(2)
    
    with col1:
        budget = st.slider(
            "💰 최대 예산 설정 (원)",
            min_value=5000, 
            max_value=30000, 
            step=1000, 
            value=15000
        )
    
    with col2:
        st.markdown("##### 🎫 쿠폰 사용")
        use_coupon_toggle()
        
    # 쿠폰 사용 시 예산 할인 적용
    final_budget = budget
    coupon_discount = 0
    if st.session_state.get('use_coupon'):
        coupon_discount = 1000 
        final_budget = budget + coupon_discount 
        st.info(f"쿠폰 사용으로 **{coupon_discount}원** 할인 적용! 추천은 최대 {final_budget}원 기준으로 진행됩니다.")
        
    st.markdown("---")
    
    st.markdown("##### 🏷️ 선호 해시태그 선택 (최대 3개)")
    selected_tags = st.multiselect(
        "원하는 메뉴 스타일을 선택하세요:",
        options=all_tags,
        max_selections=3,
        default=st.session_state.get('selected_tags', []),
        label_visibility="collapsed"
    )
    st.session_state['selected_tags'] = selected_tags

    # 추천 버튼
    if st.button("메뉴 추천 받기", type="primary"):
        set_recommendations, drink_df, bakery_df = recommend_menus(menu_df, final_budget, selected_tags, recommendation_count=3)
        
        st.session_state['recommendation_results']['set'] = set_recommendations
        st.session_state['recommendation_results']['drink'] = drink_df
        st.session_state['recommendation_results']['bakery'] = bakery_df
        st.session_state['recommended'] = True
        st.rerun()

    # --- 2. 추천 결과 섹션 (탭 분리) ---
    if st.session_state.get('recommended'):
        st.markdown("---")
        st.subheader("✨ 맞춤 추천 결과")
        
        set_tab, drink_tab, bakery_tab = st.tabs(["🎁 예산 내 세트 추천", "☕ 음료 추천", "🥐 베이커리 추천"])
        
        # 1. 세트 추천 탭
        with set_tab:
            sets = st.session_state['recommendation_results']['set']
            if sets:
                st.markdown("##### 예산 안에서 가능한 조합 3세트 (식사 + 베이커리)")
                for i, rec in enumerate(sets):
                    st.success(f"**세트 {i+1}**: {rec}")
            else:
                st.error("😭 선택하신 조건으로 추천 가능한 세트 조합이 없습니다. 예산 또는 해시태그를 조정해주세요.")
        
        # 2. 음료 추천 탭
        with drink_tab:
            drinks = st.session_state['recommendation_results']['drink']
            if not drinks.empty:
                st.markdown("##### 태그와 맞는 추천 음료")
                drink_list = drinks.head(5) # 상위 5개만 표시
                for _, row in drink_list.iterrows():
                    st.write(f"- **{row['name']}** ({row['price']}원) | 태그: {', '.join(row['tags_list'])}")
            else:
                st.markdown("*(선택한 태그에 맞는 음료가 없습니다. 태그를 조정해 보세요.)*")

        # 3. 베이커리 추천 탭
        with bakery_tab:
            bakery = st.session_state['recommendation_results']['bakery']
            if not bakery.empty:
                st.markdown("##### 태그와 맞는 추천 베이커리")
                bakery_list = bakery.head(5) # 상위 5개만 표시
                for _, row in bakery_list.iterrows():
                    st.write(f"- **{row['name']}** ({row['price']}원) | 태그: {', '.join(row['tags_list'])}")
            else:
                st.markdown("*(선택한 태그에 맞는 베이커리가 없습니다. 태그를 조정해 보세요.)*")
                
        # 주문 완료 버튼 (추천 결과가 있을 경우에만 표시)
        if st.session_state['recommendation_results']['set']:
            st.markdown("---")
            if st.button("🛒 주문 완료 및 쿠폰 발급", key='order_btn'):
                set_page('order_complete')
                st.rerun()

# --- 페이지: 주문 완료 ---
def order_complete_page():
    st.title("✅ 주문 완료")
    st.balloons()
    
    phone = st.session_state['phone_number']
    
    # 1. 쿠폰 사용 처리
    if st.session_state.get('use_coupon') and phone in st.session_state['user_db']:
        st.session_state['user_db'][phone]['coupons'] -= 1
        st.warning("🎫 쿠폰 1개가 사용되었습니다.")
        st.session_state['use_coupon'] = False
    
    # 2. 쿠폰 발급 (재방문 시 쿠폰함에 저장)
    if phone in st.session_state['user_db']:
        st.session_state['user_db'][phone]['coupons'] += 1
        st.success("🎁 주문 감사 쿠폰 1개가 발급되어 쿠폰함에 저장되었습니다!")
        st.info(f"현재 사용 가능 쿠폰: **{st.session_state['user_db'][phone]['coupons']}개**")
    
    st.markdown("---")
    if st.button("🏠 처음으로 돌아가기"):
        # 상태 초기화
        st.session_state['phone_number'] = None
        st.session_state['recommended'] = False
        st.session_state['recommendation_results'] = {'set': [], 'drink': pd.DataFrame(), 'bakery': pd.DataFrame()}
        st.session_state['use_coupon'] = False
        set_page('home')
        st.rerun()

# --- 메인 앱 로직 ---
def main():
    st.set_page_config(page_title="AI 메뉴 추천 키오스크", layout="centered")

    # 페이지 라우팅
    if st.session_state['page'] == 'home':
        home_page()
    elif st.session_state['page'] == 'recommend':
        # 데이터가 로드되지 않았다면 추천 페이지 진입 불가
        if not menu_df.empty:
            recommend_page()
        else:
            home_page() # 데이터 에러 시 홈으로 리디렉션
    elif st.session_state['page'] == 'order_complete':
        order_complete_page()

if __name__ == "__main__":
    if not menu_df.empty:
        main()
    else:
        # 데이터 로드 실패 시 에러 메시지가 load_data 함수에서 출력됨
        pass
