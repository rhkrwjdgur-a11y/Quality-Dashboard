# ==============================================================================
# [PART 1 / 4 - 상단 교체본] 엔터프라이즈 SaaS 화이트 UI 설정 & CSS (이모지·빨간버튼 완전 제거)
# ==============================================================================
import html
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import gspread
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from plotly.subplots import make_subplots

# ==============================================================================
# 1. 한국 표준시(KST, UTC+9) 고정 및 페이지·라우팅 기본 상태 설정
# ==============================================================================
KST_TZ = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST_TZ).replace(tzinfo=None)


st.set_page_config(
    page_title="YONSEI QUALITY ONE | 품질안전 통합 플랫폼",
    layout="wide",
    initial_sidebar_state="expanded"
)

BUNDLE_KEY = "kpi_ax_white_v4"

if "current_view" not in st.session_state:
    st.session_state.current_view = "main"


def set_view(view_name: str):
    st.session_state.current_view = view_name


def jump_to_lot_trace(prod_kw: str = "", exp_str: str = ""):
    st.session_state["lot_sel_prod"] = "전체 (제품 미선택 · 소비기한으로만 검색)"
    st.session_state["lot_in_kw"] = str(prod_kw or "").strip()
    st.session_state["lot_in_exp"] = str(exp_str or "").strip()
    st.session_state.current_view = "lot_trace"


def on_global_quick_search():
    q = st.session_state.get("global_top_search", "").strip()
    if not q:
        return
    st.session_state["lot_sel_prod"] = "전체 (제품 미선택 · 소비기한으로만 검색)"
    if re.search(r"\d{1,4}[\.\-/]\d{1,2}", q):
        st.session_state["lot_in_exp"] = q
        st.session_state["lot_in_kw"] = ""
    else:
        st.session_state["lot_in_kw"] = q
        st.session_state["lot_in_exp"] = ""
    st.session_state["global_top_search"] = ""
    st.session_state.current_view = "lot_trace"


# 좌측 사이드바 메뉴 (만화풍 컬러 이모지 완전 제거 · 엔터프라이즈 텍스트 네비게이션)
SIDEBAR_MENU_GROUPS = [
    {
        "group_title": "품질안전부문 (통합)",
        "items": [
            ("main", "통합 대시보드"),
            ("dept_kpi8", "2026 부문 8대 KPI")
        ]
    },
    {
        "group_title": "식품안전팀 (QA)",
        "items": [
            ("label_status", "표시사항 진행 현황"),
            ("label_issue", "원자재 표시사항 DB"),
            ("kpi_5", "심사점수 · 일정 관리"),
            ("supplier", "협력업체 서류심사"),
            ("fs_haccp_risk", "HACCP · 법적 RISK")
        ]
    },
    {
        "group_title": "품질관리팀 (QC)",
        "items": [
            ("process", "공정 및 배양 실시간 관제"),
            ("lot_trace", "생산이력 · LOT 역추적"),
            ("claim", "클레임 발생률 분석"),
            ("qc_defect_sub", "핵심불량 · 부자재 관리")
        ]
    }
]

AUDIT_STATUS_LIST = ["심사준비중", "심사중", "서류심사중", "현장심사중", "심사종료"]
AUDIT_STATUS_CONFIG = {
    "심사준비중": {"pct": 20, "color": "#64748B", "bg": "#F1F5F9", "fg": "#334155", "icon": ""},
    "심사중": {"pct": 50, "color": "#0284C7", "bg": "#E0F2FE", "fg": "#0369A1", "icon": ""},
    "서류심사중": {"pct": 75, "color": "#2563EB", "bg": "#DBEAFE", "fg": "#1D4ED8", "icon": ""},
    "현장심사중": {"pct": 85, "color": "#D97706", "bg": "#FEF3C7", "fg": "#92400E", "icon": ""},
    "심사종료": {"pct": 100, "color": "#10B981", "bg": "#DCFCE7", "fg": "#166534", "icon": ""}
}

DEFAULT_MANUAL_KPIS = {
    "kpi_8": {
        "no": "3",
        "title": "3. 식품안전 및 HACCP 강화",
        "short_title": "3. HACCP 강화",
        "target_text": "11건 이상",
        "actual_text": "11건, 100% 달성",
        "compact_val": "11건",
        "sub_badge": "목표 100% 달성 완료",
        "target_num": 11.0,
        "actual_num": 11.0,
        "suffix": "",
        "unit_label": "(단위 : 건)",
        "signal": "green",
        "has_chart": True,
        "notes_title": "식품안전 및 HACCP 강화 추진 실적",
        "notes": [
            "연간 식품안전 및 HACCP 유효성 검증·개선 과제 11건 이행 완료",
            "현장 작업자 정기 위생·CCP 교육 및 검증 프로세스 고도화"
        ]
    },
    "kpi_9": {
        "no": "4",
        "title": "4. 핵심불량(클레임) 발생 저감화",
        "short_title": "4. 핵심불량 저감",
        "target_text": "38건 이하",
        "actual_text": "5건",
        "compact_val": "5건",
        "sub_badge": "목표(38건 이하) 대비 안정 관리",
        "target_num": 38.0,
        "actual_num": 5.0,
        "suffix": "",
        "unit_label": "(단위 : 건)",
        "signal": "green",
        "has_chart": True,
        "notes_title": "핵심불량(클레임) 중점 저감 내역",
        "notes": [
            "연간 허용 한도(38건 이하) 대비 현재 누적 5건으로 안정적 관리 중",
            "설비 접착·이물·파손 등 핵심 중대 불량 요인 사전 예방 점검"
        ]
    },
    "kpi_10": {
        "no": "5",
        "title": "5. 부자재 관리 고도화",
        "short_title": "5. 부자재 관리",
        "target_text": "부자재폐기 0건",
        "actual_text": "0건",
        "compact_val": "0건",
        "sub_badge": "부자재 폐기 0건 유지",
        "target_num": 0.0,
        "actual_num": 0.0,
        "suffix": "건",
        "unit_label": "(단위 : 건)",
        "signal": "green",
        "has_chart": False,
        "notes_title": "부자재 폐기 Zero화 관리 내역",
        "notes": [
            "표시사항 사전 심의 및 법규 개정 선제 반영으로 부자재 오인쇄·폐기 0건 유지",
            "포장재 발주 전 표시사항 더블체크 프로세스 상시 가동"
        ]
    },
    "kpi_11": {
        "no": "6",
        "title": "6. 협력업체 관리강화",
        "short_title": "6. 협력업체 관리",
        "target_text": "실행률 88.3% 이상",
        "actual_text": "77.9%",
        "compact_val": "77.9%",
        "sub_badge": "목표 88.3% 대비 집중 관리 중",
        "target_num": 88.3,
        "actual_num": 77.9,
        "suffix": "%",
        "unit_label": "(단위 : %)",
        "signal": "red",
        "has_chart": True,
        "notes_title": "협력업체 현장·서류 관리강화 내역",
        "notes": [
            "연간 협력업체 정기 서류·현장심사 및 개선조치 실행률 점검 진행",
            "등급 외 및 미제출 업체 대상 집중 피드백 및 보완 점검"
        ]
    },
    "kpi_5": {
        "no": "7",
        "title": "7. 심사점수",
        "short_title": "7. 심사점수",
        "target_text": "94.28점 이상",
        "actual_text": "91.56점",
        "compact_val": "91.56점",
        "sub_badge": "목표 대비 -2.72점",
        "target_num": 94.28,
        "actual_num": 91.56,
        "suffix": "",
        "unit_label": "(단위 : 점)",
        "signal": "red",
        "has_chart": True,
        "notes_title": "심사점수 주요 관리 내역",
        "notes": [
            "정기 위생·품질 심사 결과 집계 및 미비점 개선 조치 진행",
            "현장 CCP 모니터링 및 중점 위생관리 항목 상시 점검"
        ]
    },
    "kpi_12": {
        "no": "8",
        "title": "8. 식품안전 법적 RISK 최소화",
        "short_title": "8. 법적 RISK",
        "target_text": "행정처분 0건",
        "actual_text": "0건",
        "compact_val": "0건",
        "sub_badge": "행정처분 0건 · 중요건 조사 대응",
        "target_num": 0.0,
        "actual_num": 0.0,
        "suffix": "건",
        "unit_label": "(단위 : 건)",
        "signal": "green",
        "has_chart": False,
        "notes_title": "중요건 행정기관 조사 3건 대응",
        "notes": [
            "카톤발효유 : 3월",
            "락토프리(명가) : 6월",
            "호상발효유 : 10월"
        ]
    }
}

DEFAULT_LABEL_MEMO = (
    "원재료 변경 품목 전성분 및 알레르기 유발물질 표시 교차 점검 진행\n"
    "표시사항 신규·변경 의뢰 건 부자재 발주 전 최종 확인필 여부 상시 체크"
)

DEFAULT_CLAIM_ISSUES = [
    {"구분": "클레임추적", "특이사항": "주요 클레임 접수 품목 생산·멸균·배양 이력 점검", "상태": "확인 필요", "제품키워드": "", "소비기한": ""},
    {"구분": "공정·부적합", "특이사항": "카톤·멸균팩 상하부 접착 및 표시사항 인쇄 상태 집중 모니터링", "상태": "진행 중", "제품키워드": "", "소비기한": ""}
]

if "manual_kpis" not in st.session_state:
    st.session_state["manual_kpis"] = {k: {**v, "notes": list(v["notes"])} for k, v in DEFAULT_MANUAL_KPIS.items()}
if "label_special_memo" not in st.session_state:
    st.session_state["label_special_memo"] = DEFAULT_LABEL_MEMO
if "claim_special_list" not in st.session_state:
    st.session_state["claim_special_list"] = [dict(x) for x in DEFAULT_CLAIM_ISSUES]

FISCAL_MONTHS = ["3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월", "1월", "2월"]
DAIRY_CATEGORIES = ["냉장우유 카톤팩", "냉장우유 병", "발효유/음료 카톤팩", "발효유/음료 병"]
RT_CATEGORIES = ["상온 멸균팩", "상온 프리즈마"]

SHEET_NAMES = {
    "cost": "원가절감 현황",
    "claim": "클레임 건수",
    "supplier": "협력업체 심사 결과 DB",
    "audit_db": "심사점수 및 일정 관리 DB",
    "label_status": "표시사항 현황",
    "raw_label_db": "원자재 표시사항 DB",
    "process_soy": "[상온]두유 배양검사 일보",
    "process_rt": "[상온]상온제품 공정 관리 일보",
    "process_milk": "[우유] 유제품 포장 공정관리 일보"
}

HIST_TABS = {
    "dairy_prod": "_이력DB_유제품포장",
    "dairy_ccp": "_이력DB_유제품공정CCP",
    "rt_prod": "_이력DB_상온생산",
    "rt_ccp": "_이력DB_상온CCP",
    "soy_inc": "_이력DB_두유배양"
}

# ==============================================================================
# 2. 엔터프라이즈 B2B SaaS 디자인 시스템 CSS (QUALITY ONE 레퍼런스 정밀 반영)
# ==============================================================================
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    :root {
        --primary-color: #2563EB !important;
    }
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Malgun Gothic', sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }
    .stApp {
        background-color: #F7F8FA !important;
        color: #111827 !important;
    }

    /* Streamlit 기본 상단 우측 메뉴/장식 숨김 -> 순수 업무용 웹솔루션 외형 */
    #MainMenu, footer { visibility: hidden; }
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        height: 1.8rem !important;
    }
    div[data-testid="stMainBlockContainer"],
    div[data-testid="stAppViewBlockContainer"],
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 2.0rem !important;
        padding-left: 2.0rem !important;
        padding-right: 2.0rem !important;
        max-width: 100% !important;
    }

    /* ------------------------------------------------------------------ */
    /* 좌측 사이드바 : QUALITY ONE 스타일 (화이트 배경 + 소프트 블루 활성탭) */
    /* ------------------------------------------------------------------ */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #EAECF0 !important;
        min-width: 236px !important;
        max-width: 248px !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
        padding: 1.1rem 0.9rem !important;
    }
    .qo-brand-wrap {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 4px 6px 16px 6px;
        border-bottom: 1px solid #F2F4F7;
        margin-bottom: 12px;
    }
    .qo-logo-mark {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        background: linear-gradient(135deg, #1D4ED8 0%, #2563EB 100%);
        color: #FFFFFF;
        font-weight: 900;
        font-size: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        letter-spacing: -0.5px;
        box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25);
        flex-shrink: 0;
    }
    .qo-brand-name {
        font-size: 14.5px;
        font-weight: 800;
        color: #111827;
        letter-spacing: -0.3px;
        line-height: 1.2;
    }
    .qo-brand-sub {
        font-size: 10.8px;
        font-weight: 500;
        color: #6B7280;
        margin-top: 2px;
    }
    .sb-group-hdr {
        font-size: 11px;
        font-weight: 700;
        color: #9CA3AF;
        padding: 12px 10px 4px 10px;
        letter-spacing: -0.1px;
    }

    /* 사이드바 모든 버튼 공통 초기화 후 활성/비활성 분리 */
    section[data-testid="stSidebar"] button {
        width: 100% !important;
        text-align: left !important;
        justify-content: flex-start !important;
        border-radius: 8px !important;
        padding: 7px 12px !important;
        min-height: 36px !important;
        margin-bottom: 1px !important;
        box-shadow: none !important;
        transition: background-color 0.14s ease, color 0.14s ease !important;
    }
    section[data-testid="stSidebar"] button div[data-testid="stMarkdownContainer"] p {
        font-size: 13.2px !important;
        margin: 0 !important;
    }
    /* 사이드바 활성 메뉴 (연한 파스텔 블루 박스 + 블루 텍스트, 빨간색 완전 차단) */
    section[data-testid="stSidebar"] button[kind="primary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"],
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
        background-color: #EFF6FF !important;
        color: #1D4ED8 !important;
        border: 1px solid #DBEAFE !important;
        font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"] div[data-testid="stMarkdownContainer"] p {
        color: #1D4ED8 !important;
        font-weight: 700 !important;
    }
    /* 사이드바 비활성 메뉴 (테두리 없음) */
    section[data-testid="stSidebar"] button[kind="secondary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"],
    section[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {
        background-color: transparent !important;
        color: #4B5563 !important;
        border: 1px solid transparent !important;
        font-weight: 500 !important;
    }
    section[data-testid="stSidebar"] button[kind="secondary"]:hover,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {
        background-color: #F3F4F6 !important;
        color: #111827 !important;
    }

    /* ------------------------------------------------------------------ */
    /* 메인 영역 모든 버튼 : 빨간색 원천 봉쇄 & 슬림 엔터프라이즈 텍스트 버튼 */
    /* ------------------------------------------------------------------ */
    div[data-testid="stMain"] button[kind="primary"],
    div[data-testid="stMain"] button[data-testid="stBaseButton-primary"],
    div[data-testid="stMain"] button[data-testid="baseButton-primary"],
    .main button[kind="primary"] {
        background-color: #1D4ED8 !important;
        color: #FFFFFF !important;
        border: 1px solid #1D4ED8 !important;
        border-radius: 7px !important;
        font-size: 12.8px !important;
        font-weight: 600 !important;
        padding: 5px 12px !important;
        min-height: 32px !important;
        box-shadow: none !important;
    }
    div[data-testid="stMain"] button[kind="secondary"],
    div[data-testid="stMain"] button[data-testid="stBaseButton-secondary"],
    div[data-testid="stMain"] button[data-testid="baseButton-secondary"],
    .main button[kind="secondary"] {
        background-color: #F9FAFB !important;
        color: #4B5563 !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 6px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        padding: 3px 10px !important;
        min-height: 28px !important;
        box-shadow: none !important;
        transition: all 0.14s ease !important;
    }
    div[data-testid="stMain"] button[kind="secondary"]:hover,
    div[data-testid="stMain"] button[data-testid="stBaseButton-secondary"]:hover {
        background-color: #EFF6FF !important;
        color: #1D4ED8 !important;
        border-color: #BFDBFE !important;
    }

    /* 상단 검색창 (QUALITY ONE 상단 검색바 스타일) */
    div[data-testid="stTextInput"] div[data-baseweb="input"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 8px !important;
        min-height: 36px !important;
        font-size: 13px !important;
    }
    div[data-testid="stPopover"] > div > button {
        background-color: #F9FAFB !important;
        color: #374151 !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 7px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        min-height: 30px !important;
        padding: 3px 10px !important;
    }

    /* ------------------------------------------------------------------ */
    /* 상단 글로벌 바 & 히어로 헤더 (QUALITY ONE 스타일)                    */
    /* ------------------------------------------------------------------ */
    .qo-hero-wrap {
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        padding: 6px 2px 14px 2px;
        margin-bottom: 6px;
    }
    .qo-hero-title {
        font-size: 20px;
        font-weight: 800;
        color: #111827;
        letter-spacing: -0.4px;
        border-left: 3.5px solid #2563EB;
        padding-left: 10px;
        line-height: 1.25;
    }
    .qo-hero-sub {
        font-size: 12.3px;
        color: #6B7280;
        margin-top: 4px;
        padding-left: 13px;
        font-weight: 500;
    }
    .live-status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background-color: #ECFDF5;
        color: #059669;
        border: 1px solid #A7F3D0;
        padding: 4px 11px;
        border-radius: 999px;
        font-size: 11.8px;
        font-weight: 600;
    }
    .live-dot-green {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background-color: #10B981;
        display: inline-block;
    }

    .yonsei-header-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #E5E7EB;
        padding: 4px 0 12px 0;
        margin-bottom: 16px;
    }
    .yonsei-title {
        font-size: 19.5px;
        font-weight: 800;
        color: #111827;
        letter-spacing: -0.4px;
        border-left: 3.5px solid #2563EB;
        padding-left: 10px;
    }

    /* ------------------------------------------------------------------ */
    /* 화이트 카드 컨테이너 & 카드 내부 헤더                                */
    /* ------------------------------------------------------------------ */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border: 1px solid #EAECF0 !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(16, 24, 40, 0.04) !important;
        padding: 14px 16px !important;
        margin-bottom: 10px;
    }
    .qo-card-title {
        font-size: 14.5px;
        font-weight: 700;
        color: #111827;
        letter-spacing: -0.2px;
        padding-top: 3px;
    }
    .qo-card-caption {
        font-size: 11.8px;
        color: #6B7280;
        font-weight: 500;
    }
    .qo-divider {
        height: 1px;
        background-color: #F2F4F7;
        margin: 8px 0 10px 0;
    }

    /* 리스트 행 & 상태 배지 (채도 낮춘 엔터프라이즈 파스텔 배지) */
    .qo-list-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 4px;
        border-bottom: 1px solid #F2F4F7;
        font-size: 13px;
    }
    .qo-list-row:last-child { border-bottom: none; }
    .qo-row-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        flex-shrink: 0;
    }
    .dot-green { background-color: #10B981; }
    .dot-amber { background-color: #F59E0B; }
    .dot-red { background-color: #EF4444; }
    .dot-blue { background-color: #2563EB; }

    .badge-pill {
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 11.3px;
        font-weight: 600;
        white-space: nowrap;
    }
    .badge-ok { background-color: #ECFDF5; color: #047857; }
    .badge-warn { background-color: #FFFBEB; color: #B45309; }
    .badge-err { background-color: #FEF2F2; color: #DC2626; }
    .badge-info { background-color: #EFF6FF; color: #1D4ED8; }
    .badge-neutral { background-color: #F3F4F6; color: #4B5563; }

    .qo-scroll-area {
        max-height: 148px;
        min-height: 148px;
        overflow-y: auto;
        padding-right: 4px;
    }
    .qo-sub-box {
        background-color: #F9FAFB;
        border: 1px solid #EAECF0;
        border-radius: 8px;
        padding: 9px 12px;
        min-height: 86px;
        max-height: 98px;
        overflow-y: auto;
        font-size: 12.4px;
        line-height: 1.55;
        color: #374151;
        margin-top: 6px;
    }

    /* 슬림 진행률 게이지 바 (온도계 이모지 제거 -> 모던 프로그레스 바) */
    .qo-prog-banner {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 8px 11px;
        font-size: 12.5px;
        font-weight: 600;
        color: #1E293B;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .qo-prog-track {
        width: 100%;
        height: 8px;
        background-color: #EAECF0;
        border-radius: 999px;
        overflow: hidden;
        margin: 8px 0 5px 0;
    }
    .qo-prog-fill {
        height: 100%;
        border-radius: 999px;
        transition: width 0.3s ease;
    }
    .qo-prog-steps {
        display: flex;
        justify-content: space-between;
        font-size: 10.8px;
        color: #9CA3AF;
        font-weight: 500;
        margin-bottom: 8px;
    }

    /* 우측 하단 8대 KPI 스코어카드 (QUALITY ONE 상단 숫자 카드 스타일) */
    .qo-kpi-num {
        font-size: 22px;
        font-weight: 800;
        color: #111827;
        letter-spacing: -0.5px;
        line-height: 1.2;
        margin: 2px 0 4px 0;
    }
    .qo-kpi-target {
        font-size: 11.5px;
        color: #6B7280;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 5px;
    }

    .signal-dot {
        height: 9px;
        width: 9px;
        border-radius: 50%;
        display: inline-block;
    }
    .signal-green { background-color: #10B981; }
    .signal-yellow { background-color: #F59E0B; }
    .signal-red { background-color: #EF4444; }
    .signal-gray { background-color: #9CA3AF; }

    /* 세부 페이지 공통 요소 */
    .kpi-meta-wrap {
        position: relative;
        min-height: 80px;
        padding: 4px 2px;
        font-size: 13.2px;
        color: #374151;
        line-height: 1.65;
    }
    .kpi-dot-bullet { color: #2563EB; font-weight: 700; margin-right: 5px; }
    .kpi-sub-pill {
        display: inline-block;
        margin-top: 4px;
        padding: 2px 8px;
        font-size: 11.3px;
        font-weight: 600;
        color: #1D4ED8;
        background-color: #EFF6FF;
        border-radius: 6px;
    }
    .card-scroll-box {
        background-color: #F9FAFB;
        border: 1px solid #EAECF0;
        border-radius: 8px;
        padding: 9px 11px;
        height: 146px;
        overflow-y: auto;
        margin-top: 4px;
        font-size: 12.4px;
        line-height: 1.55;
    }
    .forecast-box {
        background-color: #FFFFFF;
        border: 1px solid #EAECF0;
        border-left: 3.5px solid #2563EB;
        padding: 13px 16px;
        border-radius: 8px;
        margin-bottom: 14px;
        font-size: 13.4px;
        line-height: 1.62;
        color: #1F2937;
    }
    .trace-hero-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #2563EB;
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 14px;
        color: #1F2937;
        font-size: 13.4px;
        line-height: 1.6;
    }
    .issue-card-ok {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-left: 3.5px solid #10B981;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 12px;
        font-size: 13px;
        color: #065F46;
    }
    .issue-card-warn {
        background-color: #FFFBEB;
        border: 1px solid #FDE68A;
        border-left: 3.5px solid #F59E0B;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 12px;
        font-size: 13px;
        color: #92400E;
    }

    /* 관제 테이블 (차분한 엔터프라이즈 그리드 헤더) */
    .mon-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 12.6px;
        margin-bottom: 14px;
        background-color: #FFFFFF;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #EAECF0;
    }
    .mon-table th {
        background-color: #F9FAFB;
        color: #374151;
        font-weight: 700;
        padding: 9px 8px;
        border-bottom: 1px solid #EAECF0;
        text-align: center;
        word-break: keep-all;
    }
    .mon-table td {
        padding: 8px 8px;
        border-bottom: 1px solid #F2F4F7;
        vertical-align: middle;
        word-break: keep-all;
        overflow-wrap: break-word;
        line-height: 1.45;
        color: #1F2937;
    }
    .mon-table tr:hover td { background-color: #F9FAFB; }
    .td-center { text-align: center; }
    .td-left { text-align: left; }
    .cell-green { background-color: #ECFDF5 !important; color: #047857 !important; font-weight: 600; }
    .cell-yellow { background-color: #FFFBEB !important; color: #B45309 !important; font-weight: 600; }
    .cell-red { background-color: #FEF2F2 !important; color: #DC2626 !important; font-weight: 600; }
    .cell-gray { background-color: #F9FAFB !important; color: #9CA3AF !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. Google 인증 · 429 재시도 · 로트 역추적 정규화 · HTML 테이블 유틸리티
# ==============================================================================
def api_call_with_retry(func, *args, **kwargs):
    for attempt in range(4):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "Quota exceeded" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                time.sleep(2.5 * (attempt + 1))
                continue
            raise
    return func(*args, **kwargs)


def build_google_credentials():
    if "google_oauth" in st.secrets:
        try:
            oauth_info = st.secrets["google_oauth"]
            creds = OAuthCredentials(
                token=None,
                refresh_token=oauth_info["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=oauth_info["client_id"],
                client_secret=oauth_info["client_secret"]
            )
            creds.refresh(Request())
            return creds, None
        except Exception as e:
            return None, f"Google OAuth 인증 실패: {e}"

    if "gcp_service_account" in st.secrets:
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = ServiceAccountCredentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes
            )
            return creds, None
        except Exception as e:
            return None, f"Service Account 인증 실패: {e}"

    return None, "Streamlit Secrets에 [google_oauth] 또는 [gcp_service_account] 설정이 없습니다."


def open_sheet_threadsafe(creds, sheet_urls_map: dict, key_or_title: str):
    if creds is None:
        return None, "인증 자격증명이 없습니다."

    client = gspread.authorize(creds)
    errors = []

    if key_or_title in sheet_urls_map:
        url_val = str(sheet_urls_map[key_or_title]).strip()
        if url_val:
            try:
                if url_val.startswith("http"):
                    return api_call_with_retry(client.open_by_url, url_val), None
                return api_call_with_retry(client.open_by_key, url_val), None
            except Exception as e:
                errors.append(f"URL/ID 열기 실패({key_or_title}): {e}")

    target_title = SHEET_NAMES.get(key_or_title, key_or_title)
    for candidate in [target_title, target_title.strip(), target_title.strip() + " "]:
        try:
            return api_call_with_retry(client.open, candidate), None
        except Exception as e:
            errors.append(f"파일명 '{candidate}' 열기 실패: {e}")

    return None, " / ".join(errors)


def get_values_unformatted(ws):
    try:
        return api_call_with_retry(ws.get_all_values, value_render_option="UNFORMATTED_VALUE")
    except Exception:
        return api_call_with_retry(ws.get_all_values)


def get_values_formatted(ws):
    return api_call_with_retry(ws.get_all_values)


def safe_ws_update(ws, payload: list):
    try:
        api_call_with_retry(ws.update, values=payload, range_name="A1", value_input_option="USER_ENTERED")
    except TypeError:
        api_call_with_retry(ws.update, "A1", payload, value_input_option="USER_ENTERED")


def rows_to_df(rows: list) -> pd.DataFrame:
    if not rows or len(rows) < 2:
        return pd.DataFrame()
    hdr = [str(h).strip() for h in rows[0]]
    data = []
    for r in rows[1:]:
        if not any(str(x).strip() != "" for x in r):
            continue
        r_pad = [str(x).strip() for x in r] + [""] * max(0, len(hdr) - len(r))
        data.append(dict(zip(hdr, r_pad[:len(hdr)])))
    return pd.DataFrame(data)


def to_float(val, default=0.0):
    if val is None or pd.isna(val):
        return default
    s = str(val).strip()
    if s in ["", "-", "nan", "None", "#######"]:
        return default
    try:
        cleaned = re.sub(r"[^\d.-]", "", s)
        return float(cleaned) if cleaned not in ["", "-", "."] else default
    except Exception:
        return default


def normalize_comp_name(name, core_only=False):
    if not name:
        return ""
    s = str(name).strip()
    if core_only:
        s = re.sub(r"\([^)]*\)", "", s)
        s = s.split("_")[0]
    for token in ["농업회사법인", "주식회사", "유한회사", "(주)", "㈜", "(유)", "(법인)", " ", "_", "\n", "\t", ","]:
        s = s.replace(token, "")
    s = s.replace("롯데웰푸드", "롯데푸드")
    return s.strip()


def clean_product_for_match(name: str) -> str:
    if not name:
        return ""
    s = str(name).strip()
    s = re.sub(r"\(\s*\d+(?:\.\d+)?\s*(?:mL|ml|ML|㎖|L|g|kg)\s*\)", "", s)
    s = re.sub(r"(?<!\d)\d{2,4}\s*(?:mL|ml|ML|㎖)(?!\w)", "", s)
    s = re.sub(r"\s+1[0127]\d{3}\b", "", s)
    s = re.sub(r"[\s\(\)\[\]\{\}\-_·,/&\+!]+", "", s).lower()
    return s


def is_product_match(record_prod: str, selected_prod: str, kw_text: str = "") -> bool:
    rec_raw = str(record_prod or "").strip()
    if not rec_raw or rec_raw == "-":
        return False

    rec_parts = [p.strip() for p in rec_raw.split("/") if p.strip()]
    rec_cleans = [clean_product_for_match(p) for p in rec_parts] + [clean_product_for_match(rec_raw)]

    if selected_prod and selected_prod != "전체 (제품 미선택 · 소비기한으로만 검색)":
        sel_clean = clean_product_for_match(selected_prod)
        if not sel_clean:
            return False
        matched_sel = False
        for rc in rec_cleans:
            if not rc:
                continue
            if sel_clean == rc or (len(sel_clean) >= 2 and sel_clean in rc) or (len(rc) >= 3 and rc in sel_clean):
                matched_sel = True
                break
        if not matched_sel:
            return False

    if kw_text and kw_text.strip():
        kw_clean = clean_product_for_match(kw_text)
        kw_raw_low = kw_text.strip().lower()
        if kw_clean:
            if not any(kw_clean in rc for rc in rec_cleans if rc) and (kw_raw_low not in rec_raw.lower()):
                return False

    return True


def parse_exp_query_info(exp_input: str) -> dict:
    s = str(exp_input or "").strip()
    if not s:
        return {"empty": True}

    m_full = re.search(r"(20\d{2})\D+(\d{1,2})\D+(\d{1,2})", s)
    if m_full:
        yr, mm, dd = int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3))
        return {
            "empty": False,
            "iso_full": f"{yr:04d}-{mm:02d}-{dd:02d}",
            "mm_dd_dash": f"{mm:02d}-{dd:02d}",
            "mm_dd_dot": f"{mm:02d}.{dd:02d}",
            "m_d_dot": f"{mm}.{dd}",
            "raw": s
        }

    m_two = re.search(r"^(\d{2})\D+(\d{1,2})\D+(\d{1,2})$", s)
    if m_two:
        yr, mm, dd = 2000 + int(m_two.group(1)), int(m_two.group(2)), int(m_two.group(3))
        return {
            "empty": False,
            "iso_full": f"{yr:04d}-{mm:02d}-{dd:02d}",
            "mm_dd_dash": f"{mm:02d}-{dd:02d}",
            "mm_dd_dot": f"{mm:02d}.{dd:02d}",
            "m_d_dot": f"{mm}.{dd}",
            "raw": s
        }

    m_short = re.search(r"^(\d{1,2})\D+(\d{1,2})$", s)
    if m_short:
        mm, dd = int(m_short.group(1)), int(m_short.group(2))
        return {
            "empty": False,
            "iso_full": "",
            "mm_dd_dash": f"{mm:02d}-{dd:02d}",
            "mm_dd_dot": f"{mm:02d}.{dd:02d}",
            "m_d_dot": f"{mm}.{dd}",
            "raw": s
        }

    return {"empty": False, "iso_full": "", "mm_dd_dash": "", "mm_dd_dot": "", "m_d_dot": "", "raw": s}


def is_exp_match(raw_exp: str, iso_exp: str, q_info: dict) -> bool:
    if q_info.get("empty", True):
        return True

    raw_s = re.sub(r"\s+", "", str(raw_exp or ""))
    iso_s = re.sub(r"\s+", "", str(iso_exp or ""))

    if q_info.get("iso_full"):
        if q_info["iso_full"] in iso_s:
            return True
        yr_2 = q_info["iso_full"][2:4]
        mm_dd_dot = q_info["mm_dd_dot"]
        if f"{q_info['iso_full'][:4]}.{mm_dd_dot}" in raw_s or f"{yr_2}.{mm_dd_dot}" in raw_s:
            return True
        return False

    if q_info.get("mm_dd_dash"):
        if iso_s and any(tok.endswith(q_info["mm_dd_dash"]) for tok in iso_s.split(",")):
            return True
        if q_info["mm_dd_dot"] in raw_s or q_info["m_d_dot"] in raw_s:
            return True
        return False

    q_raw = re.sub(r"\s+", "", q_info.get("raw", ""))
    return (q_raw in raw_s) or (q_raw in iso_s)


def get_signal_dot_html(status_code: str) -> str:
    if status_code == "red":
        return '<div class="signal-dot signal-red" title="경고"></div>'
    if status_code == "yellow":
        return '<div class="signal-dot signal-yellow" title="주의"></div>'
    if status_code == "gray":
        return '<div class="signal-dot signal-gray" title="대기"></div>'
    return '<div class="signal-dot signal-green" title="양호"></div>'


def calc_trend_and_forecast_split(y_values: list, is_recorded_list: list = None, total_periods: int = 12):
    if is_recorded_list is not None:
        valid_idx = [i for i, flag in enumerate(is_recorded_list) if flag]
    else:
        valid_idx = [i for i, v in enumerate(y_values) if v > 0]

    valid_y = [float(y_values[i]) for i in valid_idx]

    if len(valid_idx) >= 2:
        slope, intercept = np.polyfit(valid_idx, valid_y, 1)
        full_line = [round(max(float(slope * i + intercept), 0.0), 2) for i in range(total_periods)]
    elif len(valid_idx) == 1:
        slope = 0.0
        full_line = [round(valid_y[0], 2)] * total_periods
    else:
        return [None] * total_periods, [None] * total_periods, [0.0] * total_periods, 0.0, 0, -1

    last_idx = max(valid_idx)
    actual_line = [full_line[i] if i <= last_idx else None for i in range(total_periods)]
    forecast_line = [full_line[i] if i >= last_idx else None for i in range(total_periods)]

    return actual_line, forecast_line, full_line, round(float(slope), 4), len(valid_idx), last_idx


def render_html_table(columns_spec: list, rows_data: list) -> str:
    if not rows_data:
        return "<div style='padding:10px; color:#64748B; background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px;'>기록된 데이터가 없습니다.</div>"

    colgroup = "".join([f"<col style='width:{c.get('width', 'auto')};'>" for c in columns_spec])
    thead = "".join([f"<th>{html.escape(str(c['label']))}</th>" for c in columns_spec])

    tbody_rows = []
    for row in rows_data:
        tds = []
        for c in columns_spec:
            k = c["key"]
            align_cls = "td-left" if c.get("align") == "left" else "td-center"
            cell_obj = row.get(k, {"text": "-", "cls": ""})
            if isinstance(cell_obj, dict):
                raw_txt = str(cell_obj.get("text", "-"))
                c_cls = cell_obj.get("cls", "")
            else:
                raw_txt = str(cell_obj)
                c_cls = ""
            safe_txt = html.escape(raw_txt).replace("\n", "<br>")
            tds.append(f"<td class='{align_cls} {c_cls}'>{safe_txt}</td>")
        tbody_rows.append(f"<tr>{''.join(tds)}</tr>")

    return f"""
    <table class="mon-table">
        <colgroup>{colgroup}</colgroup>
        <thead><tr>{thead}</tr></thead>
        <tbody>{''.join(tbody_rows)}</tbody>
    </table>
    """


# ==============================================================================
# 4. [1] 원가절감 현황 & [2] 클레임 건수 시트 파서
# ==============================================================================
def fetch_cost_sheet(creds, sheet_urls_map):
    sh, err = open_sheet_threadsafe(creds, sheet_urls_map, "cost")
    default_targets = {"부문": 1.54, "식품안전팀": 1.0, "품질관리팀": 0.54}
    if sh is None:
        return pd.DataFrame(), default_targets, err

    try:
        ws = api_call_with_retry(sh.get_worksheet, 0)
        rows = get_values_unformatted(ws)
        targets = default_targets.copy()

        if len(rows) >= 1:
            r0_join = " ".join([str(x) for x in rows[0]])
            nums_uk = re.findall(r"(\d+(?:\.\d+)?)\s*억", r0_join)
            if len(nums_uk) >= 3:
                targets = {
                    "부문": float(nums_uk[0]),
                    "식품안전팀": float(nums_uk[1]),
                    "품질관리팀": float(nums_uk[2])
                }

        hdr_row_idx = 1
        for idx, r in enumerate(rows[:5]):
            if sum(1 for c in r if re.sub(r"\s+", "", str(c)) == "원가절감") >= 2:
                hdr_row_idx = idx
                break

        hdr_cells = [re.sub(r"\s+", "", str(c)) for c in rows[hdr_row_idx]]
        act_cols = [i for i, h in enumerate(hdr_cells) if h == "원가절감"]
        if len(act_cols) < 3:
            act_cols = [1, 6, 11]

        b_c, fs_c, qc_c = act_cols[0], act_cols[1], act_cols[2]

        parsed = []
        for r in rows[hdr_row_idx + 1:]:
            r_pad = list(r) + [""] * max(0, qc_c + 4 - len(r))
            m_name = str(r_pad[max(0, b_c - 1)]).strip()
            if m_name in FISCAL_MONTHS:
                b_act = round(to_float(r_pad[b_c]), 1)
                b_tar = round(to_float(r_pad[b_c + 1]), 1)
                fs_act = round(to_float(r_pad[fs_c]), 1)
                fs_tar = round(to_float(r_pad[fs_c + 1]), 1)
                qc_act = round(to_float(r_pad[qc_c]), 1)
                qc_tar = round(to_float(r_pad[qc_c + 1]), 1)

                is_rec = (b_act > 0) or (fs_act > 0) or (qc_act > 0)
                parsed.append({
                    "월": m_name,
                    "부문_실적(만원)": b_act,
                    "부문_기준(만원)": b_tar,
                    "부문_달성률(%)": round((b_act / b_tar) * 100, 1) if b_tar > 0 else 0.0,
                    "식품안전팀_실적(만원)": fs_act,
                    "식품안전팀_기준(만원)": fs_tar,
                    "식품안전팀_달성률(%)": round((fs_act / fs_tar) * 100, 1) if fs_tar > 0 else 0.0,
                    "품질관리팀_실적(만원)": qc_act,
                    "품질관리팀_기준(만원)": qc_tar,
                    "품질관리팀_달성률(%)": round((qc_act / qc_tar) * 100, 1) if qc_tar > 0 else 0.0,
                    "_기록여부": is_rec
                })
        return pd.DataFrame(parsed), targets, None
    except Exception as e:
        return pd.DataFrame(), default_targets, str(e)


def fetch_claim_sheet(creds, sheet_urls_map):
    sh, err = open_sheet_threadsafe(creds, sheet_urls_map, "claim")
    if sh is None:
        return pd.DataFrame(), pd.DataFrame(), err

    try:
        ws_all = api_call_with_retry(sh.worksheets)
        target_ws = ws_all[0] if ws_all else None
        if len(ws_all) > 1:
            for w in ws_all:
                sample = get_values_formatted(w)[:8]
                flat_txt = " ".join([" ".join(r) for r in sample])
                if "유형" in flat_txt and ("3월" in flat_txt or "생산" in flat_txt):
                    target_ws = w
                    break

        rows = get_values_unformatted(target_ws)
        header_row_idx = 1
        for idx, r in enumerate(rows[:10]):
            r_str = [str(c).strip() for c in r]
            if "유형" in r_str and "합계" in r_str:
                header_row_idx = idx
                break

        hdr = [str(c).strip() for c in rows[header_row_idx]]
        cat_col = hdr.index("유형") if "유형" in hdr else 1
        sum_col = hdr.index("합계") if "합계" in hdr else 2
        year_col = max(0, cat_col - 1)

        month_col_map = {}
        for idx, cell_txt in enumerate(hdr):
            if cell_txt in FISCAL_MONTHS:
                month_col_map[cell_txt] = idx
        for idx, m in enumerate(FISCAL_MONTHS):
            if m not in month_col_map:
                month_col_map[m] = sum_col + 3 + (idx * 3)

        cat_list = []
        current_year = ""
        for r in rows[header_row_idx + 2:]:
            if not any(str(x).strip() != "" for x in r):
                continue
            r_pad = list(r) + [""] * max(0, 45 - len(r))
            yr_raw = str(r_pad[year_col]).strip()
            cat_raw = str(r_pad[cat_col]).strip()

            if re.search(r"20\d{2}", yr_raw):
                m_yr = re.search(r"(20\d{2})", yr_raw)
                current_year = f"{m_yr.group(1)}년"

            if not current_year or not cat_raw or cat_raw in ["유형", "클레임 건수"]:
                continue

            t_cnt = int(round(to_float(r_pad[sum_col])))
            t_prod = int(round(to_float(r_pad[sum_col + 1])))
            t_ppm = round(to_float(r_pad[sum_col + 2]), 2)

            row_dict = {
                "연도": current_year,
                "유형": cat_raw,
                "합계_건수": t_cnt,
                "합계_생산수량": t_prod,
                "합계_PPM": t_ppm
            }
            for m in FISCAL_MONTHS:
                mc = month_col_map[m]
                m_cnt = int(round(to_float(r_pad[mc]))) if mc < len(r_pad) else 0
                m_prd = int(round(to_float(r_pad[mc + 1]))) if mc + 1 < len(r_pad) else 0
                m_ppm = round(to_float(r_pad[mc + 2]), 2) if mc + 2 < len(r_pad) else 0.0
                row_dict[f"{m}_건수"] = m_cnt
                row_dict[f"{m}_생산수량"] = m_prd
                row_dict[f"{m}_PPM"] = m_ppm
            cat_list.append(row_dict)

        df_category = pd.DataFrame(cat_list)
        if df_category.empty:
            return pd.DataFrame(), pd.DataFrame(), "클레임 시트에서 유효한 데이터를 찾지 못했습니다."

        years_found = sorted(df_category["연도"].unique().tolist(), reverse=True)
        yr_cur = "2026년" if "2026년" in years_found else years_found[0]
        yr_prev = "2025년" if "2025년" in years_found else (years_found[1] if len(years_found) > 1 else "")

        row_cur = df_category[(df_category["연도"] == yr_cur) & (df_category["유형"] == "합계")]
        row_prev = df_category[(df_category["연도"] == yr_prev) & (df_category["유형"] == "합계")] if yr_prev else pd.DataFrame()

        trend_rows = []
        for m in FISCAL_MONTHS:
            c26 = int(row_cur[f"{m}_건수"].values[0]) if not row_cur.empty else 0
            prod26 = int(row_cur[f"{m}_생산수량"].values[0]) if not row_cur.empty else 0
            p26 = float(row_cur[f"{m}_PPM"].values[0]) if not row_cur.empty else 0.0
            c25 = int(row_prev[f"{m}_건수"].values[0]) if not row_prev.empty else 0
            p25 = float(row_prev[f"{m}_PPM"].values[0]) if not row_prev.empty else 0.0
            trend_rows.append({
                "월": m,
                "2026년_건수": c26,
                "2026년_생산수량": prod26,
                "2026년_PPM": p26,
                "2025년_건수": c25,
                "2025년_PPM": p25,
                "목표_PPM": 1.12,
                "_기록여부": (prod26 > 0 or c26 > 0)
            })
        return pd.DataFrame(trend_rows), df_category, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)


def build_division_claim_df(df_category: pd.DataFrame, year_str: str, division_categories: list):
    if df_category.empty:
        return pd.DataFrame(), pd.DataFrame()
    sub = df_category[(df_category["연도"] == year_str) & (df_category["유형"].isin(division_categories))]
    monthly_rows = []
    for m in FISCAL_MONTHS:
        cnt_sum = int(sub[f"{m}_건수"].sum()) if not sub.empty else 0
        prod_sum = int(sub[f"{m}_생산수량"].sum()) if not sub.empty else 0
        ppm_val = round((cnt_sum / prod_sum) * 1_000_000, 2) if prod_sum > 0 else 0.0
        row_item = {
            "월": m,
            "합산_건수": cnt_sum,
            "합산_생산수량": prod_sum,
            "부문_통합_PPM": ppm_val,
            "_기록여부": (prod_sum > 0 or cnt_sum > 0)
        }
        for cat in division_categories:
            cat_row = sub[sub["유형"] == cat]
            row_item[f"{cat}_건수"] = int(cat_row[f"{m}_건수"].values[0]) if not cat_row.empty else 0
            row_item[f"{cat}_PPM"] = float(cat_row[f"{m}_PPM"].values[0]) if not cat_row.empty else 0.0
        monthly_rows.append(row_item)
    return pd.DataFrame(monthly_rows), sub
# ============================ [PART 1 / 4 끝] ============================
# ==============================================================================
# [PART 2 / 4] 3대 공정·이력DB 파서 + 협력업체/심사/특이사항 보드 시트 저장 + 병렬 로딩 엔진
# ==============================================================================

# [3] 공정일보 공통 하단 날짜 탭 정렬 함수 (한국 시간 KST 기준)
def get_sorted_date_worksheets(sh):
    if sh is None:
        return None, None, []
    ws_list = api_call_with_retry(sh.worksheets)
    today = now_kst()
    yesterday = today - timedelta(days=1)

    date_tabs = []
    for w in ws_list:
        t = w.title.strip()
        if t.startswith("_이력DB_") or any(ex in t for ex in ["양식", "복사", "백업", "사본", "대기", "식품안전나라"]):
            continue
        m = re.match(r"^(\d{1,2})[/\.\-](\d{1,2})$", t)
        if m:
            mm, dd = int(m.group(1)), int(m.group(2))
            yr = today.year if mm <= today.month + 1 else today.year - 1
            try:
                dt_obj = datetime(yr, mm, dd)
            except ValueError:
                dt_obj = datetime(today.year, 1, 1)
            date_tabs.append((dt_obj, w))

    past_or_today = sorted([x for x in date_tabs if x[0].date() <= today.date()], key=lambda x: x[0], reverse=True)
    future_tabs = sorted([x for x in date_tabs if x[0].date() > today.date()], key=lambda x: x[0], reverse=True)
    ordered_ws = [w for _, w in (past_or_today + future_tabs)]

    t_cands = {today.strftime("%m/%d"), f"{today.month}/{today.day}", today.strftime("%m.%d"), f"{today.month}.{today.day}"}
    y_cands = {yesterday.strftime("%m/%d"), f"{yesterday.month}/{yesterday.day}", yesterday.strftime("%m.%d"), f"{yesterday.month}.{yesterday.day}"}

    ws_today = next((w for w in ordered_ws if w.title.strip() in t_cands), None)
    ws_yest = next((w for w in ordered_ws if w.title.strip() in y_cands), None)

    if ws_today is None and len(ordered_ws) >= 1:
        ws_today = ordered_ws[0]
    if ws_yest is None and len(ordered_ws) >= 2:
        idx_t = ordered_ws.index(ws_today) if ws_today in ordered_ws else 0
        ws_yest = ordered_ws[idx_t + 1] if idx_t + 1 < len(ordered_ws) else ordered_ws[0]

    if ws_today is None and ws_list:
        non_db_ws = [w for w in ws_list if not w.title.strip().startswith("_이력DB_")]
        ws_today = non_db_ws[0] if non_db_ws else ws_list[0]

    return ws_today, ws_yest, ordered_ws


def eval_ccp3b_cell(val_str: str, std_str: str) -> str:
    s = str(val_str).strip()
    if s in ["", "-"]:
        return ""
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    if not nums:
        return "cell-green" if "적합" in s else ""

    ranges = re.findall(r"(\d+(?:\.\d+)?)\s*~\s*(\d+(?:\.\d+)?)", str(std_str))
    if not ranges:
        return "cell-green"

    all_ok = all(any(float(lo) <= n <= float(hi) for lo, hi in ranges) for n in nums)
    return "cell-green" if all_ok else "cell-red"


def eval_ster_metric(actual_str: str, std_str: str, sterilizer_ho: str, metric_kind: str) -> str:
    act_s = str(actual_str).strip()
    if act_s in ["", "-", "기록대기"]:
        return "cell-yellow"
    act_nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", act_s)]
    if not act_nums:
        return "cell-yellow"
    act_val = act_nums[0]

    std_s = str(std_str).strip()
    if std_s in ["", "-"]:
        return "cell-green"

    target_val = None
    ho_num_m = re.search(r"(\d+)호기", str(sterilizer_ho))
    ho_num = ho_num_m.group(1) if ho_num_m else ""

    if ho_num and f"{ho_num}호기" in std_s:
        m_specific = re.search(rf"{ho_num}호기[^\d]*(\d+(?:\.\d+)?)", std_s)
        if m_specific:
            target_val = float(m_specific.group(1))
    elif "그외" in std_s:
        m_other = re.search(r"그외[^\d]*(\d+(?:\.\d+)?)", std_s)
        if m_other:
            target_val = float(m_other.group(1))

    if target_val is None:
        std_nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", std_s)]
        if std_nums:
            target_val = min(std_nums)

    if target_val is None:
        return "cell-green"

    if metric_kind == "temp":
        return "cell-green" if act_val >= (target_val - 2.0) else "cell-red"
    if metric_kind == "press":
        return "cell-green" if act_val >= (target_val * 0.90) else "cell-red"
    if metric_kind == "hold":
        return "cell-green" if act_val >= (target_val - 0.8) else "cell-red"
    return "cell-green"


def is_same_tab_date_memo(memo_dt_str: str, tab_title: str) -> bool:
    m_tab = re.match(r"^(\d{1,2})[/\.\-](\d{1,2})$", str(tab_title).strip())
    if not m_tab or not str(memo_dt_str).strip():
        return False
    t_m, t_d = int(m_tab.group(1)), int(m_tab.group(2))

    s = str(memo_dt_str).strip()
    if re.search(r"(?:20)?25[\.\-/]", s):
        return False
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if len(nums) >= 3:
        yr, mm, dd = nums[0], nums[1], nums[2]
        if yr in (26, 2026) and mm == t_m and dd == t_d:
            return True
    elif len(nums) == 2:
        if nums[0] == t_m and nums[1] == t_d:
            return True
    return False


# [3-A] 상온제품 공정 관리 일보 실시간 파서 (기존 화면 구조 100% 보존)
def parse_rt_process_worksheet(ws):
    if ws is None:
        return None
    rows = get_values_formatted(ws)
    if len(rows) < 5:
        return None

    tab_title = ws.title.strip()
    prod_date_str = tab_title
    for r in rows[:4]:
        for c in r[:18]:
            if "생 산 일" in str(c) or re.search(r"202\d\.\s*\d{1,2}\.\s*\d{1,2}", str(c)):
                prod_date_str = str(c).replace("생 산 일 :", "").strip()
                break

    r_pack_hdr, r_ccp3b_hdr, r_ster_hdr = None, None, None
    for idx, r in enumerate(rows):
        b_txt = re.sub(r"\s+", "", str(r[1])) if len(r) > 1 else ""
        row_join = re.sub(r"\s+", "", "".join(str(x) for x in r[:12]))
        if r_pack_hdr is None and b_txt == "포장호기":
            r_pack_hdr = idx
        elif r_ccp3b_hdr is None and ("CCP-3B" in row_join or "포장기공정관리" in row_join):
            r_ccp3b_hdr = idx
        elif r_ccp3b_hdr is not None and r_ster_hdr is None and b_txt == "멸균기":
            r_ster_hdr = idx
            break

    if r_pack_hdr is None:
        r_pack_hdr = 2
    if r_ccp3b_hdr is None:
        r_ccp3b_hdr = min(15, len(rows) - 1)
    if r_ster_hdr is None:
        r_ster_hdr = min(r_ccp3b_hdr + 6, len(rows) - 1)

    ho_products, ho_rows_raw = {}, {}
    current_ho = ""
    for r in rows[r_pack_hdr + 1 : r_ccp3b_hdr]:
        r_pad = list(r) + [""] * max(0, 18 - len(r))
        b_val = str(r_pad[1]).strip()
        if re.match(r"^[A-Z가-힣0-9]+호기$", b_val):
            current_ho = b_val
            ho_rows_raw.setdefault(current_ho, [])
            ho_products.setdefault(current_ho, [])

        if not current_ho:
            continue

        slots = [
            (r_pad[2:6], [r_pad[6]], r_pad[7:9]),
            (r_pad[9:13], r_pad[13:15], r_pad[15:17])
        ]
        for p_cells, e_cells, t_cells in slots:
            p_name = next((str(x).strip() for x in p_cells if str(x).strip() not in ["", "제 품 명", "제  품  명"]), "")
            exp_v = next((str(x).strip() for x in e_cells if str(x).strip() != ""), "")
            t_parts = [str(x).strip() for x in t_cells if str(x).strip() != ""]
            t_str = " / ".join(t_parts)

            if p_name or exp_v:
                has_time = bool(re.search(r"\d{1,2}:\d{2}", t_str))
                if p_name and has_time and exp_v:
                    st_txt, st_cls = "🟢 확인완료", "cell-green"
                elif p_name and not exp_v:
                    st_txt, st_cls = "🔴 소비기한 누락", "cell-red"
                else:
                    st_txt, st_cls = "🟡 확인시간 대기", "cell-yellow"

                if p_name and p_name not in ho_products[current_ho]:
                    ho_products[current_ho].append(p_name)

                ho_rows_raw[current_ho].append({
                    "포장호기": current_ho,
                    "생산 제품명": p_name if p_name else "(제품명 미기입)",
                    "소비기한": exp_v if exp_v else "-",
                    "확인시간": t_str if t_str else "미기입(대기)",
                    "상태": st_txt,
                    "_cls": st_cls
                })

    lines_records = []
    for ho_k, items in ho_rows_raw.items():
        if items:
            lines_records.extend(items)
        else:
            lines_records.append({
                "포장호기": ho_k,
                "생산 제품명": "(비가동)",
                "소비기한": "-",
                "확인시간": "-",
                "상태": "⚪ 비가동",
                "_cls": "cell-gray"
            })

    ccp3b_records = []
    r_3b_colhdr = r_ccp3b_hdr
    for sub_i in range(r_ccp3b_hdr, min(r_ccp3b_hdr + 3, r_ster_hdr)):
        if sum(1 for c in rows[sub_i][:18] if re.match(r"^[A-F]호기$", str(c).strip())) >= 3:
            r_3b_colhdr = sub_i
            break

    hdr_3b = [str(x).strip() for x in rows[r_3b_colhdr][:18]]
    ho_pos_list = sorted([(idx, cell) for idx, cell in enumerate(hdr_3b) if re.match(r"^[A-F]호기$", cell)], key=lambda x: x[0])

    first_ho_col = ho_pos_list[0][0] if ho_pos_list else 8
    ho_col_spans = {}
    for i_p, (c_start, h_lbl) in enumerate(ho_pos_list):
        c_end = ho_pos_list[i_p + 1][0] if i_p + 1 < len(ho_pos_list) else 17
        ho_col_spans[h_lbl] = (c_start, c_end)

    last_item_3b = ""
    for r in rows[r_3b_colhdr + 1 : r_ster_hdr]:
        r_pad = list(r) + [""] * max(0, 18 - len(r))
        if not any(str(x).strip() for x in r_pad[1:17]):
            continue
        item_nm = str(r_pad[1]).strip()
        if item_nm:
            last_item_3b = item_nm

        left_meta = [str(x).strip() for x in r_pad[2:first_ho_col] if str(x).strip() and str(x).strip() != item_nm]
        std_parts = [x for x in left_meta if any(u in x for u in ["~", "%", "℃", "㎕", "이상", "이하"])]
        eq_parts = [x for x in left_meta if x not in std_parts]

        std_nm = " ".join(std_parts)
        equip_nm = " ".join(eq_parts)
        if not last_item_3b and not std_nm:
            continue

        rec_3b = {"항목": last_item_3b, "관리기준": std_nm or "-", "적용설비": equip_nm or "-"}
        for ho_lbl in ["A호기", "B호기", "C호기", "D호기", "E호기", "F호기"]:
            if ho_lbl in ho_col_spans:
                cs, ce = ho_col_spans[ho_lbl]
                vals_in_span = [str(x).strip() for x in r_pad[cs:ce] if str(x).strip() not in ["", "-"]]
                rec_3b[ho_lbl] = " / ".join(vals_in_span) if vals_in_span else "-"
            else:
                rec_3b[ho_lbl] = "-"
        ccp3b_records.append(rec_3b)

    sv_std_by_prod = {}
    for r in rows[r_ster_hdr:]:
        if len(r) >= 22:
            s_t = re.sub(r"\s+", " ", str(r[18])).strip()
            t_p = re.sub(r"\s+", " ", str(r[19])).strip()
            u_h = re.sub(r"\s+", " ", str(r[20])).strip()
            v_pr = re.sub(r"\s+", " ", str(r[21])).strip()
            if v_pr and v_pr not in ["호기별 제품", "제품명"] and any([s_t, t_p, u_h]):
                sv_std_by_prod[v_pr] = (s_t, t_p, u_h)

    ster_blocks = []
    cur_block = None
    for r in rows[r_ster_hdr + 1:]:
        r_pad = list(r) + [""] * max(0, 23 - len(r))
        b_cell = str(r_pad[1]).strip()

        if re.match(r"^\d+호기$", b_cell):
            if cur_block:
                ster_blocks.append(cur_block)
            cur_block = {"ster_ho": b_cell, "rows": [r_pad], "remark": ""}
        elif re.sub(r"\s+", "", b_cell) == "특이사항" and cur_block is not None:
            rem_chunks = []
            for x in r_pad[2:17]:
                xs = str(x).strip()
                if xs not in ["", "-"] and xs not in rem_chunks:
                    rem_chunks.append(xs)
            cur_block["remark"] = " ".join(rem_chunks)
            ster_blocks.append(cur_block)
            cur_block = None
        elif cur_block is not None and len(cur_block["rows"]) < 5:
            if b_cell == "":
                cur_block["rows"].append(r_pad)
            else:
                ster_blocks.append(cur_block)
                cur_block = None
    if cur_block:
        ster_blocks.append(cur_block)

    ster_records = []
    ster_special_notes = []
    ho_ster_summary, ho_remark_map = {}, {}

    for blk in ster_blocks:
        s_ho = blk["ster_ho"]
        b_rows = blk["rows"]
        pack_ho = next((str(br[2]).strip() for br in b_rows if str(br[2]).strip() not in ["", "-"]), "-")
        vol_str = next((str(br[3]).strip() for br in b_rows if str(br[3]).strip() not in ["", "-"]), "-")
        flt_str = next((str(br[13]).strip() or str(br[14]).strip() for br in b_rows if (str(br[13]).strip() or str(br[14]).strip()) not in ["", "-"]), "-")

        std_temp = next((re.sub(r"\s+", " ", str(br[18])).strip() for br in b_rows if str(br[18]).strip() not in ["", "-", "멸균온도"]), "")
        std_press = next((re.sub(r"\s+", " ", str(br[19])).strip() for br in b_rows if str(br[19]).strip() not in ["", "-", "균질압"]), "")
        std_hold = next((re.sub(r"\s+", " ", str(br[20])).strip() for br in b_rows if str(br[20]).strip() not in ["", "-", "멸균시간"]), "")
        std_v_prod = next((re.sub(r"\s+", " ", str(br[21])).strip() for br in b_rows if str(br[21]).strip() not in ["", "-", "호기별 제품"]), "")

        matched_prods = ho_products.get(pack_ho, [])
        matched_prod_str = ", ".join(matched_prods) if matched_prods else (std_v_prod or "-")

        if not (std_temp or std_press or std_hold) and matched_prods:
            for mp in matched_prods:
                for sv_k, (st_t, st_p, st_h) in sv_std_by_prod.items():
                    if sv_k in mp or mp in sv_k:
                        std_temp, std_press, std_hold = st_t, st_p, st_h
                        break

        rem_val = blk["remark"].strip()
        if rem_val:
            ster_special_notes.append(f"[{s_ho}·{pack_ho} {matched_prod_str}] {rem_val}")
            if pack_ho != "-":
                ho_remark_map[pack_ho] = rem_val

        has_record = False
        for br in b_rows:
            mon_time = str(br[4]).strip() or str(br[5]).strip()
            temp_v = str(br[6]).strip()
            press_v = str(br[7]).strip() or str(br[8]).strip()
            hold_v = str(br[9]).strip()
            flow_v = str(br[10]).strip() or str(br[11]).strip()
            cool_v = str(br[12]).strip()
            sign_v = str(br[15]).strip() or str(br[16]).strip()

            if any(x not in ["", "-"] for x in [mon_time, temp_v, press_v, hold_v, flow_v, cool_v]):
                has_record = True
                temp_disp = f"{temp_v}℃" + (f" (기준: {std_temp})" if std_temp else "")
                press_disp = f"{press_v}" + (f" (기준: {std_press})" if std_press else "")
                hold_disp = f"{hold_v}초" + (f" (기준: {std_hold})" if std_hold else "")

                c_temp = eval_ster_metric(temp_v, std_temp, s_ho, "temp")
                c_press = eval_ster_metric(press_v, std_press, s_ho, "press")
                c_hold = eval_ster_metric(hold_v, std_hold, s_ho, "hold")
                c_flt = "cell-green" if flt_str == "적합" else ("cell-red" if "부적합" in flt_str else "cell-yellow")
                c_time = "cell-green" if re.search(r"\d{1,2}:\d{2}", mon_time) else "cell-yellow"
                c_sign = "cell-green" if sign_v not in ["", "-"] else "cell-yellow"

                ster_records.append({
                    "멸균기_포장": f"{s_ho} ({pack_ho})",
                    "매칭 제품명": f"{matched_prod_str} ({vol_str})" if vol_str != "-" else matched_prod_str,
                    "확인시간": mon_time or "미기입",
                    "멸균온도": temp_disp,
                    "균질압": press_disp,
                    "멸균시간": hold_disp,
                    "유량_냉각": f"{flow_v or '-'} L/h / {cool_v or '-'}℃",
                    "여과망_서명": f"{flt_str} / {sign_v or '미서명'}",
                    "특이사항": rem_val if rem_val else "없음",
                    "_c_time": c_time,
                    "_c_temp": c_temp,
                    "_c_press": c_press,
                    "_c_hold": c_hold,
                    "_c_flt": c_flt if c_sign == "cell-green" else "cell-yellow",
                    "_c_rem": "cell-yellow" if rem_val else ""
                })
                if pack_ho != "-":
                    ho_ster_summary[pack_ho] = f"{s_ho} ({temp_v}℃ / {press_v}bar / {hold_v}초 / 여과망:{flt_str})"

        if not has_record and pack_ho != "-":
            ster_records.append({
                "멸균기_포장": f"{s_ho} ({pack_ho})",
                "매칭 제품명": f"{matched_prod_str} ({vol_str})" if vol_str != "-" else matched_prod_str,
                "확인시간": "기록대기",
                "멸균온도": f"- (기준: {std_temp})" if std_temp else "-",
                "균질압": f"- (기준: {std_press})" if std_press else "-",
                "멸균시간": f"- (기준: {std_hold})" if std_hold else "-",
                "유량_냉각": "-",
                "여과망_서명": f"{flt_str} / 미서명",
                "특이사항": rem_val if rem_val else "없음",
                "_c_time": "cell-yellow",
                "_c_temp": "cell-yellow",
                "_c_press": "cell-yellow",
                "_c_hold": "cell-yellow",
                "_c_flt": "cell-yellow",
                "_c_rem": "cell-yellow" if rem_val else ""
            })

    compact_rows = []
    for lr in lines_records:
        if lr["생산 제품명"] == "(비가동)":
            continue
        p_ho = lr["포장호기"]
        rem_txt = ho_remark_map.get(p_ho, "이상없음")
        compact_rows.append({
            "포장호기": p_ho,
            "생산 제품명": lr["생산 제품명"],
            "소비기한": lr["소비기한"],
            "확인시간": lr["확인시간"],
            "멸균기·CCP 요약": ho_ster_summary.get(p_ho, "-"),
            "특이사항": rem_txt,
            "_cls_status": lr["_cls"],
            "_cls_rem": "cell-yellow" if rem_txt != "이상없음" else "cell-green"
        })

    for r in rows[4:]:
        if len(r) >= 29:
            dt_s = str(r[27]).strip()
            if not is_same_tab_date_memo(dt_s, tab_title):
                continue
            memo_chunks = []
            for c in r[28:]:
                cs = str(c).strip()
                if cs and cs not in memo_chunks and "전달(특이)" not in cs and "생 산 일" not in cs:
                    memo_chunks.append(cs)
            memo_s = " / ".join(memo_chunks)
            if memo_s:
                ster_special_notes.append(f"[당일 전달사항] {memo_s}")

    return {
        "tab_title": tab_title,
        "prod_date": prod_date_str,
        "running_hos": {k for k, v in ho_products.items() if v},
        "lines_records": lines_records,
        "compact_rows": compact_rows,
        "ccp3b_records": ccp3b_records,
        "ster_records": ster_records,
        "ster_special_notes": ster_special_notes
    }


# [3-B] 유제품 포장 공정관리 일보 실시간 파서 (기존 화면 구조 100% 보존)
def parse_dairy_pack_worksheet(ws, line_label: str):
    if ws is None:
        return pd.DataFrame(), "-"
    rows = get_values_formatted(ws)
    w_date = ws.title.strip()
    for r in rows[:5]:
        joined = " ".join([str(c).strip() for c in r if str(c).strip()])
        m_dt = re.search(r"202\d[\.\-\s]+\d{1,2}[\.\-\s]+\d{1,2}", joined)
        if m_dt:
            w_date = m_dt.group(0).strip()
            break

    parsed_products = []
    for r_idx, r in enumerate(rows):
        first_cell = re.sub(r"\s+", "", str(r[0])) if len(r) > 0 else ""
        if first_cell in ["제품명", "품목"]:
            next_block_r = len(rows)
            for nr in range(r_idx + 1, min(r_idx + 20, len(rows))):
                nc = re.sub(r"\s+", "", str(rows[nr][0])) if len(rows[nr]) > 0 else ""
                if nc in ["제품명", "품목", "생산시간", "CCP검증모니터링"]:
                    next_block_r = nr
                    break

            for col_i in range(1, len(r)):
                p_name = re.sub(r"\s+", " ", str(r[col_i])).strip()
                if not p_name or p_name in ["제 품 명", "제품명", "품 목", "품목"] or "특이사항" in p_name:
                    continue

                vol_str, chk_time = "", "-"
                exp_list = []
                label_ok, top_ok, bot_ok, vol_ok, sens_ok = "-", "-", "-", "-", "-"

                for sub_r in rows[r_idx + 1 : next_block_r]:
                    row_lbl = re.sub(r"\s+", "", str(sub_r[0])) if len(sub_r) > 0 else ""
                    val = str(sub_r[col_i]).strip() if col_i < len(sub_r) else ""
                    if not val:
                        continue
                    if "㎖" in val or "mL" in val:
                        vol_str = val
                    elif "확인시간" in row_lbl:
                        chk_time = val
                    elif any(k in row_lbl for k in ["소비기한", "Tank"]) or re.match(r"^\d{2}\.\d{2}[A-Z]?$", row_lbl):
                        if val not in ["00.00", "-", "소비기한"] and "제조일로부터" not in val:
                            exp_list.append(val)
                    elif "표시사항" in row_lbl or "표기사항" in row_lbl:
                        label_ok = val
                    elif "상부접착" in row_lbl or "상/하부접착" in row_lbl:
                        top_ok = val
                        if "상/하부" in row_lbl:
                            bot_ok = val
                    elif "하부접착" in row_lbl:
                        bot_ok = val
                    elif "제품용량" in row_lbl:
                        vol_ok = val
                    elif "관능" in row_lbl:
                        sens_ok = val

                exp_joined = ", ".join(dict.fromkeys(exp_list)) if exp_list else "-"
                is_running = (exp_joined != "-") or (chk_time not in ["-", ""])
                full_p_name = f"{p_name} ({vol_str})" if vol_str else p_name

                parsed_products.append({
                    "라인구분": line_label,
                    "작성일": w_date,
                    "가동여부": "🟢 금일생산" if is_running else "⚪ 미생산(00.00)",
                    "제품명": full_p_name,
                    "확인시간": chk_time,
                    "표기 소비기한": exp_joined,
                    "표시사항": label_ok,
                    "상부접착": top_ok,
                    "하부접착": bot_ok,
                    "제품용량": vol_ok,
                    "관능(5점법)": sens_ok
                })

    return pd.DataFrame(parsed_products), w_date


# [3-C] 두유 배양검사 일보 실시간 파서 (탭 날짜 기준 생산일 역산 보정 유지)
SOY_STOP_LABELS = {
    "배양검사", "배양온도", "용량/포장기", "포장기", "작성자", "검사자",
    "품목", "생산일", "소비기한", "검사일", "생산시작", "생산종료",
    "총검사수량", "오염수량", "판정", "특이사항", "소비기한품목명표시",
    "확인시간", "제품명", "TRUE", "FALSE"
}


def calc_run_duration(start_str: str, end_str: str) -> str:
    m1 = re.search(r"(\d{1,2}):(\d{2})", str(start_str))
    m2 = re.search(r"(\d{1,2}):(\d{2})", str(end_str))
    if not m1 or not m2:
        return "-"
    s_min = int(m1.group(1)) * 60 + int(m1.group(2))
    e_min = int(m2.group(1)) * 60 + int(m2.group(2))
    if e_min < s_min:
        e_min += 24 * 60
    diff = e_min - s_min
    return f"{diff // 60}시간 {diff % 60:02d}분"


def extract_clean_right_values(sr: list, start_idx: int) -> list:
    out = []
    for raw_x in sr[start_idx + 1:]:
        xs = str(raw_x).strip()
        if not xs:
            continue
        norm_x = re.sub(r"\s+", "", xs).upper()
        if norm_x in SOY_STOP_LABELS or "소비기한품목명표시" in norm_x:
            break
        out.append(xs)
    return out


def resolve_soy_realtime_dates(tab_title: str, raw_prod_dt: str, raw_insp_dt: str, inc_days: str):
    today_d = now_kst().date()
    m_tab = re.match(r"^(\d{1,2})[/\.\-](\d{1,2})$", str(tab_title).strip())
    if not m_tab:
        return raw_prod_dt or "-", raw_insp_dt or "-"

    mm, dd = int(m_tab.group(1)), int(m_tab.group(2))
    yr = today_d.year if mm <= today_d.month + 1 else today_d.year - 1
    try:
        tab_d = date(yr, mm, dd)
    except ValueError:
        return raw_prod_dt or "-", raw_insp_dt or "-"

    c_insp = pd.to_datetime(re.sub(r"\s+", "", str(raw_insp_dt)).rstrip("."), errors="coerce")
    c_prod = pd.to_datetime(re.sub(r"\s+", "", str(raw_prod_dt)).rstrip("."), errors="coerce")

    offset = 7 if "7" in str(inc_days) else 5
    if pd.notna(c_insp) and pd.notna(c_prod):
        diff = (c_insp.date() - c_prod.date()).days
        if 1 <= diff <= 20:
            offset = diff

    if pd.isna(c_prod) or (pd.notna(c_insp) and c_insp.date() == today_d and tab_d != today_d):
        true_prod = (tab_d - timedelta(days=offset)).strftime("%Y-%m-%d")
        return true_prod, tab_d.strftime("%Y-%m-%d")

    prod_str = c_prod.strftime("%Y-%m-%d") if pd.notna(c_prod) else (raw_prod_dt or "-")
    return prod_str, tab_d.strftime("%Y-%m-%d")


def parse_soy_incubation_worksheet(ws):
    if ws is None:
        return pd.DataFrame(), pd.DataFrame()
    rows = get_values_formatted(ws)
    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    tab_title = ws.title.strip()
    anchors = []
    for r_i, r in enumerate(rows):
        for c_i, cell in enumerate(r):
            if re.sub(r"\s+", "", str(cell)) == "배양검사":
                anchors.append((r_i, c_i))

    blocks_parsed, hourly_all = [], []

    for _, (r0, c0) in enumerate(anchors):
        same_row_next_c = [c for (rr, c) in anchors if abs(rr - r0) <= 2 and c > c0]
        c_end = min(same_row_next_c) if same_row_next_c else c0 + 14

        same_col_next_r = [rr for (rr, c) in anchors if abs(c - c0) <= 2 and rr > r0]
        r_end = min(same_col_next_r) if same_col_next_r else min(len(rows), r0 + 48)

        sub_rows = [list(rows[rr][c0:min(c_end, len(rows[rr]))]) for rr in range(r0, r_end)]

        inc_days, inc_temp, vol_ml, machine_ho = "", "", "", ""
        writer_nm, inspector_nm = "", ""
        item_names, exp_dates = [], []
        prod_dt, insp_dt, t_start, t_end, total_smp = "", "", "", "", ""
        contam_cnt, judge_res, remark_txt = "", "", ""

        for sr_i, sr in enumerate(sub_rows):
            for sc_i, val in enumerate(sr):
                key = re.sub(r"\s+", "", str(val))
                if not key:
                    continue
                right_vals = extract_clean_right_values(sr, sc_i)

                if key == "배양검사" and not inc_days and right_vals:
                    inc_days = right_vals[0]
                elif key == "배양온도" and not inc_temp and right_vals:
                    inc_temp = right_vals[0]
                elif ("용량/포장기" in key or key == "포장기") and not machine_ho:
                    for rv in right_vals[:3]:
                        if "호기" in rv and not machine_ho:
                            machine_ho = rv
                        elif re.search(r"^\d{2,4}$", rv.replace("mL", "").replace("㎖", "").strip()) and not vol_ml:
                            vol_ml = rv
                elif key == "작성자" and not writer_nm and right_vals:
                    writer_nm = right_vals[0]
                elif key == "검사자" and not inspector_nm and right_vals:
                    inspector_nm = right_vals[0]
                elif key == "품목":
                    for rv in right_vals:
                        if rv not in item_names:
                            item_names.append(rv)
                    if sr_i + 1 < len(sub_rows):
                        next_sr = sub_rows[sr_i + 1]
                        next_first = re.sub(r"\s+", "", str(next_sr[0])) if next_sr else ""
                        if next_first not in SOY_STOP_LABELS:
                            for rv in [str(x).strip() for x in next_sr if str(x).strip()]:
                                norm_rv = re.sub(r"\s+", "", rv).upper()
                                if norm_rv in SOY_STOP_LABELS or "소비기한품목명표시" in norm_rv:
                                    continue
                                if not re.search(r"^202\d", rv) and rv not in item_names:
                                    item_names.append(rv)
                elif key == "생산일" and not prod_dt and right_vals:
                    prod_dt = right_vals[0]
                elif key == "소비기한":
                    for rv in right_vals:
                        if re.search(r"\d{2,4}[\.\-/]\s*\d{1,2}[\.\-/]\s*\d{1,2}", rv) and rv not in exp_dates:
                            exp_dates.append(rv)
                elif key == "검사일" and not insp_dt and right_vals:
                    insp_dt = right_vals[0]
                elif key == "생산시작" and not t_start and right_vals:
                    if re.search(r"\d{1,2}:\d{2}", right_vals[0]):
                        t_start = right_vals[0]
                elif key == "생산종료" and not t_end and right_vals:
                    if re.search(r"\d{1,2}:\d{2}", right_vals[0]):
                        t_end = right_vals[0]
                elif key == "총검사수량" and not total_smp and right_vals:
                    if re.search(r"\d+", right_vals[0]):
                        total_smp = right_vals[0]
                elif key == "오염수량":
                    look_cells = right_vals[:]
                    if sr_i + 1 < len(sub_rows):
                        look_cells.extend([
                            str(x).strip() for x in sub_rows[sr_i + 1]
                            if str(x).strip() and re.sub(r"\s+", "", str(x)).upper() not in SOY_STOP_LABELS
                        ])
                    for lv in look_cells:
                        if ("개" in lv or lv.isdigit()) and not contam_cnt:
                            contam_cnt = lv
                        elif lv in ["적합", "부적합"] and not judge_res:
                            judge_res = lv
                elif key == "특이사항" and right_vals:
                    remark_txt = " ".join(right_vals)

            first_t = str(sr[0]).strip() if sr else ""
            if re.match(r"^\d{2}\s*:$", first_t) and machine_ho:
                smp_v = " ".join([str(x).strip() for x in sr[1:6] if str(x).strip()])
                strp_v = " ".join([str(x).strip() for x in sr[6:9] if str(x).strip()])
                pap_v = " ".join([str(x).strip() for x in sr[9:12] if str(x).strip()])
                if smp_v or strp_v or pap_v:
                    hourly_all.append({
                        "포장기": machine_ho,
                        "시간대": first_t,
                        "샘플체크": smp_v or "-",
                        "Strip": strp_v or "-",
                        "Paper": pap_v or "-"
                    })

        has_valid_record = bool(machine_ho) and (bool(item_names) or bool(total_smp) or bool(t_start))
        if not has_valid_record:
            continue

        clean_inspector = re.sub(r"[\s\-_]", "", str(inspector_nm))
        is_inspected = bool(clean_inspector) and clean_inspector not in ["미입력", "미검사", "검사전", "대기", "없음"]

        if not is_inspected:
            insp_disp = "미입력 (검사전)"
            final_judge = "검사전"
            status_badge = "🟡 검사전"
        else:
            insp_disp = inspector_nm.strip()
            final_judge = judge_res if judge_res else "적합"
            if to_float(contam_cnt, 0) > 0 or "부적합" in final_judge:
                status_badge = "🔴 부적합"
            else:
                status_badge = "🟢 검사완료"

        true_prod_dt, true_insp_dt = resolve_soy_realtime_dates(tab_title, prod_dt, insp_dt, inc_days)

        blocks_parsed.append({
            "시트탭": tab_title,
            "포장기": machine_ho,
            "배양구분": f"{inc_days} ({inc_temp})".strip(" ()"),
            "용량(mL)": vol_ml or "-",
            "품목명": " / ".join(item_names) if item_names else "-",
            "생산일": true_prod_dt,
            "소비기한": " / ".join(exp_dates) if exp_dates else "-",
            "검사일(개봉일)": true_insp_dt,
            "생산 시작~종료": f"{t_start} ~ {t_end}" if (t_start or t_end) else "-",
            "실가동시간": calc_run_duration(t_start, t_end),
            "총 검사수량": total_smp or "0",
            "오염수량": contam_cnt if is_inspected and contam_cnt else ("-" if not is_inspected else (contam_cnt or "0 개")),
            "작성자": writer_nm.strip() if writer_nm.strip() else "-",
            "검사자": insp_disp,
            "검사완료여부": is_inspected,
            "진행상태": status_badge,
            "판정": final_judge,
            "특이사항": remark_txt or "없음"
        })

    return pd.DataFrame(blocks_parsed), pd.DataFrame(hourly_all)


# [3-D] 3개 공정 시트 로더 (실시간 탭 + 숨김 _이력DB_* 탭 + '제품명 식품안전나라' A열 마스터 동시 로드)
def fetch_process_rt_sheet(creds, sheet_urls_map):
    sh_rt, err_rt = open_sheet_threadsafe(creds, sheet_urls_map, "process_rt")
    if sh_rt is None:
        return None, None, pd.DataFrame(), pd.DataFrame(), [], f"[상온공정일보] {err_rt}"
    try:
        ws_all = api_call_with_retry(sh_rt.worksheets)
        ws_rt_today, ws_rt_yest, _ = get_sorted_date_worksheets(sh_rt)
        rt_today_parsed = parse_rt_process_worksheet(ws_rt_today)
        rt_yest_parsed = parse_rt_process_worksheet(ws_rt_yest)

        ws_hist_p = next((w for w in ws_all if w.title.strip() == HIST_TABS["rt_prod"]), None)
        ws_hist_c = next((w for w in ws_all if w.title.strip() == HIST_TABS["rt_ccp"]), None)
        df_rt_hist_p = rows_to_df(get_values_formatted(ws_hist_p)) if ws_hist_p is not None else pd.DataFrame()
        df_rt_hist_c = rows_to_df(get_values_formatted(ws_hist_c)) if ws_hist_c is not None else pd.DataFrame()

        fsk_products = []
        ws_fsk = next(
            (w for w in ws_all if re.sub(r"\s+", "", w.title) == "제품명식품안전나라" or "식품안전나라" in w.title),
            None
        )
        if ws_fsk is not None:
            fsk_rows = get_values_formatted(ws_fsk)
            skip_hdrs = {"제품명", "품목명", "품목", "제 품 명", "번호", "no", "코드", "품목제조보고"}
            for r in fsk_rows:
                if not r:
                    continue
                col_a = re.sub(r"\s+", " ", str(r[0])).strip()
                if not col_a or col_a == "-" or col_a.lower() in skip_hdrs:
                    continue
                if re.match(r"^\d+$", col_a):
                    continue
                if col_a not in fsk_products:
                    fsk_products.append(col_a)

        return rt_today_parsed, rt_yest_parsed, df_rt_hist_p, df_rt_hist_c, fsk_products, None
    except Exception as e:
        return None, None, pd.DataFrame(), pd.DataFrame(), [], f"[상온공정일보] {e}"


def fetch_process_milk_sheet(creds, sheet_urls_map):
    sh_milk, err_milk = open_sheet_threadsafe(creds, sheet_urls_map, "process_milk")
    if sh_milk is None:
        return pd.DataFrame(), pd.DataFrame(), "-", "-", pd.DataFrame(), pd.DataFrame(), [], f"[유제품포장일보] {err_milk}"
    try:
        ws_all = api_call_with_retry(sh_milk.worksheets)
        ws_m, ws_f = None, None
        ws_m_tpl, ws_f_tpl = None, None

        for w in ws_all:
            wt = w.title.strip()
            if wt == "우유":
                ws_m = w
            elif wt == "발효유":
                ws_f = w
            elif "우유" in wt and "복사용" in wt and ws_m_tpl is None:
                ws_m_tpl = w
            elif "발효유" in wt and "복사용" in wt and ws_f_tpl is None:
                ws_f_tpl = w

        df_m, m_dt = parse_dairy_pack_worksheet(ws_m, "우유") if ws_m is not None else (pd.DataFrame(), "-")
        df_f, f_dt = parse_dairy_pack_worksheet(ws_f, "발효유") if ws_f is not None else (pd.DataFrame(), "-")

        ws_hist_dp = next((w for w in ws_all if w.title.strip() == HIST_TABS["dairy_prod"]), None)
        ws_hist_dc = next((w for w in ws_all if w.title.strip() == HIST_TABS["dairy_ccp"]), None)
        df_dairy_hist_p = rows_to_df(get_values_formatted(ws_hist_dp)) if ws_hist_dp is not None else pd.DataFrame()
        df_dairy_hist_c = rows_to_df(get_values_formatted(ws_hist_dc)) if ws_hist_dc is not None else pd.DataFrame()

        dairy_prod_names = []
        for tpl_ws, lbl in [(ws_m or ws_m_tpl, "우유"), (ws_f or ws_f_tpl, "발효유")]:
            if tpl_ws is not None:
                df_tpl, _ = parse_dairy_pack_worksheet(tpl_ws, lbl)
                if not df_tpl.empty and "제품명" in df_tpl.columns:
                    for pn in df_tpl["제품명"].dropna().tolist():
                        p_clean = str(pn).strip()
                        if p_clean and p_clean != "-" and p_clean not in dairy_prod_names:
                            dairy_prod_names.append(p_clean)

        return df_m, df_f, m_dt, f_dt, df_dairy_hist_p, df_dairy_hist_c, dairy_prod_names, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), "-", "-", pd.DataFrame(), pd.DataFrame(), [], f"[유제품포장일보] {e}"


def fetch_process_soy_sheet(creds, sheet_urls_map):
    sh_soy, err_soy = open_sheet_threadsafe(creds, sheet_urls_map, "process_soy")
    if sh_soy is None:
        return "-", {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), f"[두유배양일보] {err_soy}"
    try:
        ws_all = api_call_with_retry(sh_soy.worksheets)
        _, _, soy_date_ws_list = get_sorted_date_worksheets(sh_soy)
        soy_tabs_parsed = {}
        default_tab_title = "-"

        for w in soy_date_ws_list[:5]:
            t_title = w.title.strip()
            df_b, df_h = parse_soy_incubation_worksheet(w)
            if not df_b.empty:
                soy_tabs_parsed[t_title] = (df_b, df_h)
                if default_tab_title == "-":
                    default_tab_title = t_title

        if default_tab_title == "-" and soy_date_ws_list:
            first_ws = soy_date_ws_list[0]
            default_tab_title = first_ws.title.strip()
            soy_tabs_parsed[default_tab_title] = parse_soy_incubation_worksheet(first_ws)

        df_sb, df_sh = soy_tabs_parsed.get(default_tab_title, (pd.DataFrame(), pd.DataFrame()))

        ws_hist_soy = next((w for w in ws_all if w.title.strip() == HIST_TABS["soy_inc"]), None)
        df_soy_hist = rows_to_df(get_values_formatted(ws_hist_soy)) if ws_hist_soy is not None else pd.DataFrame()

        return default_tab_title, soy_tabs_parsed, df_sb, df_sh, df_soy_hist, None
    except Exception as e:
        return "-", {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), f"[두유배양일보] {e}"


# [4] 협력업체 심사 결과 DB
def fetch_supplier_sheet(creds, sheet_urls_map):
    sh, err = open_sheet_threadsafe(creds, sheet_urls_map, "supplier")
    if sh is None:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), err

    try:
        ws_list = api_call_with_retry(sh.worksheets)
        ws1 = ws_list[0] if len(ws_list) >= 1 else None
        ws2 = ws_list[1] if len(ws_list) >= 2 else None
        if ws2 is None:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "협력업체 시트2가 없습니다."

        rows1 = get_values_formatted(ws1) if ws1 else []
        df_s1 = pd.DataFrame()
        if len(rows1) >= 2:
            hdr1 = [str(h).strip() for h in rows1[0]]
            data1 = [dict(zip(hdr1, (list(r) + [""] * len(hdr1))[:len(hdr1)])) for r in rows1[1:] if any(r)]
            df_s1 = pd.DataFrame(data1)

        rows2 = get_values_formatted(ws2)
        if len(rows2) < 2:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), df_s1, "협력업체 시트2(마스터 명단)가 비어 있습니다."

        exact_score_map, core_score_map = {}, {}
        if not df_s1.empty and "업체명" in df_s1.columns and "심사항목" in df_s1.columns:
            df_s1["_norm_exact"] = df_s1["업체명"].apply(lambda x: normalize_comp_name(x, core_only=False))
            df_s1["_norm_core"] = df_s1["업체명"].apply(lambda x: normalize_comp_name(x, core_only=True))
            df_s1["_item_clean"] = df_s1["심사항목"].astype(str).str.strip()
            if "제출일시" in df_s1.columns:
                df_s1 = df_s1.sort_values("제출일시")
            df_dedup = df_s1.drop_duplicates(subset=["_norm_exact", "_item_clean"], keep="last")

            for norm_k, grp in df_dedup.groupby("_norm_exact"):
                if not norm_k:
                    continue
                total_pts = 0.0
                weak_items = []
                for _, s_row in grp.iterrows():
                    adm_str = str(s_row.get("관리자최종점수", "")).strip()
                    ai_str = str(s_row.get("AI판정결과", "")).strip()
                    target_str = adm_str if adm_str != "" else ai_str
                    m_pt = re.search(r"(\d+(?:\.\d+)?)\s*점", target_str)
                    pt_val = float(m_pt.group(1)) if m_pt else to_float(target_str, 0.0)
                    total_pts += pt_val

                    if any(w in target_str for w in ["부적합", "미흡", "누락", "0점"]):
                        clean_it = re.sub(r"^\[[^\]]+\]\s*\(\d+\)\s*", "", s_row["_item_clean"])
                        weak_items.append(clean_it)

                info_pack = {
                    "score": int(round(min(total_pts, 100.0))),
                    "weak_count": len(weak_items),
                    "weak_items": weak_items
                }
                exact_score_map[norm_k] = info_pack
                core_k = grp["_norm_core"].iloc[0]
                if core_k and core_k not in core_score_map:
                    core_score_map[core_k] = info_pack

        hdr2 = [str(c).replace(" ", "").strip() for c in rows2[0]]
        col_gubun = next((i for i, h in enumerate(hdr2) if "구분" in h), 0)
        col_comp = next((i for i, h in enumerate(hdr2) if "업체" in h), 1)
        col_item = next((i for i, h in enumerate(hdr2) if "품목" in h), 2)
        col_sc2 = next((i for i, h in enumerate(hdr2) if "점수" in h), -1)
        col_res2 = next((i for i, h in enumerate(hdr2) if "결과" in h), -1)
        col_note2 = next((i for i, h in enumerate(hdr2) if "비고" in h), -1)

        temp_list = []
        for r in rows2[1:]:
            if not any(str(x).strip() for x in r):
                continue
            r_pad = list(r) + [""] * max(0, 7 - len(r))
            gubun = str(r_pad[col_gubun]).strip()
            comp = str(r_pad[col_comp]).strip()
            item = str(r_pad[col_item]).strip()
            if not comp:
                continue

            nk_exact = normalize_comp_name(comp, core_only=False)
            nk_core = normalize_comp_name(comp, core_only=True)
            matched = exact_score_map.get(nk_exact) or core_score_map.get(nk_core)

            s2_score_txt = str(r_pad[col_sc2]).strip() if col_sc2 >= 0 else ""
            s2_res_txt = str(r_pad[col_res2]).strip() if col_res2 >= 0 else ""
            s2_note_txt = str(r_pad[col_note2]).strip() if col_note2 >= 0 else ""

            if s2_score_txt != "":
                if s2_score_txt == "미제출":
                    sc_num, sc_disp = -1, "미제출"
                else:
                    sc_num = int(round(to_float(s2_score_txt, -1)))
                    sc_disp = str(sc_num) if sc_num >= 0 else "미제출"
                weak_cnt = matched["weak_count"] if matched else 0
                weak_list = matched["weak_items"] if matched else []
            elif matched is not None:
                sc_num = matched["score"]
                sc_disp = str(sc_num)
                weak_cnt = matched["weak_count"]
                weak_list = matched["weak_items"]
            else:
                sc_num, sc_disp = -1, "미제출"
                weak_cnt, weak_list = 0, []

            if s2_res_txt in ["승인", "지도", "등급 외"]:
                grade = s2_res_txt
            else:
                grade = "승인" if sc_num >= 85 else ("지도" if sc_num >= 70 else "등급 외")

            note_final = s2_note_txt if s2_note_txt else ("미제출" if sc_disp == "미제출" else ("복수거래, 거래중지 등 검토" if grade == "등급 외" else ""))
            temp_list.append({
                "_sort_sc": sc_num,
                "구분": gubun,
                "업체명": comp,
                "품목": item,
                "점수": sc_disp,
                "결과": grade,
                "비고": note_final,
                "_weak_cnt": weak_cnt,
                "_weak_list": weak_list
            })

        temp_list.sort(key=lambda x: x["_sort_sc"], reverse=True)
        master_records, under_comp_rows, under_detail_rows = [], [], []

        for i, rec in enumerate(temp_list, start=1):
            master_records.append({
                "NO": i,
                "구분": rec["구분"],
                "업체명": rec["업체명"],
                "품목": rec["품목"],
                "점수": rec["점수"],
                "결과": rec["결과"],
                "비고": rec["비고"]
            })
            if rec["결과"] == "등급 외":
                under_comp_rows.append({
                    "업체명": rec["업체명"],
                    "점수": f"{rec['점수']}점" if rec["점수"] != "미제출" else "미제출",
                    "미비 항목": f"{rec['_weak_cnt']}개" if rec["점수"] != "미제출" else "미제출",
                    "조치": "복수거래, 거래중지 등 검토"
                })
                if rec["_weak_list"]:
                    under_detail_rows.append({
                        "대상 구분": rec["업체명"],
                        "분류": "서류심사 미흡",
                        "미비 사항": ", ".join(rec["_weak_list"])
                    })

        ws_under = next((w for w in ws_list if w.title.strip() == "등급외_미비사항"), None)
        if ws_under is not None:
            u_rows = get_values_formatted(ws_under)
            if len(u_rows) >= 2:
                sheet_uc, sheet_ud = [], []
                hdr_uc = [str(x).strip() for x in u_rows[0][:4]]
                hdr_ud = [str(x).strip() for x in u_rows[0][5:8]] if len(u_rows[0]) >= 8 else []

                for ur in u_rows[1:]:
                    ur_pad = list(ur) + [""] * max(0, 8 - len(ur))
                    if any(str(x).strip() for x in ur_pad[:4]) and len(hdr_uc) == 4:
                        sheet_uc.append(dict(zip(hdr_uc, [str(x).strip() for x in ur_pad[:4]])))
                    if any(str(x).strip() for x in ur_pad[5:8]) and len(hdr_ud) == 3:
                        sheet_ud.append(dict(zip(hdr_ud, [str(x).strip() for x in ur_pad[5:8]])))
                if sheet_uc:
                    under_comp_rows = sheet_uc
                if sheet_ud:
                    under_detail_rows = sheet_ud

        df_master = pd.DataFrame(master_records)
        cnt_ok = int((df_master["결과"] == "승인").sum())
        cnt_guide = int((df_master["결과"] == "지도").sum())
        cnt_out = int((df_master["결과"] == "등급 외").sum())
        cnt_unsub = int((df_master["점수"] == "미제출").sum())
        tot_sup = len(df_master)

        df_grade_sum = pd.DataFrame([
            {"등급": "승인", "점수": "85-100점", "업체수": cnt_ok, "조치": "승인"},
            {"등급": "지도", "점수": "70-84점", "업체수": cnt_guide, "조치": "업체별 개선사항 피드백"},
            {"등급": "등급 외", "점수": "70점미만, 미제출", "업체수": cnt_out, "조치": "복수거래, 거래중지 등 검토"},
            {"등급": "합계", "점수": "-", "업체수": tot_sup, "조치": f"제출 {tot_sup - cnt_unsub}개사 / 미제출 {cnt_unsub}개사"}
        ])

        return df_master, df_grade_sum, pd.DataFrame(under_comp_rows), pd.DataFrame(under_detail_rows), None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), str(e)


# [5] 심사점수·일정 관리 DB + 수동 KPI + 대시보드 특이사항 보드(표시사항 메모 & 클레임/부적합 LOT 연동)
AUDIT_COLS = ["고유ID", "심사일자", "심사명", "진행현황", "점수", "비고", "수정일시"]
MANUAL_KPI_TAB = "수동KPI_설정"
MANUAL_KPI_COLS = [
    "kpi_key", "target_text", "actual_text", "sub_badge",
    "target_num", "actual_num", "signal", "notes_title", "notes_joined", "updated_at"
]
SPECIAL_BOARD_TAB = "대시보드_특이사항_보드"


def fetch_audit_and_manual_db(creds, sheet_urls_map):
    empty_sched = pd.DataFrame(columns=AUDIT_COLS)
    sh, _ = open_sheet_threadsafe(creds, sheet_urls_map, "audit_db")
    if sh is None:
        return empty_sched, {}, None, None, None

    try:
        ws_list = api_call_with_retry(sh.worksheets)
        ws_sched = ws_list[0] if ws_list else None
        df_sched = empty_sched.copy()

        if ws_sched is not None:
            rows = get_values_formatted(ws_sched)
            if len(rows) >= 2:
                hdr = [str(c).strip() for c in rows[0]]
                recs = []
                for r in rows[1:]:
                    if not any(str(x).strip() for x in r):
                        continue
                    r_pad = [str(x).strip() for x in r] + [""] * max(0, len(hdr) - len(r))
                    item = dict(zip(hdr, r_pad[:len(hdr)]))
                    dt_parsed = pd.to_datetime(item.get("심사일자", ""), errors="coerce")
                    dt_norm = dt_parsed.strftime("%Y-%m-%d") if pd.notna(dt_parsed) else item.get("심사일자", "")
                    st_val = item.get("진행현황", "심사준비중")
                    if st_val not in AUDIT_STATUS_LIST:
                        st_val = "심사준비중"
                    recs.append({
                        "고유ID": item.get("고유ID", "") or str(uuid.uuid4())[:8],
                        "심사일자": dt_norm,
                        "심사명": item.get("심사명", ""),
                        "진행현황": st_val,
                        "점수": item.get("점수", ""),
                        "비고": item.get("비고", ""),
                        "수정일시": item.get("수정일시", "")
                    })
                if recs:
                    df_sched = pd.DataFrame(recs).sort_values("심사일자", ascending=True).reset_index(drop=True)

        saved_manual = {}
        ws_manual = next((w for w in ws_list if w.title.strip() == MANUAL_KPI_TAB), None)
        if ws_manual is not None:
            m_rows = get_values_formatted(ws_manual)
            if len(m_rows) >= 2:
                m_hdr = [str(c).strip() for c in m_rows[0]]
                for mr in m_rows[1:]:
                    if not any(str(x).strip() for x in mr):
                        continue
                    mr_pad = [str(x).strip() for x in mr] + [""] * max(0, len(m_hdr) - len(mr))
                    md = dict(zip(m_hdr, mr_pad[:len(m_hdr)]))
                    k_key = md.get("kpi_key", "")
                    if k_key in DEFAULT_MANUAL_KPIS:
                        notes_raw = md.get("notes_joined", "")
                        act_txt = md.get("actual_text", DEFAULT_MANUAL_KPIS[k_key]["actual_text"])
                        saved_manual[k_key] = {
                            "target_text": md.get("target_text", DEFAULT_MANUAL_KPIS[k_key]["target_text"]),
                            "actual_text": act_txt,
                            "compact_val": act_txt.split(",")[0].strip() if act_txt else DEFAULT_MANUAL_KPIS[k_key]["compact_val"],
                            "sub_badge": md.get("sub_badge", DEFAULT_MANUAL_KPIS[k_key]["sub_badge"]),
                            "target_num": to_float(md.get("target_num"), DEFAULT_MANUAL_KPIS[k_key]["target_num"]),
                            "actual_num": to_float(md.get("actual_num"), DEFAULT_MANUAL_KPIS[k_key]["actual_num"]),
                            "signal": md.get("signal", DEFAULT_MANUAL_KPIS[k_key]["signal"]),
                            "notes_title": md.get("notes_title", DEFAULT_MANUAL_KPIS[k_key]["notes_title"]),
                            "notes": [x.strip() for x in notes_raw.split("||") if x.strip()] if notes_raw else list(DEFAULT_MANUAL_KPIS[k_key]["notes"])
                        }

        loaded_lbl_memo = None
        loaded_clm_issues = None
        ws_sp = next((w for w in ws_list if w.title.strip() == SPECIAL_BOARD_TAB), None)
        if ws_sp is not None:
            sp_rows = get_values_formatted(ws_sp)
            if len(sp_rows) >= 2:
                for sr in sp_rows[1:]:
                    if len(sr) >= 2:
                        b_key = str(sr[0]).strip()
                        b_val = str(sr[1]).strip()
                        if b_key == "label_memo" and b_val:
                            loaded_lbl_memo = b_val
                        elif b_key == "claim_issues_json" and b_val:
                            try:
                                parsed_json = json.loads(b_val)
                                if isinstance(parsed_json, list):
                                    loaded_clm_issues = parsed_json
                            except Exception:
                                pass

        return df_sched, saved_manual, loaded_lbl_memo, loaded_clm_issues, None
    except Exception as e:
        return empty_sched, {}, None, None, f"[심사점수 및 일정 관리 DB] {e}"


def save_audit_schedule_df_to_sheet(df_sched: pd.DataFrame):
    creds, auth_err = build_google_credentials()
    if creds is None:
        return False, auth_err
    sheet_urls_map = dict(st.secrets["sheet_urls"]) if "sheet_urls" in st.secrets else {}
    sh, err = open_sheet_threadsafe(creds, sheet_urls_map, "audit_db")
    if sh is None:
        return False, f"'심사점수 및 일정 관리 DB' 시트를 열 수 없습니다: {err}"

    try:
        ws_sched = api_call_with_retry(sh.get_worksheet, 0)
        df_clean = df_sched.copy()
        for c in AUDIT_COLS:
            if c not in df_clean.columns:
                df_clean[c] = ""
        df_clean = df_clean[AUDIT_COLS].fillna("").sort_values("심사일자", ascending=True).reset_index(drop=True)
        payload = [AUDIT_COLS] + df_clean.astype(str).values.tolist()
        api_call_with_retry(ws_sched.clear)
        safe_ws_update(ws_sched, payload)

        if BUNDLE_KEY in st.session_state:
            st.session_state[BUNDLE_KEY]["df_audit_sched"] = df_clean
        st.cache_data.clear()
        return True, "심사 일정 및 진행현황이 구글 시트에 저장되었습니다."
    except Exception as e:
        return False, f"시트 저장 실패: {e}"


def save_manual_kpi_to_sheet(kpi_key: str, kpi_info: dict):
    creds, auth_err = build_google_credentials()
    if creds is None:
        return False, auth_err
    sheet_urls_map = dict(st.secrets["sheet_urls"]) if "sheet_urls" in st.secrets else {}
    sh, err = open_sheet_threadsafe(creds, sheet_urls_map, "audit_db")
    if sh is None:
        return False, f"'심사점수 및 일정 관리 DB' 시트를 열 수 없습니다: {err}"

    try:
        ws_list = api_call_with_retry(sh.worksheets)
        ws_manual = next((w for w in ws_list if w.title.strip() == MANUAL_KPI_TAB), None)
        if ws_manual is None:
            ws_manual = api_call_with_retry(sh.add_worksheet, title=MANUAL_KPI_TAB, rows=30, cols=12)

        all_manual = st.session_state["manual_kpis"]
        kpi_info["compact_val"] = str(kpi_info.get("actual_text", "")).split(",")[0].strip()
        all_manual[kpi_key] = kpi_info
        now_s = now_kst().strftime("%Y-%m-%d %H:%M:%S")

        payload = [MANUAL_KPI_COLS]
        for k, v in all_manual.items():
            payload.append([
                str(k),
                str(v.get("target_text", "")),
                str(v.get("actual_text", "")),
                str(v.get("sub_badge", "")),
                str(v.get("target_num", 0.0)),
                str(v.get("actual_num", 0.0)),
                str(v.get("signal", "green")),
                str(v.get("notes_title", "")),
                "||".join(v.get("notes", [])),
                now_s
            ])
        api_call_with_retry(ws_manual.clear)
        safe_ws_update(ws_manual, payload)

        if BUNDLE_KEY in st.session_state:
            st.session_state[BUNDLE_KEY]["saved_manual_kpis"][kpi_key] = kpi_info
        st.cache_data.clear()
        return True, "구글 시트에 영구 저장되었습니다."
    except Exception as e:
        return False, f"시트 저장 실패(현재 화면에는 반영됨): {e}"


def save_special_boards_to_sheet(label_memo_str: str, claim_issues_list: list):
    """메인 관제판 '표시사항 특이사항 메모란' 및 '클레임·부적합 특이사항 리스트' 시트 영구 저장"""
    st.session_state["label_special_memo"] = label_memo_str
    st.session_state["claim_special_list"] = claim_issues_list

    creds, auth_err = build_google_credentials()
    if creds is None:
        return False, auth_err
    sheet_urls_map = dict(st.secrets["sheet_urls"]) if "sheet_urls" in st.secrets else {}
    sh, err = open_sheet_threadsafe(creds, sheet_urls_map, "audit_db")
    if sh is None:
        return False, f"시트 열기 실패(현재 세션에는 반영됨): {err}"

    try:
        ws_list = api_call_with_retry(sh.worksheets)
        ws_sp = next((w for w in ws_list if w.title.strip() == SPECIAL_BOARD_TAB), None)
        if ws_sp is None:
            ws_sp = api_call_with_retry(sh.add_worksheet, title=SPECIAL_BOARD_TAB, rows=20, cols=4)

        now_s = now_kst().strftime("%Y-%m-%d %H:%M:%S")
        payload = [
            ["항목키", "저장내용", "수정일시"],
            ["label_memo", str(label_memo_str), now_s],
            ["claim_issues_json", json.dumps(claim_issues_list, ensure_ascii=False), now_s]
        ]
        api_call_with_retry(ws_sp.clear)
        safe_ws_update(ws_sp, payload)

        if BUNDLE_KEY in st.session_state:
            st.session_state[BUNDLE_KEY]["saved_label_memo"] = label_memo_str
            st.session_state[BUNDLE_KEY]["saved_claim_issues"] = claim_issues_list
        st.cache_data.clear()
        return True, "특이사항 내역이 구글 시트에 영구 저장되었습니다."
    except Exception as e:
        return False, f"시트 저장 실패(현재 화면에는 반영됨): {e}"


# [6] 표시사항 현황 & [7] 원자재 표시사항 DB
def parse_factual_date(row_dict: dict):
    for col_key in ["등록일", "최종수정일", "완료일"]:
        raw = row_dict.get(col_key, "")
        if raw is None:
            continue
        s = str(raw).strip()
        if not s or "###" in s:
            continue
        if re.match(r"^\d{5}(\.\d+)?$", s):
            try:
                dt = datetime(1899, 12, 30) + timedelta(days=float(s))
                return dt.strftime("%Y-%m-%d"), f"{dt.year}년", f"{dt.month}월", dt.year, dt.month
            except Exception:
                pass
        dt_parsed = pd.to_datetime(s, errors="coerce")
        if pd.notna(dt_parsed) and 2018 <= dt_parsed.year <= 2035:
            return dt_parsed.strftime("%Y-%m-%d"), f"{dt_parsed.year}년", f"{dt.month}월", int(dt_parsed.year), int(dt_parsed.month)

    return "원본날짜깨짐(#######)", "날짜미상", "날짜미상", 0, 0


def classify_label_status(status_str: str) -> str:
    s = str(status_str).strip()
    if s == "식품안전팀 검토중":
        return "식품안전팀 검토중"
    if s in ["개시/준비", "보류", "검토/개시", ""]:
        return "제외(개시/준비·보류)"
    return "검토완료(확인필)"


def fetch_label_status_sheet(creds, sheet_urls_map):
    sh, err = open_sheet_threadsafe(creds, sheet_urls_map, "label_status")
    if sh is None:
        return pd.DataFrame(), err
    try:
        ws = api_call_with_retry(sh.get_worksheet, 0)
        rows = get_values_unformatted(ws)
        if len(rows) < 2:
            return pd.DataFrame(), "표시사항 현황 시트에 데이터가 없습니다."
        headers = [str(h).strip() for h in rows[0]]
        data = []
        for r in rows[1:]:
            if not any(str(x).strip() != "" for x in r):
                continue
            r_pad = [str(x).strip() for x in r] + [""] * max(0, len(headers) - len(r))
            item = dict(zip(headers, r_pad[:len(headers)]))
            dt_str, yr_str, mo_str, yr_num, mo_num = parse_factual_date(item)
            item["등록일자"] = dt_str
            item["등록연도"] = yr_str
            item["등록월"] = mo_str
            item["_yr_num"] = yr_num
            item["_mo_num"] = mo_num
            item["분류"] = classify_label_status(item.get("상태", ""))
            data.append(item)
        return pd.DataFrame(data), None
    except Exception as e:
        return pd.DataFrame(), str(e)


def fetch_raw_material_db_sheet(creds, sheet_urls_map):
    sh, err = open_sheet_threadsafe(creds, sheet_urls_map, "raw_label_db")
    if sh is None:
        return pd.DataFrame(), 0, err
    df_submitted = pd.DataFrame()
    total_master_count = 0
    try:
        ws_list = api_call_with_retry(sh.worksheets)
        if ws_list:
            rows_sub = get_values_formatted(ws_list[0])
            if len(rows_sub) >= 2:
                headers = [str(h).strip() for h in rows_sub[0]]
                data = [dict(zip(headers, (list(r) + [""] * len(headers))[:len(headers)])) for r in rows_sub[1:] if any(r)]
                df_submitted = pd.DataFrame(data)
        ws_master = next((w for w in ws_list if w.title.strip() == "전체 원재료 명단"), None)
        if ws_master is not None:
            rows_m = get_values_formatted(ws_master)
            total_master_count = max(len([r for r in rows_m[1:] if any(r)]), 0)
    except Exception:
        pass
    return df_submitted, total_master_count, None


# ==============================================================================
# 5. 병렬 데이터 로딩 엔진 (5분 캐시 + 호출 분산 + 마스터 제품명 통합)
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def load_all_sheets_parallel(today_cache_key: str) -> dict:
    creds, auth_err = build_google_credentials()
    sheet_urls_map = dict(st.secrets["sheet_urls"]) if "sheet_urls" in st.secrets else {}
    cur_kst = now_kst()

    empty_proc = {
        "rt_today": None, "rt_yest": None, "milk_date": "-", "ferm_date": "-",
        "df_milk_pack": pd.DataFrame(), "df_ferm_pack": pd.DataFrame(),
        "soy_default_tab": "-", "soy_tabs_map": {},
        "df_soy_blocks": pd.DataFrame(), "df_soy_hourly": pd.DataFrame(),
        "df_rt_hist_p": pd.DataFrame(), "df_rt_hist_c": pd.DataFrame(),
        "df_dairy_hist_p": pd.DataFrame(), "df_dairy_hist_c": pd.DataFrame(),
        "df_soy_hist": pd.DataFrame(),
        "fsk_products": [], "master_products": []
    }

    if creds is None:
        return {
            "df_cost": pd.DataFrame(),
            "cost_targets": {"부문": 1.54, "식품안전팀": 1.0, "품질관리팀": 0.54},
            "df_claim_trend": pd.DataFrame(),
            "df_claim_cat": pd.DataFrame(),
            "proc_data": empty_proc,
            "df_sup_master": pd.DataFrame(),
            "df_sup_grade": pd.DataFrame(),
            "df_sup_under_c": pd.DataFrame(),
            "df_sup_under_d": pd.DataFrame(),
            "df_audit_sched": pd.DataFrame(columns=AUDIT_COLS),
            "saved_manual_kpis": {},
            "saved_label_memo": None,
            "saved_claim_issues": None,
            "df_label_status": pd.DataFrame(),
            "df_raw_sub": pd.DataFrame(),
            "raw_master_cnt": 0,
            "errors": [auth_err],
            "loaded_at": cur_kst.strftime("%Y. %m. %d %H:%M:%S (KST)"),
            "loaded_date": today_cache_key
        }

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_cost = ex.submit(fetch_cost_sheet, creds, sheet_urls_map)
        f_claim = ex.submit(fetch_claim_sheet, creds, sheet_urls_map)
        f_rt = ex.submit(fetch_process_rt_sheet, creds, sheet_urls_map)
        f_milk = ex.submit(fetch_process_milk_sheet, creds, sheet_urls_map)
        f_soy = ex.submit(fetch_process_soy_sheet, creds, sheet_urls_map)
        f_sup = ex.submit(fetch_supplier_sheet, creds, sheet_urls_map)
        f_audit = ex.submit(fetch_audit_and_manual_db, creds, sheet_urls_map)
        f_lbl = ex.submit(fetch_label_status_sheet, creds, sheet_urls_map)
        f_raw = ex.submit(fetch_raw_material_db_sheet, creds, sheet_urls_map)

        df_cost, cost_targets, err_cost = f_cost.result()
        df_claim_trend, df_claim_cat, err_claim = f_claim.result()
        rt_today, rt_yest, df_rt_hp, df_rt_hc, fsk_prods, err_rt = f_rt.result()
        df_milk, df_ferm, milk_dt, ferm_dt, df_dy_hp, df_dy_hc, dairy_prods, err_milk = f_milk.result()
        soy_def_tab, soy_map, df_soy_b, df_soy_h, df_soy_hist, err_soy = f_soy.result()
        df_sup_m, df_sup_g, df_sup_uc, df_sup_ud, err_sup = f_sup.result()
        df_audit_sched, saved_manual_kpis, saved_lbl_memo, saved_clm_issues, err_audit = f_audit.result()
        df_lbl, err_lbl = f_lbl.result()
        df_raw_sub, raw_m_cnt, err_raw = f_raw.result()

    master_prods = []
    seen_norm = set()

    def add_prod_unique(p_str: str):
        ps = str(p_str or "").strip()
        if not ps or ps in ["-", "(비가동)", "(제품명 미기입)"]:
            return
        nk = clean_product_for_match(ps)
        if nk and nk not in seen_norm:
            seen_norm.add(nk)
            master_prods.append(ps)

    for fp in fsk_prods:
        add_prod_unique(fp)
    for dp in dairy_prods:
        add_prod_unique(dp)
    if not df_rt_hp.empty and "제품명" in df_rt_hp.columns:
        for rp in df_rt_hp["제품명"].dropna().tolist():
            add_prod_unique(rp)
    if not df_dy_hp.empty and "제품명" in df_dy_hp.columns:
        for dhp in df_dy_hp["제품명"].dropna().tolist():
            add_prod_unique(dhp)

    errors = []
    for label_nm, er in [
        ("원가절감", err_cost), ("클레임", err_claim), ("협력업체", err_sup),
        ("표시사항 현황", err_lbl), ("원자재 DB", err_raw)
    ]:
        if er:
            errors.append(f"[{label_nm}] {er}")
    for p_er in [err_rt, err_milk, err_soy, err_audit]:
        if p_er:
            errors.append(p_er)

    done_kst = now_kst()
    return {
        "df_cost": df_cost,
        "cost_targets": cost_targets,
        "df_claim_trend": df_claim_trend,
        "df_claim_cat": df_claim_cat,
        "proc_data": {
            "rt_today": rt_today,
            "rt_yest": rt_yest,
            "milk_date": milk_dt,
            "ferm_date": ferm_dt,
            "df_milk_pack": df_milk,
            "df_ferm_pack": df_ferm,
            "soy_default_tab": soy_def_tab,
            "soy_tabs_map": soy_map,
            "df_soy_blocks": df_soy_b,
            "df_soy_hourly": df_soy_h,
            "df_rt_hist_p": df_rt_hp,
            "df_rt_hist_c": df_rt_hc,
            "df_dairy_hist_p": df_dy_hp,
            "df_dairy_hist_c": df_dy_hc,
            "df_soy_hist": df_soy_hist,
            "fsk_products": fsk_prods,
            "master_products": master_prods
        },
        "df_sup_master": df_sup_m,
        "df_sup_grade": df_sup_g,
        "df_sup_under_c": df_sup_uc,
        "df_sup_under_d": df_sup_ud,
        "df_audit_sched": df_audit_sched,
        "saved_manual_kpis": saved_manual_kpis,
        "saved_label_memo": saved_lbl_memo,
        "saved_claim_issues": saved_clm_issues,
        "df_label_status": df_lbl,
        "df_raw_sub": df_raw_sub,
        "raw_master_cnt": raw_m_cnt,
        "errors": errors,
        "loaded_at": done_kst.strftime("%Y. %m. %d %H:%M:%S (KST)"),
        "loaded_date": done_kst.strftime("%Y-%m-%d")
    }


def trigger_manual_sync():
    st.cache_data.clear()
    st.session_state.pop(BUNDLE_KEY, None)


today_kst_str = now_kst().strftime("%Y-%m-%d")
if BUNDLE_KEY not in st.session_state or st.session_state[BUNDLE_KEY].get("loaded_date") != today_kst_str:
    loading_box = st.empty()
    loading_box.markdown(
        """
        <div style="margin-top: 18px; padding: 16px 20px; background: #FFFFFF;
                    border: 1px solid #DCE4EE; border-left: 5px solid #00205B;
                    border-radius: 10px; font-size: 14.5px; font-weight: 700; color: #00205B;">
            ⏳ 연세유업 품질안전부문 실시간 현황 및 공정 이력 DB를 불러오는 중입니다...
        </div>
        """,
        unsafe_allow_html=True
    )
    loaded_bundle = load_all_sheets_parallel(today_kst_str)
    for mk_k, mk_val in loaded_bundle.get("saved_manual_kpis", {}).items():
        if mk_k in st.session_state["manual_kpis"]:
            st.session_state["manual_kpis"][mk_k].update(mk_val)
    if loaded_bundle.get("saved_label_memo"):
        st.session_state["label_special_memo"] = loaded_bundle["saved_label_memo"]
    if loaded_bundle.get("saved_claim_issues"):
        st.session_state["claim_special_list"] = loaded_bundle["saved_claim_issues"]
    st.session_state[BUNDLE_KEY] = loaded_bundle
    loading_box.empty()

bundle = st.session_state[BUNDLE_KEY]
df_cost = bundle["df_cost"]
cost_targets = bundle["cost_targets"]
df_claim_trend = bundle["df_claim_trend"]
df_claim_cat = bundle["df_claim_cat"]
proc_data = bundle["proc_data"]
df_sup_master = bundle["df_sup_master"]
df_sup_grade = bundle["df_sup_grade"]
df_sup_under_c = bundle["df_sup_under_c"]
df_sup_under_d = bundle["df_sup_under_d"]
df_audit_sched = bundle["df_audit_sched"]
df_label_status = bundle["df_label_status"]
df_raw_sub = bundle["df_raw_sub"]
raw_master_cnt = bundle["raw_master_cnt"]
all_load_errors = bundle["errors"]
# ============================ [PART 2 / 4 끝] ============================
# ==============================================================================
# [PART 3 / 4 - 교체본] QUALITY ONE 스타일 카드 헤더 · 사이드바 · 실시간 통합 대시보드
# ==============================================================================

def render_card_header(title_txt: str, target_view: str, btn_key: str, link_label: str = "상세보기 ›"):
    """빨간 버튼 박스 대신 좌측 타이포그래피 제목 + 우측 슬림 이동 링크 배치"""
    hc1, hc2 = st.columns([3.4, 1.1])
    with hc1:
        st.markdown(f"<div class='qo-card-title'>{html.escape(title_txt)}</div>", unsafe_allow_html=True)
    with hc2:
        st.button(link_label, key=btn_key, type="secondary", use_container_width=True, on_click=set_view, args=(target_view,))
    st.markdown("<div class='qo-divider'></div>", unsafe_allow_html=True)


def draw_mini_bar(target_val: float, actual_val: float, suffix: str = "", bar_labels=("목표", "실적")):
    def fmt_num(v: float) -> str:
        return f"{int(v)}{suffix}" if float(v).is_integer() else f"{v}{suffix}"

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[bar_labels[0]], y=[target_val], text=[fmt_num(target_val)],
        textposition="outside", cliponaxis=False,
        marker_color="#E5E7EB", width=0.32,
        textfont=dict(color="#6B7280", size=11.5, family="Pretendard, Malgun Gothic")
    ))
    fig.add_trace(go.Bar(
        x=[bar_labels[1]], y=[actual_val], text=[fmt_num(actual_val)],
        textposition="outside", cliponaxis=False,
        marker_color="#2563EB", width=0.32,
        textfont=dict(color="#1D4ED8", size=12, family="Pretendard, Malgun Gothic")
    ))
    try:
        fig.update_traces(marker_cornerradius=5)
    except Exception:
        pass

    max_y = max(target_val, actual_val) * 1.36 if max(target_val, actual_val) > 0 else 10
    fig.update_layout(
        height=148,
        margin=dict(l=8, r=8, t=22, b=16),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(size=11.5, color="#4B5563")),
        yaxis=dict(showgrid=False, zeroline=True, zerolinecolor="#F2F4F7", showticklabels=False, range=[0, max_y])
    )
    return fig


def draw_compact_ppm_chart(df_trend: pd.DataFrame, act_line: list, fc_line: list, last_i: int):
    fig = go.Figure()
    if not df_trend.empty:
        rec_flags = df_trend["_기록여부"].tolist() if "_기록여부" in df_trend.columns else [True] * len(df_trend)
        y_vals = [v if flag else None for v, flag in zip(df_trend["2026년_PPM"], rec_flags)]

        fig.add_trace(go.Scatter(
            x=df_trend["월"], y=y_vals,
            name="실적 PPM", mode="lines+markers+text",
            text=[f"{v:.2f}" if (v is not None and idx == last_i) else "" for idx, v in enumerate(y_vals)],
            textposition="top center",
            line=dict(color="#2563EB", width=2.4),
            marker=dict(size=5.5, color="#2563EB"),
            fill="tozeroy", fillcolor="rgba(37, 99, 235, 0.06)"
        ))
        fig.add_trace(go.Scatter(
            x=df_trend["월"], y=df_trend["목표_PPM"],
            name="목표(1.12)", mode="lines",
            line=dict(color="#EF4444", width=1.5, dash="dash")
        ))
        if 0 <= last_i < 11:
            fig.add_trace(go.Scatter(
                x=df_trend["월"], y=fc_line,
                name="예상 추세", mode="lines+markers",
                line=dict(color="#93C5FD", width=1.8, dash="dot"),
                marker=dict(size=4.5, color="#60A5FA")
            ))

    max_ppm = max(float(df_trend["2026년_PPM"].max()) if not df_trend.empty else 1.5, 1.4) * 1.22
    fig.update_layout(
        height=158,
        margin=dict(l=26, r=10, t=6, b=22),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=0.98, xanchor="right", x=1, font=dict(size=10.5, color="#6B7280")),
        xaxis=dict(showgrid=False, tickfont=dict(size=10.5, color="#6B7280")),
        yaxis=dict(showgrid=True, gridcolor="#F3F4F6", range=[0, max_ppm], tickfont=dict(size=10.5, color="#6B7280"))
    )
    return fig


def get_active_audit_summary(df_sched: pd.DataFrame, today_str: str) -> dict:
    if df_sched is None or df_sched.empty:
        return {
            "has_data": False,
            "mode": "empty",
            "banner_text": "등록된 심사 일정이 없습니다",
            "status": "일정 대기",
            "pct": 0,
            "color": "#9CA3AF",
            "icon": "",
            "row": None
        }

    today_dt = pd.to_datetime(today_str).date()
    df_w = df_sched.copy()
    df_w["_dt"] = pd.to_datetime(df_w["심사일자"], errors="coerce").dt.date

    today_rows = df_w[df_w["_dt"] == today_dt]
    if not today_rows.empty:
        r = today_rows.iloc[0]
        st_nm = r["진행현황"] if r["진행현황"] in AUDIT_STATUS_CONFIG else "심사준비중"
        cfg = AUDIT_STATUS_CONFIG[st_nm]
        return {
            "has_data": True,
            "mode": "today",
            "banner_text": f"[금일 심사 · {r['심사일자'][5:]}] {r['심사명']}",
            "status": st_nm,
            "pct": cfg["pct"],
            "color": cfg["color"],
            "icon": "",
            "row": r
        }

    in_prog_rows = df_w[df_w["진행현황"].isin(["심사중", "서류심사중", "현장심사중"])]
    if not in_prog_rows.empty:
        r = in_prog_rows.iloc[0]
        st_nm = r["진행현황"]
        cfg = AUDIT_STATUS_CONFIG[st_nm]
        dt_short = str(r["심사일자"])[5:] if len(str(r["심사일자"])) >= 10 else str(r["심사일자"])
        return {
            "has_data": True,
            "mode": "in_progress",
            "banner_text": f"[진행 중 · {dt_short}] {r['심사명']}",
            "status": st_nm,
            "pct": cfg["pct"],
            "color": cfg["color"],
            "icon": "",
            "row": r
        }

    future_rows = df_w[df_w["_dt"].notna() & (df_w["_dt"] > today_dt)].sort_values("_dt", ascending=True)
    if not future_rows.empty:
        r = future_rows.iloc[0]
        d_left = (r["_dt"] - today_dt).days
        st_nm = r["진행현황"] if r["진행현황"] in AUDIT_STATUS_CONFIG else "심사준비중"
        cfg = AUDIT_STATUS_CONFIG[st_nm]
        return {
            "has_data": True,
            "mode": "upcoming",
            "banner_text": f"[차기 심사 · D-{d_left}] {r['심사명']} ({r['심사일자'][5:]})",
            "status": st_nm,
            "pct": cfg["pct"],
            "color": cfg["color"],
            "icon": "",
            "row": r
        }

    past_rows = df_w.sort_values("심사일자", ascending=False)
    r = past_rows.iloc[0]
    st_nm = r["진행현황"] if r["진행현황"] in AUDIT_STATUS_CONFIG else "심사종료"
    cfg = AUDIT_STATUS_CONFIG[st_nm]
    dt_short = str(r["심사일자"])[5:] if len(str(r["심사일자"])) >= 10 else str(r["심사일자"])
    return {
        "has_data": True,
        "mode": "past",
        "banner_text": f"[최근 완료 · {dt_short}] {r['심사명']}",
        "status": st_nm,
        "pct": cfg["pct"],
        "color": cfg["color"],
        "icon": "",
        "row": r
    }


def render_team_cost_panel(container_col, team_name: str, bar_color: str, target_uk: float):
    act_col = f"{team_name}_실적(만원)"
    std_col = f"{team_name}_기준(만원)"

    with container_col:
        t_sum_man = round(float(df_cost[act_col].sum()), 1) if not df_cost.empty else 0.0
        t_sum_uk = round(t_sum_man / 10000, 2)
        t_target_man = round(target_uk * 10000, 1)
        t_rate = round((t_sum_man / t_target_man) * 100, 1) if t_target_man > 0 else 0.0

        rec_flags = df_cost["_기록여부"].tolist() if "_기록여부" in df_cost.columns else None
        t_act_l, t_fc_l, t_full_l, t_slope, t_mcnt, t_last_i = calc_trend_and_forecast_split(
            df_cost[act_col].tolist(), rec_flags
        )
        t_proj_man = round(t_sum_man + sum(t_full_l[t_last_i + 1:]), 1) if (0 <= t_last_i < 11) else t_sum_man
        t_proj_uk = round(t_proj_man / 10000, 2)
        t_proj_rate = round((t_proj_man / t_target_man) * 100, 1) if t_target_man > 0 else 0.0

        rec_df = df_cost[df_cost["_기록여부"]] if "_기록여부" in df_cost.columns else df_cost[df_cost[act_col] > 0]
        pass_m_cnt = int((rec_df[act_col] >= rec_df[std_col]).sum()) if not rec_df.empty else 0

        status_tag = "목표 순항" if t_proj_man >= t_target_man else "추세 보완 필요"
        st.markdown(f"""
        <div class="forecast-box" style="border-left-color:{bar_color}; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <b style="font-size:15px; color:#111827;">{html.escape(team_name)} (연간 목표 {target_uk}억원)</b>
                <span class="kpi-sub-pill" style="margin-top:0;">{status_tag}</span>
            </div>
            • <b>현재 누적 실적 :</b> <b>{t_sum_man:,.1f} 만원 ({t_sum_uk}억원)</b> — 연간 목표 대비 <b>{t_rate}%</b> 달성 (월 기준 달성: {pass_m_cnt}/{max(t_mcnt, 0)}개월)<br>
            • <b>연말(2월) 추세 예측 :</b> <b>{t_proj_man:,.1f} 만원 ({t_proj_uk}억원 / 예상 {t_proj_rate}%)</b> · 월 기울기 <b>{t_slope:+.1f}만/월</b>
        </div>
        """, unsafe_allow_html=True)

        fig_t = go.Figure()
        fig_t.add_trace(go.Bar(
            x=df_cost["월"], y=df_cost[act_col], name=f"{team_name} 실적",
            marker_color=bar_color,
            text=[f"{v:,.0f}" if v > 0 else "" for v in df_cost[act_col]],
            textposition="outside"
        ))
        fig_t.add_trace(go.Scatter(
            x=df_cost["월"], y=df_cost[std_col], name="팀 월 기준선",
            mode="lines", line=dict(color="#EF4444", width=2.0, dash="dash")
        ))
        fig_t.add_trace(go.Scatter(
            x=df_cost["월"], y=t_act_l, name="실적 추세선",
            mode="lines+markers", line=dict(color="#6366F1", width=2.4)
        ))
        if 0 <= t_last_i < 11:
            fig_t.add_trace(go.Scatter(
                x=df_cost["월"], y=t_fc_l, name="잔여월 예상 추세",
                mode="lines+markers+text",
                text=[f"{v:.0f}" if (v is not None and idx > t_last_i) else "" for idx, v in enumerate(t_fc_l)],
                textposition="top center",
                line=dict(color="#0EA5E9", width=2.4, dash="dot"),
                marker=dict(symbol="diamond", size=7)
            ))
        max_v = max(
            float(df_cost[act_col].max()) if not df_cost.empty else 0.0,
            float(df_cost[std_col].max()) if not df_cost.empty else 0.0,
            max([x for x in t_full_l if x is not None], default=0.0)
        )
        fig_t.update_layout(
            height=350,
            title=f"{team_name} 월별 실적·기준선 및 잔여월 추세 예측 (단위: 만원)",
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            margin=dict(l=20, r=20, t=44, b=26),
            yaxis=dict(range=[0, max_v * 1.25 if max_v > 0 else 1000]),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1)
        )
        st.plotly_chart(fig_t, use_container_width=True)


def render_manual_kpi_editor_section(kpi_key: str, key_suffix: str = ""):
    info = st.session_state["manual_kpis"][kpi_key]
    c_preview, c_edit = st.columns([1.1, 1.35])

    with c_preview:
        st.markdown(f"#### {info['title']} 현재 표시 데이터")
        st.markdown(f"""
        <div class="forecast-box">
            • <b>목표 :</b> {html.escape(info['target_text'])}<br>
            • <b>실적 :</b> {html.escape(info['actual_text'])}<br>
            • <b>보조 요약 :</b> {html.escape(info['sub_badge'])}
        </div>
        """, unsafe_allow_html=True)
        if info["has_chart"]:
            st.plotly_chart(
                draw_mini_bar(float(info["target_num"]), float(info["actual_num"]), suffix=info["suffix"]),
                use_container_width=True,
                key=f"chart_prev_{kpi_key}_{key_suffix}"
            )
        st.markdown(f"##### {info['notes_title']}")
        for line in info["notes"]:
            st.write(f"- {line}")

    with c_edit:
        st.markdown("#### 수치 및 세부 내역 수정 (시트 영구 저장)")
        with st.form(key=f"form_{kpi_key}_{key_suffix}"):
            new_t_txt = st.text_input("목표 표시 문구", value=info["target_text"])
            new_a_txt = st.text_input("실적 표시 문구", value=info["actual_text"])
            new_badge = st.text_input("하단 배지 문구", value=info["sub_badge"])

            sig_opts = ["green", "yellow", "red", "gray"]
            sig_labels = {"green": "양호 (초록)", "yellow": "주의 (노랑)", "red": "경고 (빨강)", "gray": "대기 (회색)"}
            new_sig = st.selectbox(
                "신호등 상태 선택",
                sig_opts,
                index=sig_opts.index(info["signal"]) if info["signal"] in sig_opts else 0,
                format_func=lambda x: sig_labels[x]
            )

            if info["has_chart"]:
                nc1, nc2 = st.columns(2)
                with nc1:
                    new_t_num = st.number_input("그래프 목표 숫자", value=float(info["target_num"]), step=0.1)
                with nc2:
                    new_a_num = st.number_input("그래프 실적 숫자", value=float(info["actual_num"]), step=0.1)
            else:
                new_t_num, new_a_num = info["target_num"], info["actual_num"]

            new_notes_title = st.text_input("세부 메모 소제목", value=info["notes_title"])
            new_notes_raw = st.text_area("세부 항목 (줄바꿈으로 구분)", value="\n".join(info["notes"]), height=120)

            if st.form_submit_button("변경사항 시트 영구 저장"):
                updated_item = {
                    **info,
                    "target_text": new_t_txt.strip(),
                    "actual_text": new_a_txt.strip(),
                    "compact_val": new_a_txt.split(",")[0].strip(),
                    "sub_badge": new_badge.strip(),
                    "signal": new_sig,
                    "target_num": float(new_t_num),
                    "actual_num": float(new_a_num),
                    "notes_title": new_notes_title.strip(),
                    "notes": [ln.strip() for ln in new_notes_raw.splitlines() if ln.strip()]
                }
                st.session_state["manual_kpis"][kpi_key] = updated_item
                ok_save, msg_save = save_manual_kpi_to_sheet(kpi_key, updated_item)
                if ok_save:
                    st.success(msg_save)
                else:
                    st.warning(msg_save)
                st.rerun()


# ==============================================================================
# 공정 현황 탭별 지난 이력 조회기 & 클레임 로트 역추적 렌더러
# ==============================================================================
def render_rt_history_section(df_rt_hp: pd.DataFrame, df_rt_hc: pd.DataFrame):
    st.markdown("---")
    st.subheader("[누적 이력 DB] 지난 상온 공정관리 일보 날짜별 조회")
    if df_rt_hp.empty:
        st.info("아직 '_이력DB_상온생산' 숨김 탭에 누적된 과거 이력이 없습니다.")
        return

    date_pairs = (
        df_rt_hp[["생산일자", "원본탭명"]]
        .drop_duplicates()
        .sort_values("생산일자", ascending=False)
        .values.tolist()
    )
    opt_labels = [f"{d} (원본탭: {t})" for d, t in date_pairs]
    sel_i = st.selectbox("조회할 과거 생산일자 선택 (최신순)", range(len(opt_labels)), format_func=lambda i: opt_labels[i], key="sel_rt_hist_dt")
    sel_dt, sel_tab = date_pairs[sel_i]

    sub_p = df_rt_hp[(df_rt_hp["생산일자"] == sel_dt) & (df_rt_hp["원본탭명"] == sel_tab)]
    sub_c = (
        df_rt_hc[(df_rt_hc["생산일자"] == sel_dt) & (df_rt_hc["원본탭명"] == sel_tab)]
        if not df_rt_hc.empty else pd.DataFrame()
    )

    notes_found = []
    for _, rp in sub_p.iterrows():
        s_rem = str(rp.get("멸균특이사항", "")).strip()
        d_mem = str(rp.get("당일전달사항", "")).strip()
        if s_rem and s_rem not in ["-", "이상없음", "없음"]:
            tag = f"[{rp.get('매칭멸균기', '-')}·{rp.get('포장호기', '-')} {rp.get('제품명', '')}] {s_rem}"
            if tag not in notes_found:
                notes_found.append(tag)
        if d_mem and d_mem not in ["-", "없음"]:
            mtag = f"[당일 전달사항] {d_mem}"
            if mtag not in notes_found:
                notes_found.append(mtag)

    if notes_found:
        st.markdown(
            f"<div class='issue-card-warn'><b>[{html.escape(sel_dt)} ({html.escape(sel_tab)})] 기록된 특이사항 ({len(notes_found)}건)</b><br>"
            + "<br>".join([f"• {html.escape(x)}" for x in notes_found]) + "</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(f"<div class='issue-card-ok'><b>[{html.escape(sel_dt)} ({html.escape(sel_tab)})] 특이사항 없이 정상 생산 마감</b></div>", unsafe_allow_html=True)

    hist_p_cols = [
        {"key": "ho", "label": "포장호기", "width": "8%", "align": "center"},
        {"key": "prod", "label": "생산 제품명", "width": "27%", "align": "left"},
        {"key": "exp", "label": "표기 소비기한", "width": "13%", "align": "center"},
        {"key": "time", "label": "포장 확인시간", "width": "11%", "align": "center"},
        {"key": "st", "label": "상태", "width": "10%", "align": "center"},
        {"key": "ster", "label": "매칭 멸균기 · 핵심 CCP", "width": "18%", "align": "center"},
        {"key": "rem", "label": "호기·멸균 특이사항", "width": "13%", "align": "left"}
    ]
    hist_p_rows = []
    for _, rp in sub_p.iterrows():
        st_raw = str(rp.get("모니터링상태", ""))
        if "완료" in st_raw:
            st_disp, st_cls = "확인완료", "cell-green"
        elif "누락" in st_raw:
            st_disp, st_cls = "소비기한 누락", "cell-red"
        else:
            st_disp, st_cls = "확인시간 대기", "cell-yellow"

        rem_v = str(rp.get("멸균특이사항", "이상없음")).strip() or "이상없음"
        ster_sum = f"{rp.get('매칭멸균기', '-')} | {rp.get('멸균핵심수치_요약', '-')}"
        hist_p_rows.append({
            "ho": {"text": rp.get("포장호기", "-"), "cls": ""},
            "prod": {"text": rp.get("제품명", "-"), "cls": ""},
            "exp": {"text": rp.get("표기소비기한_원문", "-"), "cls": "cell-green" if st_cls == "cell-green" else st_cls},
            "time": {"text": rp.get("포장확인시간", "-"), "cls": st_cls},
            "st": {"text": st_disp, "cls": st_cls},
            "ster": {"text": ster_sum, "cls": "cell-green" if rp.get("매칭멸균기", "-") != "-" else ""},
            "rem": {"text": rem_v, "cls": "cell-yellow" if rem_v not in ["이상없음", "없음", "-"] else "cell-green"}
        })
    st.markdown(render_html_table(hist_p_cols, hist_p_rows), unsafe_allow_html=True)

    if not sub_c.empty:
        with st.expander(f"[{sel_dt}] 멸균기(CCP-1B/2P) 및 포장기(CCP-3B) 세부 모니터링 기록 보기 ({len(sub_c)}건)"):
            st.dataframe(sub_c.drop(columns=["최종백업일시"], errors="ignore"), use_container_width=True, hide_index=True)


def render_dairy_history_section(df_dy_hp: pd.DataFrame, df_dy_hc: pd.DataFrame):
    st.markdown("---")
    st.subheader("[누적 이력 DB] 지난 우유·발효유 포장일보 날짜별 조회")
    if df_dy_hp.empty and df_dy_hc.empty:
        st.info("아직 '_이력DB_유제품포장' 숨김 탭에 누적된 이력이 없습니다.")
        return

    all_dates = sorted(
        list(
            set(df_dy_hp["생산일자"].dropna().tolist() if not df_dy_hp.empty else [])
            | set(df_dy_hc["생산일자"].dropna().tolist() if not df_dy_hc.empty else [])
        ),
        reverse=True
    )
    if not all_dates:
        st.info("조회 가능한 날짜 이력이 없습니다.")
        return

    dc1, dc2 = st.columns([1.3, 1.7])
    with dc1:
        sel_d_dt = st.selectbox("조회할 유제품 생산일자 선택 (최신순)", all_dates, key="sel_dairy_hist_dt")
    with dc2:
        sel_d_line = st.radio("라인 필터", ["전체 (우유+발효유)", "우유", "발효유"], horizontal=True, key="rad_dairy_hist_line")

    sub_dp = df_dy_hp[df_dy_hp["생산일자"] == sel_d_dt] if not df_dy_hp.empty else pd.DataFrame()
    sub_dc = df_dy_hc[df_dy_hc["생산일자"] == sel_d_dt] if not df_dy_hc.empty else pd.DataFrame()

    if sel_d_line != "전체 (우유+발효유)":
        if not sub_dp.empty:
            sub_dp = sub_dp[sub_dp["라인구분"] == sel_d_line]
        if not sub_dc.empty:
            sub_dc = sub_dc[sub_dc["라인구분"] == sel_d_line]

    if not sub_dc.empty:
        ptime_lines, rem_lines = [], []
        for _, cr in sub_dc.iterrows():
            cat = str(cr.get("기록분류", ""))
            if cat == "포장생산시간":
                ptime_lines.append(f"[{cr.get('라인구분', '')}] {cr.get('세부항목', '')} : {cr.get('기록내용_수치', '-')}")
            elif cat == "특이사항":
                rv = str(cr.get("특이사항", "이상없음")).strip()
                if rv and rv not in ["이상없음", "-"]:
                    rem_lines.append(f"[{cr.get('라인구분', '')}] {cr.get('세부항목', '')} : {rv}")

        ptime_html = " &nbsp;|&nbsp; ".join([html.escape(x) for x in ptime_lines]) if ptime_lines else "기록된 포장 생산시간 없음"
        rem_html = "<br>".join([f"• {html.escape(x)}" for x in rem_lines]) if rem_lines else "• 포장 특이사항 없음 (이상없음)"
        box_cls = "issue-card-warn" if rem_lines else "issue-card-ok"
        st.markdown(
            f"<div class='{box_cls}'><b>[{html.escape(sel_d_dt)}] 포장별 생산시간 :</b> {ptime_html}<br>{rem_html}</div>",
            unsafe_allow_html=True
        )

    if not sub_dp.empty:
        dy_hist_cols = [
            {"key": "ln", "label": "라인/유형", "width": "11%", "align": "center"},
            {"key": "prod", "label": "제품명 (용량)", "width": "25%", "align": "left"},
            {"key": "time", "label": "확인시간", "width": "9%", "align": "center"},
            {"key": "tank", "label": "Tank번호", "width": "9%", "align": "center"},
            {"key": "exp", "label": "표기 소비기한", "width": "13%", "align": "center"},
            {"key": "lbl", "label": "표시사항", "width": "7%", "align": "center"},
            {"key": "seal", "label": "접착 및 외관", "width": "11%", "align": "center"},
            {"key": "vol", "label": "용량", "width": "5%", "align": "center"},
            {"key": "sens", "label": "관능", "width": "5%", "align": "center"},
            {"key": "jdg", "label": "판정", "width": "5%", "align": "center"}
        ]
        dy_hist_rows = []
        for _, dr in sub_dp.iterrows():
            jdg_v = str(dr.get("판정", "적합")).strip()
            j_cls = "cell-red" if "부적합" in jdg_v else ("cell-green" if "적합" in jdg_v else "cell-yellow")
            t_v = str(dr.get("확인시간", "-")).strip()
            dy_hist_rows.append({
                "ln": {"text": f"{dr.get('라인구분', '')}\n({dr.get('세부유형', '')})", "cls": ""},
                "prod": {"text": dr.get("제품명", "-"), "cls": ""},
                "time": {"text": t_v, "cls": "cell-green" if t_v not in ["", "-"] else "cell-yellow"},
                "tank": {"text": dr.get("Tank번호", "-"), "cls": ""},
                "exp": {"text": dr.get("표기소비기한_원문", "-"), "cls": "cell-green"},
                "lbl": {"text": dr.get("표시사항", "-"), "cls": "cell-green" if dr.get("표시사항", "-") not in ["", "-"] else ""},
                "seal": {"text": dr.get("접착및외관", "-"), "cls": "cell-green" if dr.get("접착및외관", "-") not in ["", "-"] else ""},
                "vol": {"text": dr.get("제품용량", "-"), "cls": "cell-green" if dr.get("제품용량", "-") not in ["", "-"] else ""},
                "sens": {"text": dr.get("관능", "-"), "cls": "cell-green" if dr.get("관능", "-") not in ["", "-"] else ""},
                "jdg": {"text": jdg_v, "cls": j_cls}
            })
        st.markdown(render_html_table(dy_hist_cols, dy_hist_rows), unsafe_allow_html=True)

    ccp_only = sub_dc[sub_dc["기록분류"] == "CCP모니터링"] if (not sub_dc.empty and "기록분류" in sub_dc.columns) else pd.DataFrame()
    if not ccp_only.empty:
        st.markdown(f"##### [{sel_d_dt}] 살균기(전처리) 및 금속검출기 CCP 검증 모니터링 이력")
        ccp_cols = [
            {"key": "ln", "label": "라인", "width": "10%", "align": "center"},
            {"key": "item", "label": "CCP 설비·항목", "width": "24%", "align": "center"},
            {"key": "time", "label": "확인시간", "width": "12%", "align": "center"},
            {"key": "val", "label": "측정 수치 (유량 · 균질압 · 살균온도 · 냉각온도 등)", "width": "54%", "align": "left"}
        ]
        ccp_rows = [
            {
                "ln": {"text": r.get("라인구분", "-"), "cls": ""},
                "item": {"text": r.get("세부항목", "-"), "cls": ""},
                "time": {"text": r.get("확인시간", "-"), "cls": "cell-green" if str(r.get("확인시간", "-")) not in ["", "-"] else ""},
                "val": {"text": r.get("기록내용_수치", "-"), "cls": "cell-green"}
            }
            for _, r in ccp_only.iterrows()
        ]
        st.markdown(render_html_table(ccp_cols, ccp_rows), unsafe_allow_html=True)


def render_soy_history_section(df_soy_hist: pd.DataFrame):
    st.markdown("---")
    st.subheader("[누적 이력 DB] 지난 두유 배양검사 날짜별 조회")
    if df_soy_hist.empty:
        st.info("아직 '_이력DB_두유배양' 숨김 탭에 누적된 과거 이력이 없습니다.")
        return

    insp_col_nm = "확정검사일_탭기준" if "확정검사일_탭기준" in df_soy_hist.columns else "검사일_표기"
    sc1, sc2 = st.columns([1.2, 1.8])
    with sc1:
        mode_soy = st.radio("조회 날짜 기준", ["검사일(하단 시트탭 날짜) 기준", "실제 생산일자(5일·7일 역산) 기준"], horizontal=True, key="rad_soy_hist_mode")

    if "검사일" in mode_soy and insp_col_nm in df_soy_hist.columns:
        avail_d = sorted(df_soy_hist[insp_col_nm].dropna().unique().tolist(), reverse=True)
        with sc2:
            sel_sd = st.selectbox("조회할 배양검사일(탭 기준) 선택", avail_d, key="sel_soy_hist_insp")
        sub_s = df_soy_hist[df_soy_hist[insp_col_nm] == sel_sd]
    else:
        avail_d = sorted(df_soy_hist["생산일자"].dropna().unique().tolist(), reverse=True)
        with sc2:
            sel_sd = st.selectbox("조회할 실제 생산일자 선택", avail_d, key="sel_soy_hist_prod")
        sub_s = df_soy_hist[df_soy_hist["생산일자"] == sel_sd]

    soy_h_cols = [
        {"key": "tab", "label": "원본탭(검사일)", "width": "9%", "align": "center"},
        {"key": "ho", "label": "포장기", "width": "6%", "align": "center"},
        {"key": "inc", "label": "배양구분", "width": "9%", "align": "center"},
        {"key": "item", "label": "품목명 (용량)", "width": "21%", "align": "left"},
        {"key": "pdt", "label": "실제 생산일", "width": "9%", "align": "center"},
        {"key": "exp", "label": "소비기한", "width": "9%", "align": "center"},
        {"key": "time", "label": "생산 시작~종료 (가동)", "width": "11%", "align": "center"},
        {"key": "qty", "label": "검사수량", "width": "6%", "align": "center"},
        {"key": "wrt", "label": "작성/검사자", "width": "8%", "align": "center"},
        {"key": "st", "label": "진행상태", "width": "6%", "align": "center"},
        {"key": "jdg", "label": "오염/판정", "width": "6%", "align": "center"}
    ]
    soy_h_rows = []
    for _, sr in sub_s.iterrows():
        st_txt = str(sr.get("진행상태", "")).strip()
        if st_txt == "검사전":
            st_disp, st_cls = "검사전", "cell-yellow"
            jdg_disp = "검사전"
        elif st_txt == "부적합" or "부적합" in str(sr.get("판정", "")):
            st_disp, st_cls = "부적합", "cell-red"
            jdg_disp = f"{sr.get('오염수량', '-')} / {sr.get('판정', '-')}"
        else:
            st_disp, st_cls = "검사완료", "cell-green"
            jdg_disp = f"{sr.get('오염수량', '0 개')} / {sr.get('판정', '적합')}"

        vol_s = str(sr.get("용량_mL", "-")).strip()
        item_full = f"{sr.get('품목명', '-')} ({vol_s}mL)" if vol_s not in ["", "-"] else str(sr.get("품목명", "-"))
        insp_dt_s = str(sr.get(insp_col_nm, "-"))
        soy_h_rows.append({
            "tab": {"text": f"{sr.get('원본탭명', '-')}\n({insp_dt_s[5:] if len(insp_dt_s) >= 10 else insp_dt_s})", "cls": ""},
            "ho": {"text": sr.get("포장기", "-"), "cls": ""},
            "inc": {"text": sr.get("배양구분", "-"), "cls": ""},
            "item": {"text": item_full, "cls": ""},
            "pdt": {"text": sr.get("생산일자", "-"), "cls": ""},
            "exp": {"text": sr.get("표기소비기한_원문", "-"), "cls": ""},
            "time": {"text": f"{sr.get('생산시작_종료', '-')}\n({sr.get('실가동시간', '-')})", "cls": ""},
            "qty": {"text": sr.get("총검사수량", "0"), "cls": "cell-green" if st_cls == "cell-green" else ""},
            "wrt": {"text": f"{sr.get('작성자', '-')}\n/ {sr.get('검사자', '-')}", "cls": st_cls},
            "st": {"text": st_disp, "cls": st_cls},
            "jdg": {"text": jdg_disp, "cls": st_cls}
        })
    st.markdown(render_html_table(soy_h_cols, soy_h_rows), unsafe_allow_html=True)


def render_lot_traceability_tab(p_data: dict, widget_prefix: str = "lot"):
    master_prods = p_data.get("master_products", [])
    fsk_cnt = len(p_data.get("fsk_products", []))
    df_rt_hp = p_data.get("df_rt_hist_p", pd.DataFrame())
    df_rt_hc = p_data.get("df_rt_hist_c", pd.DataFrame())
    df_soy_h = p_data.get("df_soy_hist", pd.DataFrame())
    df_dy_hp = p_data.get("df_dairy_hist_p", pd.DataFrame())
    df_dy_hc = p_data.get("df_dairy_hist_c", pd.DataFrame())

    st.markdown(f"""
    <div class="trace-hero-box">
        <b style="font-size:15px; color:#111827;">클레임·품질 문의 대비 로트(제품명 + 소비기한) 원스톱 이력 역추적</b><br>
        • <b>제품명 표준 연동 :</b> 상온공정일보 내 <b>[제품명 식품안전나라] 탭 A열 품목({fsk_cnt:,}종)</b> 및 유제품·일보 품목을 통합 연동했습니다.<br>
        • <b>자동 교차 조회 범위 :</b> 실제 생산일자·포장호기·확인시간 &nbsp;|&nbsp; 살균/멸균기·포장기 CCP 및 <b>당일 현장 특이사항</b> &nbsp;|&nbsp; 두유 배양검사 <b>실제 생산 시작~종료 시간(실가동시간)</b>·오염·판정 결과
    </div>
    """, unsafe_allow_html=True)

    default_opt = "전체 (제품 미선택 · 소비기한으로만 검색)"
    prod_options = [default_opt] + master_prods

    q_c1, q_c2, q_c3 = st.columns([1.8, 1.1, 1.1])
    with q_c1:
        sel_prod = st.selectbox("1. 제품명 선택 ('제품명 식품안전나라' A열 연동 · 타이핑 검색)", prod_options, key=f"{widget_prefix}_sel_prod")
    with q_c2:
        in_exp = st.text_input("2. 소비기한 입력 (예: 2027-05-13, 27.05.13, 11.25)", placeholder="연.월.일 또는 월.일 입력", key=f"{widget_prefix}_in_exp")
    with q_c3:
        in_kw = st.text_input("3. 추가 키워드 필터 (선택사항)", placeholder="부분 품목명 직접 검색 시 입력", key=f"{widget_prefix}_in_kw")

    has_cond = (sel_prod != default_opt) or bool(in_exp.strip()) or bool(in_kw.strip())
    if not has_cond:
        st.info("위에서 제품명을 선택하거나 소비기한을 입력하면 상온·유제품·배양검사 누적 이력 DB에서 일치하는 로트 정보를 즉시 조회합니다.")
        return

    exp_q = parse_exp_query_info(in_exp)

    matched_rt = pd.DataFrame()
    if not df_rt_hp.empty:
        mask_rt = df_rt_hp.apply(
            lambda r: is_product_match(r.get("제품명", ""), sel_prod, in_kw)
            and is_exp_match(r.get("표기소비기한_원문", ""), r.get("표준소비기한_검색용", ""), exp_q),
            axis=1
        )
        matched_rt = df_rt_hp[mask_rt].sort_values("생산일자", ascending=False)

    matched_soy = pd.DataFrame()
    if not df_soy_h.empty:
        direct_mask_soy = df_soy_h.apply(
            lambda r: is_product_match(r.get("품목명", ""), sel_prod, in_kw)
            and is_exp_match(r.get("표기소비기한_원문", ""), r.get("표준소비기한_검색용", ""), exp_q),
            axis=1
        )
        cross_mask_soy = pd.Series([False] * len(df_soy_h), index=df_soy_h.index)
        if not matched_rt.empty:
            rt_keys = [(str(r["생산일자"]).strip(), str(r["포장호기"]).strip(), str(r["제품명"]).strip()) for _, r in matched_rt.iterrows()]
            cross_mask_soy = df_soy_h.apply(
                lambda sr: any(
                    (str(sr.get("생산일자", "")).strip() == r_dt)
                    and (
                        str(sr.get("포장기", "")).strip() == r_ho
                        or is_product_match(sr.get("품목명", ""), r_pnm, "")
                    )
                    for r_dt, r_ho, r_pnm in rt_keys
                ),
                axis=1
            )
        matched_soy = df_soy_h[direct_mask_soy | cross_mask_soy].drop_duplicates().sort_values("생산일자", ascending=False)

    matched_dy = pd.DataFrame()
    if not df_dy_hp.empty:
        mask_dy = df_dy_hp.apply(
            lambda r: is_product_match(r.get("제품명", ""), sel_prod, in_kw)
            and is_exp_match(r.get("표기소비기한_원문", ""), r.get("표준소비기한_검색용", ""), exp_q),
            axis=1
        )
        matched_dy = df_dy_hp[mask_dy].sort_values("생산일자", ascending=False)

    total_hits = len(matched_rt) + len(matched_soy) + len(matched_dy)
    if total_hits == 0:
        st.warning("입력하신 조건(제품명·소비기한)과 일치하는 생산·배양 이력이 누적 DB에서 발견되지 않았습니다.")
        return

    s1, s2, s3 = st.columns(3)
    s1.metric("상온 공정일보 매칭", f"{len(matched_rt):,} 건")
    s2.metric("두유 배양검사 매칭 (실가동시간)", f"{len(matched_soy):,} 건")
    s3.metric("유제품 포장일보 매칭", f"{len(matched_dy):,} 건")

    if not matched_rt.empty:
        st.markdown("#### 1. 상온 공정관리 일보 — 생산 호기 · 멸균 CCP · 당일 특이사항")
        rt_trace_cols = [
            {"key": "dt", "label": "생산일자 (탭)", "width": "11%", "align": "center"},
            {"key": "ho", "label": "포장호기", "width": "7%", "align": "center"},
            {"key": "prod", "label": "생산 제품명", "width": "22%", "align": "left"},
            {"key": "exp", "label": "표기 소비기한", "width": "11%", "align": "center"},
            {"key": "time", "label": "포장 확인시간", "width": "9%", "align": "center"},
            {"key": "ster", "label": "매칭 멸균기 · 핵심 CCP 수치", "width": "18%", "align": "center"},
            {"key": "rem", "label": "포장/멸균기 특이사항 & 당일 전달사항", "width": "22%", "align": "left"}
        ]
        rt_trace_rows = []
        for _, r in matched_rt.iterrows():
            s_rem = str(r.get("멸균특이사항", "이상없음")).strip()
            d_mem = str(r.get("당일전달사항", "없음")).strip()
            comb_rem_parts = []
            if s_rem and s_rem not in ["이상없음", "없음", "-"]:
                comb_rem_parts.append(f"[설비/멸균] {s_rem}")
            if d_mem and d_mem not in ["없음", "-"]:
                comb_rem_parts.append(f"[전달] {d_mem}")
            comb_rem = "\n".join(comb_rem_parts) if comb_rem_parts else "이상없음"

            rt_trace_rows.append({
                "dt": {"text": f"{r.get('생산일자', '-')}\n({r.get('원본탭명', '-')})", "cls": ""},
                "ho": {"text": r.get("포장호기", "-"), "cls": ""},
                "prod": {"text": r.get("제품명", "-"), "cls": ""},
                "exp": {"text": r.get("표기소비기한_원문", "-"), "cls": "cell-green"},
                "time": {"text": r.get("포장확인시간", "-"), "cls": "cell-green" if ":" in str(r.get("포장확인시간", "")) else "cell-yellow"},
                "ster": {"text": f"{r.get('매칭멸균기', '-')} | {r.get('멸균핵심수치_요약', '-')}", "cls": "cell-green"},
                "rem": {"text": comb_rem, "cls": "cell-yellow" if comb_rem != "이상없음" else "cell-green"}
            })
        st.markdown(render_html_table(rt_trace_cols, rt_trace_rows), unsafe_allow_html=True)

        if not df_rt_hc.empty:
            rt_dt_tabs = matched_rt[["생산일자", "원본탭명"]].drop_duplicates()
            ccp_sub = df_rt_hc.merge(rt_dt_tabs, on=["생산일자", "원본탭명"], how="inner")
            if not ccp_sub.empty:
                with st.expander(f"해당 생산일 멸균기(CCP-1B/2P) · 포장기(CCP-3B) 전체 세부 기록 보기 ({len(ccp_sub)}건)"):
                    st.dataframe(ccp_sub.drop(columns=["최종백업일시"], errors="ignore"), use_container_width=True, hide_index=True)

    if not matched_soy.empty:
        st.markdown("#### 2. 두유 배양검사 일보 — 실 생산 시작~종료 시간 · 오염수량 · 판정 이력")
        insp_c = "확정검사일_탭기준" if "확정검사일_탭기준" in matched_soy.columns else "검사일_표기"
        soy_trace_cols = [
            {"key": "pdt", "label": "실제 생산일", "width": "9%", "align": "center"},
            {"key": "idt", "label": "검사일 (탭)", "width": "9%", "align": "center"},
            {"key": "ho", "label": "포장기/배양", "width": "10%", "align": "center"},
            {"key": "item", "label": "품목명", "width": "20%", "align": "left"},
            {"key": "exp", "label": "표기 소비기한", "width": "9%", "align": "center"},
            {"key": "run", "label": "실 생산 시작 ~ 종료 (가동시간)", "width": "14%", "align": "center"},
            {"key": "qty", "label": "총 검사수량", "width": "7%", "align": "center"},
            {"key": "who", "label": "작성 / 검사자", "width": "8%", "align": "center"},
            {"key": "jdg", "label": "상태 / 판정", "width": "7%", "align": "center"},
            {"key": "rem", "label": "배양 특이사항", "width": "7%", "align": "left"}
        ]
        soy_trace_rows = []
        for _, sr in matched_soy.iterrows():
            st_s = str(sr.get("진행상태", "")).strip()
            if st_s == "검사전":
                s_cls, j_txt = "cell-yellow", "검사전"
            elif st_s == "부적합" or "부적합" in str(sr.get("판정", "")):
                s_cls, j_txt = "cell-red", f"{sr.get('오염수량', '-')} / {sr.get('판정', '-')}"
            else:
                s_cls, j_txt = "cell-green", f"{sr.get('오염수량', '0 개')} / {sr.get('판정', '적합')}"

            rem_s = str(sr.get("특이사항", "없음")).strip() or "없음"
            soy_trace_rows.append({
                "pdt": {"text": sr.get("생산일자", "-"), "cls": ""},
                "idt": {"text": f"{sr.get(insp_c, '-')}\n({sr.get('원본탭명', '-')})", "cls": ""},
                "ho": {"text": f"{sr.get('포장기', '-')}\n{sr.get('배양구분', '-')}", "cls": ""},
                "item": {"text": sr.get("품목명", "-"), "cls": ""},
                "exp": {"text": sr.get("표기소비기한_원문", "-"), "cls": ""},
                "run": {"text": f"{sr.get('생산시작_종료', '-')}\n({sr.get('실가동시간', '-')})", "cls": "cell-green" if "~" in str(sr.get("생산시작_종료", "")) else ""},
                "qty": {"text": f"{sr.get('총검사수량', '0')} 개", "cls": ""},
                "who": {"text": f"{sr.get('작성자', '-')}\n/ {sr.get('검사자', '-')}", "cls": s_cls},
                "jdg": {"text": j_txt, "cls": s_cls},
                "rem": {"text": rem_s, "cls": "cell-yellow" if rem_s not in ["없음", "이상없음", "-"] else ""}
            })
        st.markdown(render_html_table(soy_trace_cols, soy_trace_rows), unsafe_allow_html=True)

    if not matched_dy.empty:
        st.markdown("#### 3. 유제품 포장 공정관리 일보 — 확인시간 · 포장 생산시간 · 살균기 CCP · 특이사항")
        dy_trace_cols = [
            {"key": "dt", "label": "생산일자", "width": "10%", "align": "center"},
            {"key": "ln", "label": "라인구분", "width": "9%", "align": "center"},
            {"key": "prod", "label": "제품명 (용량)", "width": "21%", "align": "left"},
            {"key": "exp", "label": "표기 소비기한", "width": "10%", "align": "center"},
            {"key": "time", "label": "확인시간 / Tank", "width": "11%", "align": "center"},
            {"key": "insp", "label": "표시·접착·용량·관능·판정", "width": "15%", "align": "center"},
            {"key": "ccp", "label": "당일 포장 생산시간 · 살균기 CCP · 특이사항", "width": "24%", "align": "left"}
        ]
        dy_trace_rows = []
        for _, dr in matched_dy.iterrows():
            d_dt = str(dr.get("생산일자", "")).strip()
            d_ln = str(dr.get("라인구분", "")).strip()
            ccp_lines = []
            has_warn_rem = False
            if not df_dy_hc.empty:
                c_match = df_dy_hc[(df_dy_hc["생산일자"] == d_dt) & (df_dy_hc["라인구분"] == d_ln)]
                for _, cr in c_match.iterrows():
                    rcat = str(cr.get("기록분류", ""))
                    if rcat == "포장생산시간":
                        ccp_lines.append(f"[생산시간] {cr.get('기록내용_수치', '-')}")
                    elif rcat == "CCP모니터링":
                        ccp_lines.append(f"[{cr.get('세부항목', 'CCP')}] {cr.get('기록내용_수치', '-')}")
                    elif rcat == "특이사항":
                        rv = str(cr.get("특이사항", "이상없음")).strip()
                        if rv and rv not in ["이상없음", "-"]:
                            has_warn_rem = True
                            ccp_lines.append(f"[특이사항] {rv}")

            insp_summary = f"표시:{dr.get('표시사항', '-')} | {dr.get('접착및외관', '-')} | 관능:{dr.get('관능', '-')} ({dr.get('판정', '적합')})"
            dy_trace_rows.append({
                "dt": {"text": d_dt, "cls": ""},
                "ln": {"text": f"{d_ln}\n({dr.get('세부유형', '')})", "cls": ""},
                "prod": {"text": dr.get("제품명", "-"), "cls": ""},
                "exp": {"text": dr.get("표기소비기한_원문", "-"), "cls": "cell-green"},
                "time": {"text": f"{dr.get('확인시간', '-')}\n(Tank: {dr.get('Tank번호', '-')})", "cls": "cell-green"},
                "insp": {"text": insp_summary, "cls": "cell-red" if "부적합" in insp_summary else "cell-green"},
                "ccp": {"text": "\n".join(ccp_lines) if ccp_lines else "이상없음", "cls": "cell-yellow" if has_warn_rem else ""}
            })
        st.markdown(render_html_table(dy_trace_cols, dy_trace_rows), unsafe_allow_html=True)


# ==============================================================================
# 실시간 요약 수치 집계
# ==============================================================================
cost_target_uk = cost_targets["부문"]
cost_actual_man = round(float(df_cost["부문_실적(만원)"].sum()), 1) if not df_cost.empty else 0.0
cost_actual_uk = round(cost_actual_man / 10000, 2)
cost_rate = round((cost_actual_uk / cost_target_uk) * 100, 1) if cost_target_uk > 0 else 0.0
cost_act_line, cost_fc_line, cost_full_line, cost_slope, cost_m_cnt, cost_last_i = calc_trend_and_forecast_split(
    df_cost["부문_실적(만원)"].tolist() if not df_cost.empty else [],
    df_cost["_기록여부"].tolist() if not df_cost.empty and "_기록여부" in df_cost.columns else None
)
cost_proj_man = round(cost_actual_man + sum(cost_full_line[cost_last_i + 1:]), 1) if (0 <= cost_last_i < 11) else cost_actual_man
cost_proj_uk = round(cost_proj_man / 10000, 2)
sig_cost = "green" if (cost_actual_uk >= cost_target_uk or cost_proj_uk >= cost_target_uk) else ("red" if not df_cost.empty else "gray")

claim_target_ppm = 1.12
row_26_sum = df_claim_cat[(df_claim_cat["연도"] == "2026년") & (df_claim_cat["유형"] == "합계")] if not df_claim_cat.empty else pd.DataFrame()
claim_actual_ppm = float(row_26_sum["합계_PPM"].values[0]) if not row_26_sum.empty else 0.0
claim_total_cnt = int(row_26_sum["합계_건수"].values[0]) if not row_26_sum.empty else 0
claim_act_line, claim_fc_line, claim_full_line, claim_slope, claim_m_cnt, claim_last_i = calc_trend_and_forecast_split(
    df_claim_trend["2026년_PPM"].tolist() if not df_claim_trend.empty else [],
    df_claim_trend["_기록여부"].tolist() if not df_claim_trend.empty and "_기록여부" in df_claim_trend.columns else None
)
claim_feb_pred = claim_full_line[-1] if claim_full_line else 0.0
if row_26_sum.empty:
    sig_claim = "gray"
elif claim_actual_ppm > claim_target_ppm:
    sig_claim = "red"
elif claim_slope > 0.03:
    sig_claim = "yellow"
else:
    sig_claim = "green"

rt_t = proc_data["rt_today"]
rt_y = proc_data["rt_yest"]
rt_t_tab = rt_t["tab_title"] if rt_t else "-"
rt_y_tab = rt_y["tab_title"] if rt_y else "-"
rt_t_lines = rt_t["lines_records"] if rt_t else []
active_rt_cnt = sum(1 for r in rt_t_lines if r["생산 제품명"] != "(비가동)")
wait_rt_cnt = sum(1 for r in rt_t_lines if r["_cls"] == "cell-yellow")
red_rt_cnt = sum(1 for r in rt_t_lines if r["_cls"] == "cell-red") + (
    sum(1 for sr in rt_t["ster_records"] if "cell-red" in (sr["_c_temp"], sr["_c_press"], sr["_c_hold"], sr["_c_flt"])) if rt_t else 0
)

df_milk_run = proc_data["df_milk_pack"][proc_data["df_milk_pack"]["가동여부"].str.contains("금일생산", na=False)] if not proc_data["df_milk_pack"].empty else pd.DataFrame()
df_ferm_run = proc_data["df_ferm_pack"][proc_data["df_ferm_pack"]["가동여부"].str.contains("금일생산", na=False)] if not proc_data["df_ferm_pack"].empty else pd.DataFrame()
active_dairy_cnt = len(df_milk_run) + len(df_ferm_run)
if active_dairy_cnt == 0 and not proc_data["df_dairy_hist_p"].empty:
    active_dairy_cnt = int((proc_data["df_dairy_hist_p"]["생산일자"] == today_kst_str).sum())

df_soy_b_main = proc_data["df_soy_blocks"]
soy_blocks_cnt = len(df_soy_b_main)
soy_total_samples = sum(int(to_float(x, 0)) for x in df_soy_b_main["총 검사수량"]) if not df_soy_b_main.empty else 0
soy_uninspected_cnt = int((~df_soy_b_main["검사완료여부"]).sum()) if (not df_soy_b_main.empty and "검사완료여부" in df_soy_b_main.columns) else 0
soy_inspected_cnt = soy_blocks_cnt - soy_uninspected_cnt
soy_contam_total = sum(
    int(to_float(r["오염수량"], 0))
    for _, r in df_soy_b_main.iterrows()
    if bool(r.get("검사완료여부", False))
) if not df_soy_b_main.empty else 0

today_real_notes = list(rt_t["ster_special_notes"]) if rt_t else []
yest_real_notes = list(rt_y["ster_special_notes"]) if rt_y else []

target_exec = 88.3
total_sup_cnt = len(df_sup_master)
unsub_sup_cnt = int((df_sup_master["점수"] == "미제출").sum()) if not df_sup_master.empty else 0
sub_sup_cnt = total_sup_cnt - unsub_sup_cnt
sup_exec_rate = round((sub_sup_cnt / total_sup_cnt) * 100, 1) if total_sup_cnt > 0 else 0.0
ok_sup_cnt = int((df_sup_master["결과"] == "승인").sum()) if not df_sup_master.empty else 0
guide_sup_cnt = int((df_sup_master["결과"] == "지도").sum()) if not df_sup_master.empty else 0
out_sup_cnt = int((df_sup_master["결과"] == "등급 외").sum()) if not df_sup_master.empty else 0
sig_supplier = "green" if sup_exec_rate >= target_exec else ("yellow" if sup_exec_rate >= 75.0 else ("red" if total_sup_cnt > 0 else "gray"))

if not df_label_status.empty:
    df_rev_now = df_label_status[df_label_status["분류"] == "식품안전팀 검토중"]
    df_comp_now = df_label_status[df_label_status["분류"] == "검토완료(확인필)"]
    reviewing_cnt = len(df_rev_now)
    completed_cnt = len(df_comp_now)
    broken_date_cnt = int((df_label_status["등록연도"] == "날짜미상").sum())
    rev_rows_structured = []
    for _, r_rev in df_rev_now.iterrows():
        rev_rows_structured.append({
            "dept": str(r_rev.get("요청부서", "")).strip() or "미기입",
            "title": str(r_rev.get("제목", "")).strip() or "(제목 없음)",
            "dt": str(r_rev.get("등록일자", "")).strip()[5:] if len(str(r_rev.get("등록일자", ""))) >= 10 else ""
        })
else:
    reviewing_cnt, completed_cnt, broken_date_cnt, rev_rows_structured = 0, 0, 0, []

sub_raw_cnt = len(df_raw_sub)
verified_raw_cnt = len(df_raw_sub[df_raw_sub["검증상태"].astype(str).str.contains("완료|적합", na=False)]) if ("검증상태" in df_raw_sub.columns and not df_raw_sub.empty) else 0
allergy_raw_cnt = len(df_raw_sub[df_raw_sub["신규알레르기"].astype(str).str.strip() != ""]) if ("신규알레르기" in df_raw_sub.columns and not df_raw_sub.empty) else 0


# ==============================================================================
# 좌측 사이드바 (QUALITY ONE 스타일 브랜드 로고 + 텍스트 네비게이션)
# ==============================================================================
ACTIVE_MENU_ALIAS = {
    "cost": "dept_kpi8",
    "kpi_11": "supplier",
    "kpi_8": "fs_haccp_risk",
    "kpi_12": "fs_haccp_risk",
    "kpi_9": "qc_defect_sub",
    "kpi_10": "qc_defect_sub"
}
effective_nav_view = ACTIVE_MENU_ALIAS.get(st.session_state.current_view, st.session_state.current_view)

with st.sidebar:
    st.markdown("""
    <div class="qo-brand-wrap">
        <div class="qo-logo-mark">Y</div>
        <div>
            <div class="qo-brand-name">YONSEI QUALITY</div>
            <div class="qo-brand-sub">Integrated Quality Platform</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    for grp in SIDEBAR_MENU_GROUPS:
        st.markdown(f"<div class='sb-group-hdr'>{html.escape(grp['group_title'])}</div>", unsafe_allow_html=True)
        for v_key, v_label in grp["items"]:
            is_cur = (effective_nav_view == v_key)
            st.button(
                v_label,
                key=f"sb_nav_{v_key}",
                type="secondary" if is_cur else "secondary",
                use_container_width=True,
                on_click=set_view,
                args=(v_key,)
            )

    st.markdown("<div style='height:14px; border-bottom:1px solid #F2F4F7; margin-bottom:10px;'></div>", unsafe_allow_html=True)
    st.button("데이터 실시간 동기화", key="sb_btn_sync", type="secondary", use_container_width=True, on_click=trigger_manual_sync)
    st.markdown(
        f"<div style='font-size:11px; color:#9CA3AF; margin-top:8px; padding:0 4px; line-height:1.5;'>"
        f"업데이트 : {bundle['loaded_at']}<br>"
        f"연세유업 아산공장 품질안전부문</div>",
        unsafe_allow_html=True
    )


# ==============================================================================
# [화면 1] 통합 대시보드 (QUALITY ONE 레퍼런스 레이아웃 & 타이포그래피 적용)
# ==============================================================================
if st.session_state.current_view == "main":
    # 최상단 글로벌 검색바 & 실시간 상태 표시줄 (레퍼런스 이미지 상단 구조)
    gt_c1, gt_c2, gt_c3 = st.columns([2.2, 2.0, 0.45])
    with gt_c1:
        st.text_input(
            "글로벌 빠른 검색",
            placeholder="LOT(소비기한), 제품명 입력 후 Enter 시 즉시 이력 역추적...",
            label_visibility="collapsed",
            key="global_top_search",
            on_change=on_global_quick_search
        )
    with gt_c2:
        t_short = bundle["loaded_at"].split(" ")[-2][:5] if " " in bundle["loaded_at"] else bundle["loaded_at"]
        st.markdown(
            f"<div style='display:flex; justify-content:flex-end; align-items:center; gap:10px; padding-top:3px;'>"
            f"<span class='live-status-pill'><span class='live-dot-green'></span>실시간 운영 중 &nbsp;·&nbsp; 업데이트 {html.escape(t_short)}</span>"
            f"<span style='font-size:12.5px; font-weight:600; color:#374151;'>품질안전부문</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with gt_c3:
        st.button("새로고침", key="top_quick_sync", type="secondary", use_container_width=True, on_click=trigger_manual_sync)

    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    now_dt = now_kst()
    date_label_kr = f"{now_dt.year}년 {now_dt.month}월 {now_dt.day}일 ({weekdays_kr[now_dt.weekday()]})"

    st.markdown(f"""
    <div class="qo-hero-wrap">
        <div>
            <div class="qo-hero-title">품질안전부문 실시간 통합 관제</div>
            <div class="qo-hero-sub">{date_label_kr} &nbsp;|&nbsp; 현장 CCP · 표시사항 심의 · 대내외 심사 및 부문 핵심 지표를 실시간으로 관리합니다.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if all_load_errors:
        with st.expander(f"데이터 연동 확인 필요 ({len(all_load_errors)}건)", expanded=False):
            for err_line in all_load_errors:
                st.write(f"- {err_line}")

    # ------------------------------------------------------------------
    # [상단 구역 - 대형 3카드] 공정 실시간 · 표시사항 심의/특이사항 · 심사 진행상황/일정
    # ------------------------------------------------------------------
    top_c1, top_c2, top_c3 = st.columns([1.0, 1.18, 1.12])

    # 1) 좌측 상단: 당일 공정 CCP & 배양 실시간 현황
    with top_c1:
        with st.container(border=True):
            render_card_header("당일 공정 CCP & 배양 현황", "process", "main_go_process", "전체보기 ›")

            if red_rt_cnt > 0:
                rt_dot, rt_b_cls, rt_b_txt = "dot-red", "badge-err", "기준이탈 확인"
            elif wait_rt_cnt > 0:
                rt_dot, rt_b_cls, rt_b_txt = "dot-amber", "badge-warn", f"확인대기 {wait_rt_cnt}건"
            else:
                rt_dot, rt_b_cls, rt_b_txt = "dot-green", "badge-ok", "CCP 적합"

            if active_dairy_cnt > 0:
                dy_dot, dy_b_cls, dy_b_txt = "dot-green", "badge-ok", "점검 완료"
            else:
                dy_dot, dy_b_cls, dy_b_txt = "dot-amber", "badge-neutral", "생산 대기"

            if soy_contam_total > 0:
                sy_dot, sy_b_cls, sy_b_txt = "dot-red", "badge-err", f"오염 {soy_contam_total}건"
            elif soy_blocks_cnt == 0:
                sy_dot, sy_b_cls, sy_b_txt = "dot-amber", "badge-neutral", "기록 대기"
            elif soy_uninspected_cnt > 0:
                sy_dot, sy_b_cls, sy_b_txt = "dot-amber", "badge-warn", f"검사전 {soy_uninspected_cnt}호기"
            else:
                sy_dot, sy_b_cls, sy_b_txt = "dot-green", "badge-ok", "검사 완료"

            board_lines = []
            for tn in today_real_notes:
                board_lines.append(f"<div style='padding:3px 0; border-bottom:1px solid #F2F4F7;'><b style='color:#B45309;'>[금일 {html.escape(rt_t_tab)}]</b> {html.escape(tn)}</div>")
            for yn in yest_real_notes:
                board_lines.append(f"<div style='padding:3px 0; border-bottom:1px solid #F2F4F7;'><b style='color:#1D4ED8;'>[전일 {html.escape(rt_y_tab)}]</b> {html.escape(yn)}</div>")
            if not board_lines:
                board_lines.append(f"<div style='color:#059669; font-weight:600; padding:4px 0;'>금일({html.escape(rt_t_tab)}) 및 전일({html.escape(rt_y_tab)}) 설비·품질 특이사항 없음</div>")

            st.markdown(f"""
            <div class="qo-list-row">
                <span style="display:flex; align-items:center;">
                    <span class="qo-row-dot {rt_dot}"></span>
                    <b style="color:#111827;">상온 멸균·포장 CCP</b>
                    <span style="color:#6B7280; font-size:11.8px; margin-left:6px;">{html.escape(rt_t_tab)}탭 · {active_rt_cnt}건 가동</span>
                </span>
                <span class="badge-pill {rt_b_cls}">{rt_b_txt}</span>
            </div>
            <div class="qo-list-row">
                <span style="display:flex; align-items:center;">
                    <span class="qo-row-dot {dy_dot}"></span>
                    <b style="color:#111827;">유제품 포장 관리</b>
                    <span style="color:#6B7280; font-size:11.8px; margin-left:6px;">우유·발효유 {active_dairy_cnt}건</span>
                </span>
                <span class="badge-pill {dy_b_cls}">{dy_b_txt}</span>
            </div>
            <div class="qo-list-row">
                <span style="display:flex; align-items:center;">
                    <span class="qo-row-dot {sy_dot}"></span>
                    <b style="color:#111827;">두유 배양검사</b>
                    <span style="color:#6B7280; font-size:11.8px; margin-left:6px;">{html.escape(proc_data['soy_default_tab'])}탭 · {soy_total_samples:,}개</span>
                </span>
                <span class="badge-pill {sy_b_cls}">{sy_b_txt}</span>
            </div>
            <div style="font-size:12px; font-weight:700; color:#4B5563; margin-top:12px;">금일·전일 설비 및 공정 특이사항</div>
            <div class="qo-sub-box" style="min-height:112px; max-height:118px;">
                {''.join(board_lines)}
            </div>
            """, unsafe_allow_html=True)

    # 2) 중앙 상단: 표시사항 심의 현황 및 특이사항
    with top_c2:
        with st.container(border=True):
            render_card_header("표시사항 심의 현황 및 특이사항", "label_status", "main_go_label_status", "전체보기 ›")

            if rev_rows_structured:
                rev_list_html = "".join([
                    f"<div class='qo-list-row' style='padding:6px 2px;'>"
                    f"<span style='overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12.5px;'>"
                    f"<span style='color:#2563EB; font-weight:600; margin-right:5px;'>[{html.escape(r['dept'])}]</span>"
                    f"{html.escape(r['title'])}</span>"
                    f"<span class='badge-pill badge-info'>검토중</span>"
                    f"</div>"
                    for r in rev_rows_structured
                ])
            else:
                rev_list_html = "<div style='color:#9CA3AF; padding:10px 2px; font-size:12.5px;'>현재 검토 대기 중인 품목이 없습니다.</div>"

            memo_safe = html.escape(st.session_state.get("label_special_memo", "")).replace("\n", "<br>")
            allergy_alert_str = f" · 신규알레르기 {allergy_raw_cnt}건" if allergy_raw_cnt > 0 else ""

            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span style="font-size:12.3px; font-weight:700; color:#374151;">
                    식품안전팀 검토 진행 목록 <span style="color:#2563EB; margin-left:3px;">{reviewing_cnt}건</span>
                </span>
                <span class="qo-card-caption">누적 완료 {completed_cnt:,}건{html.escape(allergy_alert_str)}</span>
            </div>
            <div class="qo-scroll-area" style="min-height:132px; max-height:132px; border:1px solid #F2F4F7; border-radius:8px; padding:4px 8px;">
                {rev_list_html}
            </div>
            <div style="font-size:12px; font-weight:700; color:#4B5563; margin-top:10px;">표시사항 특이사항 메모 (원자재 변경 · 알레르기 점검)</div>
            <div class="qo-sub-box" style="min-height:68px; max-height:74px;">{memo_safe if memo_safe else '등록된 특이사항 메모가 없습니다.'}</div>
            """, unsafe_allow_html=True)

            lb_b1, lb_b2 = st.columns([1.2, 1.0])
            with lb_b1:
                with st.popover("특이사항 메모 편집", use_container_width=True):
                    with st.form("form_quick_lbl_memo"):
                        in_lbl_memo = st.text_area(
                            "표시사항 특이사항 (시트 영구 저장)",
                            value=st.session_state.get("label_special_memo", ""),
                            height=105
                        )
                        if st.form_submit_button("저장"):
                            save_special_boards_to_sheet(in_lbl_memo.strip(), st.session_state["claim_special_list"])
                            st.rerun()
            with lb_b2:
                st.button("원자재 표시사항 DB ›", key="main_go_raw_db", type="secondary", use_container_width=True, on_click=set_view, args=("label_issue",))

    # 3) 우측 상단: 심사 진행상황 및 일정
    with top_c3:
        aud_sum = get_active_audit_summary(df_audit_sched, today_kst_str)
        with st.container(border=True):
            render_card_header("심사 진행상황 및 일정", "kpi_5", "main_go_audit", "일정관리 ›")

            today_d_obj = now_kst().date()
            if df_audit_sched is not None and not df_audit_sched.empty:
                sched_items_html = []
                for _, sr in df_audit_sched.sort_values("심사일자", ascending=True).iterrows():
                    s_dt = pd.to_datetime(sr["심사일자"], errors="coerce")
                    dt_disp = str(sr["심사일자"])[5:] if len(str(sr["심사일자"])) >= 10 else str(sr["심사일자"])
                    st_nm = str(sr.get("진행현황", "심사준비중"))
                    sc_str = f" ({sr['점수']})" if str(sr.get("점수", "")).strip() else ""

                    if pd.notna(s_dt):
                        diff_d = (s_dt.date() - today_d_obj).days
                        if diff_d == 0:
                            d_pill_cls, d_pill_txt = "badge-err", "금일 심사"
                        elif diff_d > 0:
                            d_pill_cls = "badge-warn" if diff_d <= 7 else "badge-info"
                            d_pill_txt = f"D-{diff_d}"
                        else:
                            d_pill_cls = "badge-ok" if st_nm == "심사종료" else "badge-neutral"
                            d_pill_txt = f"완료{sc_str}" if st_nm == "심사종료" else st_nm
                    else:
                        d_pill_cls, d_pill_txt = "badge-neutral", st_nm

                    sched_items_html.append(
                        f"<div class='qo-list-row' style='padding:6px 2px;'>"
                        f"<span style='overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12.5px;'>"
                        f"<b style='color:#374151; margin-right:6px;'>{html.escape(dt_disp)}</b>"
                        f"{html.escape(str(sr['심사명']))}</span>"
                        f"<span class='badge-pill {d_pill_cls}'>{html.escape(d_pill_txt)}</span>"
                        f"</div>"
                    )
                sched_block_html = "".join(sched_items_html)
            else:
                sched_block_html = "<div style='color:#9CA3AF; padding:12px 2px; font-size:12.5px;'>등록된 심사 일정이 없습니다. 우측 상단 '일정관리'에서 추가해 주세요.</div>"

            st.markdown(f"""
            <div class="qo-prog-banner">
                <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{html.escape(aud_sum['banner_text'])}</span>
                <span style="color:{aud_sum['color']}; font-weight:700; white-space:nowrap; margin-left:8px;">{html.escape(aud_sum['status'])} {aud_sum['pct']}%</span>
            </div>
            <div class="qo-prog-track">
                <div class="qo-prog-fill" style="width:{aud_sum['pct']}%; background-color:{aud_sum['color']};"></div>
            </div>
            <div class="qo-prog-steps">
                <span>준비중 20%</span><span>심사중 50%</span><span>서류 75%</span><span>현장 85%</span><span>종료 100%</span>
            </div>
            <div style="font-size:12px; font-weight:700; color:#4B5563; margin:6px 0 4px 0;">연간 대내외 심사 일정</div>
            <div class="qo-scroll-area" style="min-height:164px; max-height:164px; border:1px solid #F2F4F7; border-radius:8px; padding:4px 8px;">
                {sched_block_html}
            </div>
            """, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # [하단 구역] 좌측: 품질 추이(PPM) 그래프 + 최근 클레임·부적합 특이사항
    #            우측: 하향 배치된 컴팩트 2026 부문 8대 KPI 스코어카드 (4x2)
    # ------------------------------------------------------------------
    bot_left, bot_right = st.columns([1.05, 1.38])

    with bot_left:
        with st.container(border=True):
            render_card_header(f"품질 추이 현황 (누적 {claim_actual_ppm} ppm / 목표 1.12 이하)", "claim", "main_go_claim_chart", "추이분석 ›")
            st.plotly_chart(
                draw_compact_ppm_chart(df_claim_trend, claim_act_line, claim_fc_line, claim_last_i),
                use_container_width=True,
                config={"displayModeBar": False}
            )

        with st.container(border=True):
            render_card_header("클레임 및 부적합 특이사항", "lot_trace", "main_go_lot_trace", "LOT 역추적 ›")

            clm_issues = st.session_state.get("claim_special_list", [])
            if not clm_issues:
                st.caption("등록된 클레임·부적합 특이사항이 없습니다.")
            else:
                for idx_ci, ci in enumerate(clm_issues[:4]):
                    ic1, ic2 = st.columns([3.4, 1.0])
                    p_kw = str(ci.get("제품키워드", "")).strip()
                    e_kw = str(ci.get("소비기한", "")).strip()
                    sub_meta = f" · {p_kw} {e_kw}".strip(" ·") if (p_kw or e_kw) else ""
                    st_tag = str(ci.get("상태", "확인 필요")).strip()

                    if "긴급" in st_tag or "부적합" in st_tag or "필요" in st_tag:
                        dot_c, b_cls = "dot-red", "badge-err"
                    elif "완료" in st_tag:
                        dot_c, b_cls = "dot-green", "badge-ok"
                    else:
                        dot_c, b_cls = "dot-blue", "badge-info"

                    with ic1:
                        st.markdown(
                            f"<div style='padding:5px 2px; font-size:12.6px; display:flex; align-items:center; justify-content:space-between;'>"
                            f"<span style='overflow:hidden; text-overflow:ellipsis; white-space:nowrap;'>"
                            f"<span class='qo-row-dot {dot_c}'></span>"
                            f"<b style='color:#111827;'>{html.escape(str(ci.get('특이사항', '')))}</b>"
                            f"<span style='color:#6B7280; font-size:11.5px;'>{html.escape(sub_meta)}</span></span>"
                            f"<span class='badge-pill {b_cls}' style='margin-left:6px;'>{html.escape(st_tag)}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
                    with ic2:
                        st.button(
                            "이력조회 ›",
                            key=f"btn_ci_trace_{idx_ci}",
                            type="secondary",
                            use_container_width=True,
                            on_click=jump_to_lot_trace,
                            args=(p_kw, e_kw)
                        )

            with st.popover("클레임·부적합 특이사항 등록 / 삭제", use_container_width=True):
                with st.form("form_add_claim_issue", clear_on_submit=True):
                    ci_desc = st.text_input("이슈 내용 (예: 혼합액 규격 점검, 멸균유 검사 지연 등)")
                    f_c1, f_c2, f_c3 = st.columns(3)
                    with f_c1:
                        ci_st = st.selectbox("상태", ["확인 필요", "진행 중", "조치 예정", "조치 완료"])
                    with f_c2:
                        ci_prod = st.text_input("제품명 키워드", placeholder="예: 검은콩")
                    with f_c3:
                        ci_exp = st.text_input("소비기한/LOT", placeholder="예: 05.13")

                    c_add_b, c_clr_b = st.columns(2)
                    with c_add_b:
                        do_add_ci = st.form_submit_button("추가 저장")
                    with c_clr_b:
                        do_del_last = st.form_submit_button("최상단 1건 삭제")

                    if do_add_ci and ci_desc.strip():
                        new_list = [{
                            "구분": "클레임/부적합",
                            "특이사항": ci_desc.strip(),
                            "상태": ci_st,
                            "제품키워드": ci_prod.strip(),
                            "소비기한": ci_exp.strip()
                        }] + list(st.session_state.get("claim_special_list", []))
                        save_special_boards_to_sheet(st.session_state["label_special_memo"], new_list[:8])
                        st.rerun()
                    if do_del_last and st.session_state.get("claim_special_list"):
                        rem_list = list(st.session_state["claim_special_list"])[1:]
                        save_special_boards_to_sheet(st.session_state["label_special_memo"], rem_list)
                        st.rerun()

    with bot_right:
        # 우측 하단으로 살짝 내려 안정감 있게 정렬한 2026 부문 8대 KPI 스코어카드
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        with st.container(border=True):
            render_card_header("2026 품질안전부문 8대 업적 KPI 현황", "dept_kpi8", "main_go_kpi8_board", "전체 차트 ›")

            mk = st.session_state["manual_kpis"]
            sup_disp_val = f"{sup_exec_rate}%" if total_sup_cnt > 0 else mk["kpi_11"]["compact_val"]
            sup_disp_sig = sig_supplier if total_sup_cnt > 0 else mk["kpi_11"]["signal"]

            compact_8_specs = [
                {"key": "c8_1", "lbl": "1. 원가 절감", "view": "cost", "val": f"{cost_actual_uk}억", "sub": f"목표 {cost_target_uk}억 ({cost_rate}%)", "sig": sig_cost},
                {"key": "c8_2", "lbl": "2. 클레임 발생률", "view": "claim", "val": f"{claim_actual_ppm} ppm", "sub": f"목표 {claim_target_ppm} 이하 ({claim_total_cnt:,}건)", "sig": sig_claim},
                {"key": "c8_3", "lbl": "3. HACCP 강화", "view": "kpi_8", "val": mk["kpi_8"]["compact_val"], "sub": f"목표 {mk['kpi_8']['target_text']}", "sig": mk["kpi_8"]["signal"]},
                {"key": "c8_4", "lbl": "4. 핵심불량 저감", "view": "kpi_9", "val": mk["kpi_9"]["compact_val"], "sub": f"목표 {mk['kpi_9']['target_text']}", "sig": mk["kpi_9"]["signal"]},
                {"key": "c8_5", "lbl": "5. 부자재 관리", "view": "kpi_10", "val": mk["kpi_10"]["compact_val"], "sub": f"목표 {mk['kpi_10']['target_text']}", "sig": mk["kpi_10"]["signal"]},
                {"key": "c8_6", "lbl": "6. 협력업체 관리", "view": "supplier", "val": sup_disp_val, "sub": f"목표 {target_exec}% ({sub_sup_cnt}/{total_sup_cnt})", "sig": sup_disp_sig},
                {"key": "c8_7", "lbl": "7. 심사점수", "view": "kpi_5", "val": mk["kpi_5"]["compact_val"], "sub": f"목표 {mk['kpi_5']['target_text']}", "sig": mk["kpi_5"]["signal"]},
                {"key": "c8_8", "lbl": "8. 법적 RISK", "view": "kpi_12", "val": mk["kpi_12"]["compact_val"], "sub": f"목표 {mk['kpi_12']['target_text']}", "sig": mk["kpi_12"]["signal"]}
            ]

            for row_start in (0, 4):
                g_cols = st.columns(4)
                for idx_offset, col_obj in enumerate(g_cols):
                    item = compact_8_specs[row_start + idx_offset]
                    with col_obj:
                        with st.container(border=True):
                            st.markdown(f"""
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-size:12px; font-weight:700; color:#4B5563;">{html.escape(item['lbl'])}</span>
                                {get_signal_dot_html(item['sig'])}
                            </div>
                            <div class="qo-kpi-num">{html.escape(str(item['val']))}</div>
                            <div class="qo-kpi-target" style="margin-bottom:6px;">{html.escape(str(item['sub']))}</div>
                            """, unsafe_allow_html=True)
                            st.button(
                                "상세보기 ›",
                                key=f"btn_{item['key']}",
                                type="secondary",
                                use_container_width=True,
                                on_click=set_view,
                                args=(item["view"],)
                            )
# ============================ [PART 3 / 4 끝] ============================
# ==============================================================================
# [PART 4 / 4] 부문 8대 KPI 현황판 · 식품안전팀 / 품질관리팀 전 세부 페이지 라우팅
# ==============================================================================
else:
    nav_c1, nav_c2, nav_c3 = st.columns([6.6, 1.8, 1.6])
    with nav_c1:
        st.button("⬅️ 실시간 통합 관제판(첫 화면)으로 돌아가기", key="btn_back_main", on_click=set_view, args=("main",))
    with nav_c2:
        st.button("📊 2026 부문 8대 KPI 보기", key="btn_go_kpi8_top", on_click=set_view, args=("dept_kpi8",))
    with nav_c3:
        st.button("🔄 시트 실시간 동기화", key="btn_sync_sub", on_click=trigger_manual_sync)

    view = st.session_state.current_view

    # ------------------------------------------------------------------
    # [부문 통합] 2026 품질안전부문 8대 업적 KPI 현황판 (4x2 막대그래프 카드 + 클릭 시 상세 이동)
    # ------------------------------------------------------------------
    if view == "dept_kpi8":
        st.markdown(f"""
        <div class="yonsei-header-bar">
            <span class="yonsei-title">2026 업적 KPI 현황판_품질안전부문 (8대 핵심 지표 Summary)</span>
            <span class="live-status-pill">각 항목 제목 클릭 시 세부 분석 화면 이동 &nbsp;|&nbsp; 기준 : {bundle['loaded_at']}</span>
        </div>
        """, unsafe_allow_html=True)

        mk = st.session_state["manual_kpis"]
        sup_rate_disp = sup_exec_rate if total_sup_cnt > 0 else float(mk["kpi_11"]["actual_num"])
        sup_sig_disp = sig_supplier if total_sup_cnt > 0 else mk["kpi_11"]["signal"]

        # 1행 (1번 원가절감 / 2번 클레임 발생률 / 3번 식품안전 및 HACCP 강화 / 4번 핵심불량 저감화)
        r1_cols = st.columns(4)

        with r1_cols[0]:
            with st.container(border=True):
                st.button("1. 원가 절감  ›", key="k8_hdr_1", type="secondary", use_container_width=True, on_click=set_view, args=("cost",))
                st.markdown(f"""
                <div class="kpi-meta-wrap">
                    {get_signal_dot_html(sig_cost)}
                    <div><span class="kpi-dot-bullet">●</span><b>목표 : {cost_target_uk}억원 이상</b></div>
                    <div><span class="kpi-dot-bullet">●</span><b>실적 : {cost_actual_uk}억원, {cost_rate}% 달성</b></div>
                    <div class="kpi-sub-pill">📈 연말 추세 예측 : {cost_proj_uk}억원</div>
                </div>
                """, unsafe_allow_html=True)
                st.plotly_chart(draw_mini_bar(cost_target_uk, cost_actual_uk), use_container_width=True, config={"displayModeBar": False}, key="k8_bar_1")

        with r1_cols[1]:
            with st.container(border=True):
                st.button("2. 클레임 발생률  ›", key="k8_hdr_2", type="secondary", use_container_width=True, on_click=set_view, args=("claim",))
                st.markdown(f"""
                <div class="kpi-meta-wrap">
                    {get_signal_dot_html(sig_claim)}
                    <div><span class="kpi-dot-bullet">●</span><b>목표 : {claim_target_ppm} ppm 이하</b></div>
                    <div><span class="kpi-dot-bullet">●</span><b>실적 : {claim_actual_ppm} ppm (총 {claim_total_cnt:,}건)</b></div>
                    <div class="kpi-sub-pill">📈 2월 예상 추세 : {claim_feb_pred:.2f} ppm</div>
                </div>
                """, unsafe_allow_html=True)
                st.plotly_chart(draw_mini_bar(claim_target_ppm, claim_actual_ppm), use_container_width=True, config={"displayModeBar": False}, key="k8_bar_2")

        with r1_cols[2]:
            i3 = mk["kpi_8"]
            with st.container(border=True):
                st.button(f"{i3['title']}  ›", key="k8_hdr_3", type="secondary", use_container_width=True, on_click=set_view, args=("kpi_8",))
                st.markdown(f"""
                <div class="kpi-meta-wrap">
                    {get_signal_dot_html(i3['signal'])}
                    <div><span class="kpi-dot-bullet">●</span><b>목표 : {html.escape(i3['target_text'])}</b></div>
                    <div><span class="kpi-dot-bullet">●</span><b>실적 : {html.escape(i3['actual_text'])}</b></div>
                    <div class="kpi-sub-pill">{html.escape(i3['sub_badge'])}</div>
                </div>
                """, unsafe_allow_html=True)
                st.plotly_chart(draw_mini_bar(float(i3["target_num"]), float(i3["actual_num"]), suffix=i3["suffix"]), use_container_width=True, config={"displayModeBar": False}, key="k8_bar_3")

        with r1_cols[3]:
            i4 = mk["kpi_9"]
            with st.container(border=True):
                st.button(f"{i4['title']}  ›", key="k8_hdr_4", type="secondary", use_container_width=True, on_click=set_view, args=("kpi_9",))
                st.markdown(f"""
                <div class="kpi-meta-wrap">
                    {get_signal_dot_html(i4['signal'])}
                    <div><span class="kpi-dot-bullet">●</span><b>목표 : {html.escape(i4['target_text'])}</b></div>
                    <div><span class="kpi-dot-bullet">●</span><b>실적 : {html.escape(i4['actual_text'])}</b></div>
                    <div class="kpi-sub-pill">{html.escape(i4['sub_badge'])}</div>
                </div>
                """, unsafe_allow_html=True)
                st.plotly_chart(draw_mini_bar(float(i4["target_num"]), float(i4["actual_num"]), suffix=i4["suffix"]), use_container_width=True, config={"displayModeBar": False}, key="k8_bar_4")

        # 2행 (5번 부자재 관리 고도화 / 6번 협력업체 관리강화 / 7번 심사점수 / 8번 식품안전 법적 RISK 최소화)
        r2_cols = st.columns(4)

        with r2_cols[0]:
            i5 = mk["kpi_10"]
            with st.container(border=True):
                st.button(f"{i5['title']}  ›", key="k8_hdr_5", type="secondary", use_container_width=True, on_click=set_view, args=("kpi_10",))
                notes5_html = "".join([f"<div style='padding:2px 0;'>- {html.escape(ln)}</div>" for ln in i5["notes"]])
                st.markdown(f"""
                <div class="kpi-meta-wrap">
                    {get_signal_dot_html(i5['signal'])}
                    <div><span class="kpi-dot-bullet">●</span><b>목표 : {html.escape(i5['target_text'])}</b></div>
                    <div><span class="kpi-dot-bullet">●</span><b>실적 : {html.escape(i5['actual_text'])}</b></div>
                    <div class="kpi-sub-pill">{html.escape(i5['sub_badge'])}</div>
                </div>
                <div class="card-scroll-box">
                    <div style="font-weight:800; color:#00205B; margin-bottom:4px;">✓ {html.escape(i5['notes_title'])}</div>
                    {notes5_html}
                </div>
                """, unsafe_allow_html=True)

        with r2_cols[1]:
            with st.container(border=True):
                st.button("6. 협력업체 관리강화  ›", key="k8_hdr_6", type="secondary", use_container_width=True, on_click=set_view, args=("supplier",))
                st.markdown(f"""
                <div class="kpi-meta-wrap">
                    {get_signal_dot_html(sup_sig_disp)}
                    <div><span class="kpi-dot-bullet">●</span><b>목표 : 실행률 {target_exec}% 이상</b></div>
                    <div><span class="kpi-dot-bullet">●</span><b>실적 : {sup_rate_disp}% (제출 {sub_sup_cnt}/{total_sup_cnt}개사)</b></div>
                    <div class="kpi-sub-pill">승인 {ok_sup_cnt} · 지도 {guide_sup_cnt} · 등급외 {out_sup_cnt}</div>
                </div>
                """, unsafe_allow_html=True)
                st.plotly_chart(draw_mini_bar(target_exec, sup_rate_disp, suffix="%"), use_container_width=True, config={"displayModeBar": False}, key="k8_bar_6")

        with r2_cols[2]:
            i7 = mk["kpi_5"]
            with st.container(border=True):
                st.button("7. 심사점수  ›", key="k8_hdr_7", type="secondary", use_container_width=True, on_click=set_view, args=("kpi_5",))
                st.markdown(f"""
                <div class="kpi-meta-wrap">
                    {get_signal_dot_html(i7['signal'])}
                    <div><span class="kpi-dot-bullet">●</span><b>목표 : {html.escape(i7['target_text'])}</b></div>
                    <div><span class="kpi-dot-bullet">●</span><b>실적 : {html.escape(i7['actual_text'])}</b></div>
                    <div class="kpi-sub-pill">{html.escape(i7['sub_badge'])}</div>
                </div>
                """, unsafe_allow_html=True)
                st.plotly_chart(draw_mini_bar(float(i7["target_num"]), float(i7["actual_num"])), use_container_width=True, config={"displayModeBar": False}, key="k8_bar_7")

        with r2_cols[3]:
            i8 = mk["kpi_12"]
            with st.container(border=True):
                st.button(f"{i8['title']}  ›", key="k8_hdr_8", type="secondary", use_container_width=True, on_click=set_view, args=("kpi_12",))
                notes8_html = "".join([f"<div style='padding:2px 0;'>- {html.escape(ln)}</div>" for ln in i8["notes"]])
                st.markdown(f"""
                <div class="kpi-meta-wrap">
                    {get_signal_dot_html(i8['signal'])}
                    <div><span class="kpi-dot-bullet">●</span><b>목표 : {html.escape(i8['target_text'])}</b></div>
                    <div><span class="kpi-dot-bullet">●</span><b>실적 : {html.escape(i8['actual_text'])}</b></div>
                    <div class="kpi-sub-pill">{html.escape(i8['sub_badge'])}</div>
                </div>
                <div class="card-scroll-box">
                    <div style="font-weight:800; color:#00205B; margin-bottom:4px;">✓ {html.escape(i8['notes_title'])}</div>
                    {notes8_html}
                </div>
                """, unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # [세부 1] 원가 절감 (8대 KPI에서 '1. 원가 절감' 클릭 시 이동 — 부문 통합 + 식안팀/품관팀 비교)
    # ------------------------------------------------------------------
    elif view == "cost":
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>1. 원가 절감 — 부문 통합 및 팀별(식품안전팀 · 품질관리팀) 추세 분석</span></div>", unsafe_allow_html=True)
        if df_cost.empty:
            st.error("원가절감 현황 시트 데이터를 불러오지 못했습니다.")
        else:
            fs_sum = round(float(df_cost["식품안전팀_실적(만원)"].sum()), 1)
            qc_sum = round(float(df_cost["품질관리팀_실적(만원)"].sum()), 1)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(f"품질안전부문 누적 (목표 {cost_targets['부문']}억)", f"{cost_actual_man:,.1f} 만원 ({cost_actual_uk}억)", f"달성률 {cost_rate}%")
            m2.metric(f"식품안전팀 누적 (목표 {cost_targets['식품안전팀']}억)", f"{fs_sum:,.1f} 만원", f"달성률 {round(fs_sum / (cost_targets['식품안전팀'] * 10000) * 100, 1)}%")
            m3.metric(f"품질관리팀 누적 (목표 {cost_targets['품질관리팀']}억)", f"{qc_sum:,.1f} 만원", f"달성률 {round(qc_sum / (cost_targets['품질관리팀'] * 10000) * 100, 1)}%")
            m4.metric("부문 연말(2월말) 추세 예상치", f"{cost_proj_man:,.1f} 만원 ({cost_proj_uk}억)", f"월 기울기 {cost_slope:+.1f}만/월")

            fig_cost = go.Figure()
            fig_cost.add_trace(go.Bar(
                x=df_cost["월"], y=df_cost["식품안전팀_실적(만원)"],
                name="식품안전팀 실적(만원)", marker_color="#003876",
                text=df_cost["식품안전팀_실적(만원)"], textposition="inside"
            ))
            fig_cost.add_trace(go.Bar(
                x=df_cost["월"], y=df_cost["품질관리팀_실적(만원)"],
                name="품질관리팀 실적(만원)", marker_color="#3B82F6",
                text=df_cost["품질관리팀_실적(만원)"], textposition="inside"
            ))
            fig_cost.add_trace(go.Scatter(
                x=df_cost["월"], y=df_cost["부문_기준(만원)"],
                name="부문 월 기준", mode="lines", line=dict(color="#DC2626", width=2.5, dash="dash")
            ))
            fig_cost.add_trace(go.Scatter(
                x=df_cost["월"], y=cost_act_line,
                name="실적 회귀 추세선", mode="lines+markers", line=dict(color="#7C3AED", width=3)
            ))
            if 0 <= cost_last_i < 11:
                fig_cost.add_trace(go.Scatter(
                    x=df_cost["월"], y=cost_fc_line,
                    name="AI 잔여월 예상 추세선", mode="lines+markers+text",
                    text=[f"{v:.0f}" if (v is not None and idx > cost_last_i) else "" for idx, v in enumerate(cost_fc_line)],
                    textposition="top center",
                    line=dict(color="#0EA5E9", width=3, dash="dot"),
                    marker=dict(symbol="diamond", size=9)
                ))
            fig_cost.update_layout(
                barmode="stack",
                height=400,
                title="📊 [품질안전부문 통합] 3월~2월 원가절감 실적 및 잔여월 예상 추세도 (단위: 만원)",
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF"
            )
            st.plotly_chart(fig_cost, use_container_width=True)

            st.markdown("---")
            st.subheader("🏢 팀별 원가절감 상세 성과 및 추세 비교 (좌: 식품안전팀 / 우: 품질관리팀)")
            team_left_col, team_right_col = st.columns(2)
            render_team_cost_panel(team_left_col, "식품안전팀", "#003876", cost_targets["식품안전팀"])
            render_team_cost_panel(team_right_col, "품질관리팀", "#3B82F6", cost_targets["품질관리팀"])

            st.markdown("---")
            st.subheader("📋 월별·팀별 원가절감 상세 수치 테이블")
            st.dataframe(df_cost.drop(columns=["_기록여부"], errors="ignore"), use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # [품질관리팀] 클레임 발생률 분석 (전사 추이 + 유제품/상온 부문별 + 전체 유형 집계표)
    # ------------------------------------------------------------------
    elif view == "claim":
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>📉 클레임 발생률 분석 — 전사 추이·AI 예상 추세도 및 부문별 분석</span></div>", unsafe_allow_html=True)
        if df_claim_cat.empty:
            st.error("클레임 건수 시트 데이터를 불러오지 못했습니다.")
        else:
            avail_claim_years = sorted(df_claim_cat["연도"].unique().tolist(), reverse=True)
            tab_c1, tab_c2, tab_c3 = st.tabs([
                "📈 전사 클레임 월별 추이 및 AI 예상 추세도 (2025 vs 2026)",
                "🏭 부문별 월단위 분석 및 예상 추세도 (유제품생산부문 vs 상온제품부문)",
                "🥛 전체 제품 유형별 상세 집계표"
            ])

            with tab_c1:
                sub_26_cats = df_claim_cat[(df_claim_cat["연도"] == "2026년") & (df_claim_cat["유형"] != "합계")]
                top_cat_txt = "-"
                if not sub_26_cats.empty:
                    top_r = sub_26_cats.sort_values("합계_건수", ascending=False).iloc[0]
                    top_cat_txt = f"{top_r['유형']} ({int(top_r['합계_건수']):,}건, {top_r['합계_PPM']}ppm)"

                ck1, ck2, ck3, ck4 = st.columns(4)
                ck1.metric("2026년 전사 누적 클레임", f"{claim_total_cnt:,} 건")
                ck2.metric("2026년 전사 누적 PPM (목표 1.12)", f"{claim_actual_ppm} ppm", "목표 이내" if claim_actual_ppm <= claim_target_ppm else "목표 초과")
                ck3.metric("월별 PPM 추세 기울기", f"{claim_slope:+.2f} ppm/월")
                ck4.metric("회계연도 말(2월) 예상 PPM", f"{claim_feb_pred:.2f} ppm", f"기록된 {claim_m_cnt}개월 추세 기준")

                rem_months_str = ", ".join(FISCAL_MONTHS[claim_last_i + 1:]) if 0 <= claim_last_i < 11 else "없음"
                pred_vals_str = ", ".join([
                    f"{FISCAL_MONTHS[i]} {claim_full_line[i]:.2f}ppm"
                    for i in range(claim_last_i + 1, 12)
                ]) if 0 <= claim_last_i < 11 else "연간 집계 완료"

                st.markdown(f"""
                <div class="forecast-box">
                    <b>🤖 전사 클레임 실시간 추세 및 AI 예상 추세 진단</b><br>
                    • <b>실적 추세 :</b> 현재 기록된 {claim_m_cnt}개월 누적 발생률은 <b>{claim_actual_ppm} ppm</b>(총 {claim_total_cnt:,}건)이며, 월평균 증감 기울기는 <b>{claim_slope:+.2f} ppm/월</b>입니다. (최다 발생 유형: {html.escape(top_cat_txt)})<br>
                    • <b>잔여월 예상 추세 ({rem_months_str}) :</b> 현재 선형 추세 연장 시 <b>{pred_vals_str}</b> 흐름으로 2월 당월 예상치는 <b>{claim_feb_pred:.2f} ppm</b>입니다.
                </div>
                """, unsafe_allow_html=True)

                fig_cl = go.Figure()
                fig_cl.add_trace(go.Bar(
                    x=df_claim_trend["월"], y=df_claim_trend["2025년_PPM"],
                    name="2025년 실적 PPM", marker_color="#CBD5E1",
                    text=df_claim_trend["2025년_PPM"], textposition="outside"
                ))
                fig_cl.add_trace(go.Bar(
                    x=df_claim_trend["월"], y=df_claim_trend["2026년_PPM"],
                    name="2026년 실적 PPM", marker_color="#003876",
                    text=[v if flag else "" for v, flag in zip(df_claim_trend["2026년_PPM"], df_claim_trend["_기록여부"])],
                    textposition="outside"
                ))
                fig_cl.add_trace(go.Scatter(
                    x=df_claim_trend["월"], y=df_claim_trend["목표_PPM"],
                    name="2026 목표 기준 (1.12 ppm)", mode="lines",
                    line=dict(color="#DC2626", width=2.5, dash="dash")
                ))
                fig_cl.add_trace(go.Scatter(
                    x=df_claim_trend["월"], y=claim_act_line,
                    name="2026 실적 추세선", mode="lines+markers",
                    line=dict(color="#7C3AED", width=3)
                ))
                if 0 <= claim_last_i < 11:
                    fig_cl.add_trace(go.Scatter(
                        x=df_claim_trend["월"], y=claim_fc_line,
                        name="AI 예상 추세선 (잔여월 예측)", mode="lines+markers+text",
                        text=[f"예상 {v:.2f}" if (v is not None and idx > claim_last_i) else "" for idx, v in enumerate(claim_fc_line)],
                        textposition="top center",
                        line=dict(color="#0284C7", width=3, dash="dot"),
                        marker=dict(symbol="diamond", size=9, color="#0284C7")
                    ))
                fig_cl.update_layout(barmode="group", height=430, title="📊 전사 2025년 vs 2026년 월별 클레임 PPM 및 잔여월 AI 예상 추세도", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                st.plotly_chart(fig_cl, use_container_width=True)

                disp_cl_trend = df_claim_trend.drop(columns=["_기록여부"], errors="ignore").copy()
                disp_cl_trend["추세/예상_PPM"] = claim_full_line
                st.dataframe(disp_cl_trend, use_container_width=True, hide_index=True)

            with tab_c2:
                cc1, cc2 = st.columns([1.2, 2.2])
                with cc1:
                    div_year = st.radio("조회 연도", avail_claim_years, horizontal=True, key="div_yr")
                with cc2:
                    div_sel = st.radio(
                        "조회 부문",
                        ["🥛 유제품생산부문 (냉장우유 카톤·병 / 발효유·음료 카톤·병)", "🧃 상온제품부문 (상온 멸균팩 / 상온 프리즈마)", "⚖️ 양 부문 통합 비교"],
                        horizontal=True, key="div_sel"
                    )

                df_dairy_m, df_dairy_raw = build_division_claim_df(df_claim_cat, div_year, DAIRY_CATEGORIES)
                df_rt_m, df_rt_raw = build_division_claim_df(df_claim_cat, div_year, RT_CATEGORIES)

                if "유제품생산부문" in div_sel:
                    t_df_m, t_df_raw, t_cats, d_lbl = df_dairy_m, df_dairy_raw, DAIRY_CATEGORIES, f"{div_year} 유제품생산부문"
                elif "상온제품부문" in div_sel:
                    t_df_m, t_df_raw, t_cats, d_lbl = df_rt_m, df_rt_raw, RT_CATEGORIES, f"{div_year} 상온제품부문"
                else:
                    t_df_m, t_df_raw, t_cats, d_lbl = None, None, [], f"{div_year} 유제품생산부문 vs 상온제품부문"

                if t_df_m is not None:
                    tot_c = int(t_df_m["합산_건수"].sum())
                    tot_p = int(t_df_m["합산_생산수량"].sum())
                    tot_ppm = round((tot_c / tot_p) * 1_000_000, 2) if tot_p > 0 else 0.0
                    d_act_l, d_fc_l, d_full_l, d_slp, _, d_last_i = calc_trend_and_forecast_split(
                        t_df_m["부문_통합_PPM"].tolist(),
                        t_df_m["_기록여부"].tolist()
                    )

                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("부문 누적 건수", f"{tot_c:,} 건")
                    k2.metric("부문 누적 생산량", f"{tot_p:,} 개")
                    k3.metric("부문 통합 PPM", f"{tot_ppm} ppm")
                    k4.metric("2월 예상 PPM (월 기울기)", f"{d_full_l[-1]:.2f} ppm", f"{d_slp:+.2f} ppm/월")

                    d_pred_txt = ", ".join([f"{FISCAL_MONTHS[i]} {d_full_l[i]:.2f}ppm" for i in range(d_last_i + 1, 12)]) if 0 <= d_last_i < 11 else "연간 집계 완료"
                    st.markdown(f"""
                    <div class="forecast-box">
                        <b>📌 {d_lbl} 추세 요약 :</b> 누적 <b>{tot_ppm} ppm</b> ({tot_c:,}건 / {tot_p:,}개) | 월 기울기 <b>{d_slp:+.2f} ppm/월</b> | 잔여월 예상: <b>{d_pred_txt}</b>
                    </div>
                    """, unsafe_allow_html=True)

                    fig_div = make_subplots(specs=[[{"secondary_y": True}]])
                    colors = ["#00205B", "#0052A5", "#3B82F6", "#93C5FD"]
                    for i, cat in enumerate(t_cats):
                        fig_div.add_trace(
                            go.Bar(
                                x=t_df_m["월"], y=t_df_m[f"{cat}_건수"], name=f"{cat} 건수",
                                marker_color=colors[i % 4], text=t_df_m[f"{cat}_건수"], textposition="inside"
                            ),
                            secondary_y=False
                        )
                    fig_div.add_trace(
                        go.Scatter(
                            x=t_df_m["월"], y=t_df_m["부문_통합_PPM"], name="부문 통합 PPM",
                            mode="lines+markers+text",
                            text=[v if flag else "" for v, flag in zip(t_df_m["부문_통합_PPM"], t_df_m["_기록여부"])],
                            textposition="top center", line=dict(color="#DC2626", width=3)
                        ),
                        secondary_y=True
                    )
                    fig_div.add_trace(go.Scatter(x=t_df_m["월"], y=d_act_l, name="실적 추세선", mode="lines", line=dict(color="#7C3AED", width=2.5)), secondary_y=True)
                    if 0 <= d_last_i < 11:
                        fig_div.add_trace(
                            go.Scatter(
                                x=t_df_m["월"], y=d_fc_l, name="AI 예상 추세선(잔여월)",
                                mode="lines+markers+text",
                                text=[f"{v:.2f}" if (v is not None and idx > d_last_i) else "" for idx, v in enumerate(d_fc_l)],
                                textposition="bottom center",
                                line=dict(color="#0284C7", width=3, dash="dot"),
                                marker=dict(symbol="diamond", size=8)
                            ),
                            secondary_y=True
                        )
                    fig_div.update_layout(barmode="stack", height=420, title=f"📊 {d_lbl} 월단위 건수 및 통합 PPM·예상 추세도", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                    fig_div.update_yaxes(title_text="클레임 건수(건)", secondary_y=False)
                    fig_div.update_yaxes(title_text="PPM", secondary_y=True)
                    st.plotly_chart(fig_div, use_container_width=True)

                    st.dataframe(t_df_m.drop(columns=["_기록여부"], errors="ignore"), use_container_width=True, hide_index=True)
                    st.dataframe(t_df_raw, use_container_width=True, hide_index=True)
                else:
                    _, dairy_fc, _, _, _, d_li = calc_trend_and_forecast_split(df_dairy_m["부문_통합_PPM"].tolist(), df_dairy_m["_기록여부"].tolist())
                    _, rt_fc, _, _, _, r_li = calc_trend_and_forecast_split(df_rt_m["부문_통합_PPM"].tolist(), df_rt_m["_기록여부"].tolist())
                    fig_cmp = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_cmp.add_trace(go.Bar(x=df_dairy_m["월"], y=df_dairy_m["합산_건수"], name="유제품생산 건수", marker_color="#003876"), secondary_y=False)
                    fig_cmp.add_trace(go.Bar(x=df_rt_m["월"], y=df_rt_m["합산_건수"], name="상온제품 건수", marker_color="#F59E0B"), secondary_y=False)
                    fig_cmp.add_trace(go.Scatter(x=df_dairy_m["월"], y=df_dairy_m["부문_통합_PPM"], name="유제품생산 PPM", mode="lines+markers", line=dict(color="#00205B", width=3)), secondary_y=True)
                    fig_cmp.add_trace(go.Scatter(x=df_rt_m["월"], y=df_rt_m["부문_통합_PPM"], name="상온제품 PPM", mode="lines+markers", line=dict(color="#DC2626", width=3)), secondary_y=True)
                    if 0 <= d_li < 11:
                        fig_cmp.add_trace(go.Scatter(x=df_dairy_m["월"], y=dairy_fc, name="유제품 예상 추세", mode="lines+markers", line=dict(color="#00205B", width=2, dash="dot")), secondary_y=True)
                    if 0 <= r_li < 11:
                        fig_cmp.add_trace(go.Scatter(x=df_rt_m["월"], y=rt_fc, name="상온 예상 추세", mode="lines+markers", line=dict(color="#DC2626", width=2, dash="dot")), secondary_y=True)
                    fig_cmp.update_layout(barmode="group", height=420, title=f"📊 {d_lbl} (실적 및 잔여월 예상 추세)", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                    st.plotly_chart(fig_cmp, use_container_width=True)

            with tab_c3:
                yr_opt = st.radio("연도 필터", avail_claim_years + ["전체"], horizontal=True, key="all_cat_yr")
                df_cv = df_claim_cat if yr_opt == "전체" else df_claim_cat[df_claim_cat["연도"] == yr_opt]
                st.dataframe(df_cv, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # [품질관리팀] 공정 현황 관제 (상온 · 유제품 · 두유배양 실시간 + 지난 날짜별 DB + 로트 역추적 탭)
    # ------------------------------------------------------------------
    elif view == "process":
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>🏭 공정 현황 및 특이사항 — 실시간 관제 · 날짜별 누적 이력 · 클레임 로트 역추적</span></div>", unsafe_allow_html=True)

        tab_p1, tab_p2, tab_p3, tab_p4 = st.tabs([
            f"🧃 [상온] 상온제품 공정 관리 일보 (금일 {rt_t_tab} & 전일 {rt_y_tab})",
            "🥛 [우유/발효유] 유제품 포장 공정관리 일보",
            f"🧪 [상온] 두유 배양검사 일보 (최신 작성 탭: {proc_data['soy_default_tab']})",
            "🔍 클레임 로트 역추적 (제품명·소비기한)"
        ])

        with tab_p1:
            if rt_t is None:
                st.warning("상온제품 공정 관리 일보 현재 탭 데이터를 불러오지 못했습니다. 아래 누적 이력 DB를 확인해 주세요.")
            else:
                b_left, b_right = st.columns(2)
                with b_left:
                    if today_real_notes:
                        notes_html = "<br>".join([f"• {html.escape(n)}" for n in today_real_notes])
                        st.markdown(f"<div class='issue-card-warn'><b>⚠️ 금일 [{html.escape(rt_t['tab_title'])}] 현장 특이사항 및 설비 조치 ({len(today_real_notes)}건)</b><br>{notes_html}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='issue-card-ok'><b>🟢 금일 [{html.escape(rt_t['tab_title'])}] 현장 특이사항 없음</b><br>• 전 가동 호기 및 멸균기 특이사항 없이 정상 생산 중입니다.</div>", unsafe_allow_html=True)

                with b_right:
                    if rt_y is not None:
                        if yest_real_notes:
                            yn_html = "<br>".join([f"• {html.escape(n)}" for n in yest_real_notes])
                            st.markdown(f"<div class='issue-card-warn'><b>📌 전일 [{html.escape(rt_y['tab_title'])}] 마감 특이사항 기록 ({len(yest_real_notes)}건)</b><br>{yn_html}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='issue-card-ok'><b>🟢 전일 [{html.escape(rt_y['tab_title'])}] 전 호기 특이사항 없이 정상 생산 마감</b><br>• 전일 설비 이상 및 품질 특이사항 기록 없음</div>", unsafe_allow_html=True)

                st.subheader(f"🟢 금일 [{rt_t['tab_title']}] 포장호기별 생산 제품·소비기한·확인시간 ({rt_t['prod_date']})")
                pack_cols = [
                    {"key": "ho", "label": "포장호기", "width": "10%", "align": "center"},
                    {"key": "prod", "label": "생산 제품명", "width": "44%", "align": "left"},
                    {"key": "exp", "label": "소비기한", "width": "16%", "align": "center"},
                    {"key": "time", "label": "확인시간", "width": "16%", "align": "center"},
                    {"key": "st", "label": "모니터링 상태", "width": "14%", "align": "center"}
                ]
                pack_rows_html = [
                    {
                        "ho": {"text": r["포장호기"], "cls": r["_cls"] if r["_cls"] == "cell-gray" else ""},
                        "prod": {"text": r["생산 제품명"], "cls": r["_cls"] if r["_cls"] == "cell-gray" else ""},
                        "exp": {"text": r["소비기한"], "cls": "cell-green" if r["_cls"] == "cell-green" else r["_cls"]},
                        "time": {"text": r["확인시간"], "cls": r["_cls"]},
                        "st": {"text": r["상태"], "cls": r["_cls"]}
                    }
                    for r in rt_t["lines_records"]
                ]
                st.markdown(render_html_table(pack_cols, pack_rows_html), unsafe_allow_html=True)

                st.subheader(f"🔥 금일 [{rt_t['tab_title']}] 멸균기 실시간 모니터링 [CCP-1B / CCP-2P] (우측 S~V열 기준 자동 대조)")
                ster_cols = [
                    {"key": "s_ho", "label": "멸균기 (포장)", "width": "9%", "align": "center"},
                    {"key": "prod", "label": "매칭 제품명 (용량)", "width": "22%", "align": "left"},
                    {"key": "time", "label": "확인시간", "width": "7%", "align": "center"},
                    {"key": "temp", "label": "멸균온도 [실측 (기준)]", "width": "13%", "align": "center"},
                    {"key": "press", "label": "균질압 [실측 (기준)]", "width": "11%", "align": "center"},
                    {"key": "hold", "label": "멸균시간 [실측 (기준)]", "width": "10%", "align": "center"},
                    {"key": "flow", "label": "처리량 / 냉각온도", "width": "10%", "align": "center"},
                    {"key": "flt", "label": "여과망 / 서명", "width": "8%", "align": "center"},
                    {"key": "rem", "label": "특이사항 (전문)", "width": "10%", "align": "left"}
                ]
                ster_rows_html = [
                    {
                        "s_ho": {"text": sr["멸균기_포장"], "cls": ""},
                        "prod": {"text": sr["매칭 제품명"], "cls": ""},
                        "time": {"text": sr["확인시간"], "cls": sr["_c_time"]},
                        "temp": {"text": sr["멸균온도"], "cls": sr["_c_temp"]},
                        "press": {"text": sr["균질압"], "cls": sr["_c_press"]},
                        "hold": {"text": sr["멸균시간"], "cls": sr["_c_hold"]},
                        "flow": {"text": sr["유량_냉각"], "cls": ""},
                        "flt": {"text": sr["여과망_서명"], "cls": sr["_c_flt"]},
                        "rem": {"text": sr["특이사항"], "cls": sr["_c_rem"]}
                    }
                    for sr in rt_t["ster_records"]
                ]
                st.markdown(render_html_table(ster_cols, ster_rows_html), unsafe_allow_html=True)

                st.subheader(f"🛡️ 금일 [{rt_t['tab_title']}] 포장기 공정관리 [CCP-3B] (농도·분사량·온도·E빔)")
                ccp3b_cols = [
                    {"key": "item", "label": "점검항목", "width": "10%", "align": "center"},
                    {"key": "std", "label": "관리기준", "width": "14%", "align": "center"},
                    {"key": "eq", "label": "적용설비", "width": "10%", "align": "center"},
                    {"key": "A호기", "label": "A호기", "width": "11%", "align": "center"},
                    {"key": "B호기", "label": "B호기", "width": "11%", "align": "center"},
                    {"key": "C호기", "label": "C호기", "width": "11%", "align": "center"},
                    {"key": "D호기", "label": "D호기", "width": "11%", "align": "center"},
                    {"key": "E호기", "label": "E호기", "width": "11%", "align": "center"},
                    {"key": "F호기", "label": "F호기", "width": "11%", "align": "center"}
                ]
                ccp3b_rows_html = []
                for r3 in rt_t["ccp3b_records"]:
                    row_obj = {
                        "item": {"text": r3["항목"], "cls": ""},
                        "std": {"text": r3["관리기준"], "cls": ""},
                        "eq": {"text": r3["적용설비"], "cls": ""}
                    }
                    for ho_nm in ["A호기", "B호기", "C호기", "D호기", "E호기", "F호기"]:
                        v_txt = r3.get(ho_nm, "-")
                        row_obj[ho_nm] = {"text": v_txt, "cls": eval_ccp3b_cell(v_txt, r3["관리기준"])}
                    ccp3b_rows_html.append(row_obj)
                st.markdown(render_html_table(ccp3b_cols, ccp3b_rows_html), unsafe_allow_html=True)

                if rt_y is not None:
                    st.markdown("---")
                    st.subheader(f"☑️ 전일 [{rt_y['tab_title']}] 마감 생산 제품 및 멸균·특이사항 전체 내역 ({rt_y['prod_date']})")
                    yest_cols = [
                        {"key": "ho", "label": "포장호기", "width": "8%", "align": "center"},
                        {"key": "prod", "label": "생산 제품명", "width": "28%", "align": "left"},
                        {"key": "exp", "label": "소비기한", "width": "12%", "align": "center"},
                        {"key": "time", "label": "확인시간", "width": "11%", "align": "center"},
                        {"key": "ster", "label": "멸균기·CCP 요약", "width": "21%", "align": "center"},
                        {"key": "rem", "label": "전일 특이사항 (전문)", "width": "20%", "align": "left"}
                    ]
                    yest_rows_html = [
                        {
                            "ho": {"text": yr["포장호기"], "cls": ""},
                            "prod": {"text": yr["생산 제품명"], "cls": ""},
                            "exp": {"text": yr["소비기한"], "cls": "cell-green"},
                            "time": {"text": yr["확인시간"], "cls": yr["_cls_status"]},
                            "ster": {"text": yr["멸균기·CCP 요약"], "cls": "cell-green" if yr["멸균기·CCP 요약"] != "-" else ""},
                            "rem": {"text": yr["특이사항"], "cls": yr["_cls_rem"]}
                        }
                        for yr in rt_y["compact_rows"]
                    ]
                    st.markdown(render_html_table(yest_cols, yest_rows_html), unsafe_allow_html=True)

            render_rt_history_section(proc_data["df_rt_hist_p"], proc_data["df_rt_hist_c"])

        with tab_p2:
            sub_m, sub_f = st.tabs([f"🥛 우유 포장 ({proc_data['milk_date']})", f"🍶 발효유 포장 ({proc_data['ferm_date']})"])
            dairy_cols = [
                {"key": "run", "label": "가동상태", "width": "11%", "align": "center"},
                {"key": "prod", "label": "제품명 (용량)", "width": "27%", "align": "left"},
                {"key": "time", "label": "확인시간", "width": "10%", "align": "center"},
                {"key": "exp", "label": "표기 소비기한", "width": "17%", "align": "center"},
                {"key": "c1", "label": "표시사항", "width": "7%", "align": "center"},
                {"key": "c2", "label": "상부접착", "width": "7%", "align": "center"},
                {"key": "c3", "label": "하부접착", "width": "7%", "align": "center"},
                {"key": "c4", "label": "제품용량", "width": "7%", "align": "center"},
                {"key": "c5", "label": "관능", "width": "7%", "align": "center"}
            ]

            def build_dairy_html_rows(df_d: pd.DataFrame):
                out_r = []
                for _, dr in df_d.iterrows():
                    running = "금일생산" in str(dr["가동여부"])
                    row_cls = "cell-green" if running else "cell-gray"

                    def chk_cls(v):
                        vs = str(v).strip()
                        if "부적합" in vs:
                            return "cell-red"
                        if vs not in ["", "-"]:
                            return "cell-green"
                        return "cell-yellow" if running else "cell-gray"

                    out_r.append({
                        "run": {"text": dr["가동여부"], "cls": row_cls},
                        "prod": {"text": dr["제품명"], "cls": "" if running else "cell-gray"},
                        "time": {"text": dr["확인시간"], "cls": chk_cls(dr["확인시간"])},
                        "exp": {"text": dr["표기 소비기한"], "cls": "cell-green" if running and dr["표기 소비기한"] != "-" else ("cell-gray" if not running else "cell-yellow")},
                        "c1": {"text": dr["표시사항"], "cls": chk_cls(dr["표시사항"])},
                        "c2": {"text": dr["상부접착"], "cls": chk_cls(dr["상부접착"])},
                        "c3": {"text": dr["하부접착"], "cls": chk_cls(dr["하부접착"])},
                        "c4": {"text": dr["제품용량"], "cls": chk_cls(dr["제품용량"])},
                        "c5": {"text": dr["관능(5점법)"], "cls": chk_cls(dr["관능(5점법)"])}
                    })
                return out_r

            with sub_m:
                if proc_data["df_milk_pack"].empty:
                    st.info("현재 시트에 활성화된 '우유' 작업 탭이 없습니다 (결재 후 삭제됨). 바로 아래 [누적 이력 DB]에서 당일 및 지난 날짜 기록을 모두 확인하실 수 있습니다.")
                else:
                    only_run_m = st.checkbox("금일 실제 생산 품목만 보기 (00.00 제외)", value=True, key="chk_milk")
                    df_m_v = proc_data["df_milk_pack"]
                    if only_run_m and not df_m_v.empty:
                        df_m_v = df_m_v[df_m_v["가동여부"].str.contains("금일생산", na=False)]
                    st.markdown(render_html_table(dairy_cols, build_dairy_html_rows(df_m_v)), unsafe_allow_html=True)

            with sub_f:
                if proc_data["df_ferm_pack"].empty:
                    st.info("현재 시트에 활성화된 '발효유' 작업 탭이 없습니다 (결재 후 삭제됨). 바로 아래 [누적 이력 DB]에서 당일 및 지난 날짜 기록을 모두 확인하실 수 있습니다.")
                else:
                    only_run_f = st.checkbox("금일 실제 생산 품목만 보기 (00.00 제외)", value=True, key="chk_ferm")
                    df_f_v = proc_data["df_ferm_pack"]
                    if only_run_f and not df_f_v.empty:
                        df_f_v = df_f_v[df_f_v["가동여부"].str.contains("금일생산", na=False)]
                    st.markdown(render_html_table(dairy_cols, build_dairy_html_rows(df_f_v)), unsafe_allow_html=True)

            render_dairy_history_section(proc_data["df_dairy_hist_p"], proc_data["df_dairy_hist_c"])

        with tab_p3:
            soy_map = proc_data["soy_tabs_map"]
            if not soy_map:
                st.warning("두유 배양검사 일보 현재 날짜 탭 데이터를 불러오지 못했습니다. 아래 누적 이력 DB를 확인해 주세요.")
            else:
                tab_keys = list(soy_map.keys())
                def_idx = tab_keys.index(proc_data["soy_default_tab"]) if proc_data["soy_default_tab"] in tab_keys else 0
                sel_soy_tab = st.selectbox("조회할 배양검사 하단 시트 탭 날짜 선택 (하단 탭 날짜 최신순)", tab_keys, index=def_idx)
                df_sb, df_sh = soy_map[sel_soy_tab]

                tot_samples = sum(int(to_float(x, 0)) for x in df_sb["총 검사수량"]) if not df_sb.empty else 0
                uninsp_cnt = int((~df_sb["검사완료여부"]).sum()) if (not df_sb.empty and "검사완료여부" in df_sb.columns) else 0
                insp_cnt = len(df_sb) - uninsp_cnt

                if uninsp_cnt > 0:
                    st.markdown(
                        f"<div class='issue-card-warn'><b>🟡 [{html.escape(sel_soy_tab)} 탭] 배양검사 진행 현황 : 총 {len(df_sb)}호기 중 "
                        f"검사완료 {insp_cnt}건 / 검사전 {uninsp_cnt}건 대기</b><br>"
                        f"• 검사자 성명이 아직 기입되지 않은 호기는 <b>검사전(배양중·개봉대기)</b> 상태로 자동 분류됩니다.</div>",
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"<div class='issue-card-ok'><b>🟢 [{html.escape(sel_soy_tab)} 탭] 전 호기({len(df_sb)}건) 검사자 확인 및 배양검사 완료 (총 {tot_samples:,}개)</b></div>",
                        unsafe_allow_html=True
                    )

                st.subheader(f"🔬 [{sel_soy_tab} 탭] 호기별 작성자·검사자 확인 및 배양 판독 내역")

                soy_cols = [
                    {"key": "ho", "label": "포장기", "width": "6%", "align": "center"},
                    {"key": "inc", "label": "배양구분", "width": "9%", "align": "center"},
                    {"key": "vol", "label": "용량", "width": "5%", "align": "center"},
                    {"key": "item", "label": "품목명", "width": "21%", "align": "left"},
                    {"key": "pdt", "label": "생산일", "width": "8%", "align": "center"},
                    {"key": "exp", "label": "소비기한", "width": "8%", "align": "center"},
                    {"key": "time", "label": "가동시간", "width": "10%", "align": "center"},
                    {"key": "qty", "label": "검사수량", "width": "6%", "align": "center"},
                    {"key": "wrt", "label": "작성자", "width": "6%", "align": "center"},
                    {"key": "ins", "label": "검사자", "width": "8%", "align": "center"},
                    {"key": "st", "label": "진행상태", "width": "7%", "align": "center"},
                    {"key": "jdg", "label": "오염/판정", "width": "6%", "align": "center"}
                ]
                soy_rows_html = []
                for _, sr in df_sb.iterrows():
                    done_flag = bool(sr.get("검사완료여부", False))
                    is_zero_contam = to_float(sr["오염수량"], 0) == 0
                    jdg_txt = str(sr["판정"]).strip()

                    if not done_flag:
                        st_cls = "cell-yellow"
                        jdg_disp = "검사전"
                        jdg_cls = "cell-yellow"
                    elif not is_zero_contam or "부적합" in jdg_txt:
                        st_cls = "cell-red"
                        jdg_disp = f"{sr['오염수량']} / {jdg_txt}"
                        jdg_cls = "cell-red"
                    else:
                        st_cls = "cell-green"
                        jdg_disp = f"{sr['오염수량']} / {jdg_txt}"
                        jdg_cls = "cell-green"

                    soy_rows_html.append({
                        "ho": {"text": sr["포장기"], "cls": ""},
                        "inc": {"text": sr["배양구분"], "cls": ""},
                        "vol": {"text": sr["용량(mL)"], "cls": ""},
                        "item": {"text": sr["품목명"], "cls": ""},
                        "pdt": {"text": sr["생산일"], "cls": ""},
                        "exp": {"text": sr["소비기한"], "cls": ""},
                        "time": {"text": f"{sr['생산 시작~종료']}\n({sr['실가동시간']})", "cls": ""},
                        "qty": {"text": sr["총 검사수량"], "cls": "cell-green" if done_flag else ""},
                        "wrt": {"text": sr["작성자"], "cls": ""},
                        "ins": {"text": sr["검사자"], "cls": st_cls},
                        "st": {"text": sr["진행상태"], "cls": st_cls},
                        "jdg": {"text": jdg_disp, "cls": jdg_cls}
                    })
                st.markdown(render_html_table(soy_cols, soy_rows_html), unsafe_allow_html=True)

                if not df_sh.empty:
                    with st.expander("⏰ 시간대별(08시~07시) 샘플·Strip·Paper 체크 상세 보기"):
                        st.dataframe(df_sh, use_container_width=True, hide_index=True)

            render_soy_history_section(proc_data["df_soy_hist"])

        with tab_p4:
            render_lot_traceability_tab(proc_data, widget_prefix="proc_lot")

    # ------------------------------------------------------------------
    # [품질관리팀] 클레임 로트 역추적 전용 페이지 (좌측 탭 & 메인 특이사항 LOT 추적 버튼 직결)
    # ------------------------------------------------------------------
    elif view == "lot_trace":
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>🔍 클레임 로트 역추적 — '제품명 식품안전나라' 표준 품목 & 소비기한 통합 조회</span></div>", unsafe_allow_html=True)
        render_lot_traceability_tab(proc_data, widget_prefix="lot")

    # ------------------------------------------------------------------
    # [식품안전팀] 협력업체 서류심사 관리 (협력업체 DB + 6번 KPI 목표/실적 연동)
    # ------------------------------------------------------------------
    elif view in ("supplier", "kpi_11"):
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>🤝 협력업체 서류심사 관리 — 등급 집계 · 미비사항 · 실행률 관리</span></div>", unsafe_allow_html=True)
        tab_s1, tab_s2 = st.tabs([
            "📋 2026년 원·부자재 및 OEM 서류심사 확정 집계 & 등급 외 미비사항",
            "⚙️ 6. 협력업체 관리강화 KPI 대표 수치 설정"
        ])

        with tab_s1:
            if df_sup_master.empty:
                st.error("협력업체 심사 결과 DB를 불러오지 못했습니다.")
            else:
                st.dataframe(df_sup_grade, use_container_width=True, hide_index=True)

                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    g_opts = ["전체"] + sorted(df_sup_master["구분"].dropna().unique().tolist())
                    sel_g = st.selectbox("구분 필터", g_opts)
                with fc2:
                    sel_r = st.selectbox("결과 필터", ["전체", "승인", "지도", "등급 외"])
                with fc3:
                    kw_s = st.text_input("업체명 / 품목 검색")

                df_sf = df_sup_master.copy()
                if sel_g != "전체":
                    df_sf = df_sf[df_sf["구분"] == sel_g]
                if sel_r != "전체":
                    df_sf = df_sf[df_sf["결과"] == sel_r]
                if kw_s:
                    df_sf = df_sf[df_sf["업체명"].str.contains(kw_s, case=False, na=False) | df_sf["품목"].str.contains(kw_s, case=False, na=False)]

                st.dataframe(df_sf, use_container_width=True, hide_index=True, height=380)

                st.subheader("■ 등급 외 업체 주요 미비사항")
                uc1, uc2 = st.columns([1, 1.45])
                with uc1:
                    st.dataframe(df_sup_under_c, use_container_width=True, hide_index=True)
                with uc2:
                    st.dataframe(df_sup_under_d, use_container_width=True, hide_index=True)

        with tab_s2:
            render_manual_kpi_editor_section("kpi_11", key_suffix="sup")

    # ------------------------------------------------------------------
    # [식품안전팀] 심사점수 · 일정 온도계 (7. 심사점수)
    # ------------------------------------------------------------------
    elif view == "kpi_5":
        info5 = st.session_state["manual_kpis"]["kpi_5"]
        aud_sum = get_active_audit_summary(df_audit_sched, today_kst_str)

        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>🌡️ 심사점수 · 일정 온도계 — 연간 심사 일정 등록 및 실시간 진행현황 관리</span></div>", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="forecast-box">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                <div>
                    <b style="font-size:16px; color:#00205B;">{html.escape(aud_sum['banner_text'])}</b><br>
                    <span style="font-size:13.5px; color:#475569;">
                        현재 대표 심사점수 — <b>목표 : {html.escape(info5['target_text'])}</b> &nbsp;|&nbsp;
                        <b>실적 : {html.escape(info5['actual_text'])}</b> ({html.escape(info5['sub_badge'])})
                    </span>
                </div>
                <span class="badge-pill" style="font-size:13.5px; padding:5px 14px; background:{aud_sum['color']}; color:#FFFFFF;">
                    {html.escape(aud_sum['icon'])} 현재 단계 : {html.escape(aud_sum['status'])} ({aud_sum['pct']}%)
                </span>
            </div>
            <div class="thermo-row" style="margin-top:10px;">
                <div class="thermo-bulb" style="width:28px; height:28px; font-size:15px; background-color:{aud_sum['color']};">🌡️</div>
                <div class="thermo-track" style="height:18px;">
                    <div class="thermo-fill" style="width:{aud_sum['pct']}%; background-color:{aud_sum['color']};"></div>
                </div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:11.8px; color:#64748B; font-weight:700; padding:0 4px;">
                <span>📋 심사준비중(20%)</span>
                <span>🔍 심사중(50%)</span>
                <span>📑 서류심사중(75%)</span>
                <span>🏭 현장심사중(85%)</span>
                <span>✅ 심사종료(100%)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_add, col_score = st.columns([1.25, 1.0])

        with col_add:
            st.subheader("➕ 신규 심사 일정 등록 (시트 자동 저장)")
            with st.form("form_add_audit_schedule", clear_on_submit=True):
                fa1, fa2 = st.columns([1, 1])
                with fa1:
                    in_audit_dt = st.date_input("심사 일자", value=now_kst().date())
                with fa2:
                    in_audit_st = st.selectbox("초기 진행현황", AUDIT_STATUS_LIST, index=0)
                in_audit_nm = st.text_input("심사명 / 심사 내용 (예: 아산공장 HACCP 정기심사, FSSC 22000 사후심사)")
                fa3, fa4 = st.columns([1, 1.5])
                with fa3:
                    in_audit_sc = st.text_input("획득 점수 (종료 시 선택 입력, 예: 95.2점)")
                with fa4:
                    in_audit_memo = st.text_input("비고 / 중점 대응 메모")

                if st.form_submit_button("💾 심사 일정 추가 및 시트 저장"):
                    if not in_audit_nm.strip():
                        st.warning("심사명(심사 내용)을 입력해 주세요.")
                    else:
                        new_row = pd.DataFrame([{
                            "고유ID": str(uuid.uuid4())[:8],
                            "심사일자": in_audit_dt.strftime("%Y-%m-%d"),
                            "심사명": in_audit_nm.strip(),
                            "진행현황": in_audit_st,
                            "점수": in_audit_sc.strip(),
                            "비고": in_audit_memo.strip(),
                            "수정일시": now_kst().strftime("%Y-%m-%d %H:%M:%S")
                        }])
                        updated_df = pd.concat([df_audit_sched, new_row], ignore_index=True)
                        ok_s, msg_s = save_audit_schedule_df_to_sheet(updated_df)
                        if ok_s:
                            st.success(msg_s)
                            st.rerun()
                        else:
                            st.error(msg_s)

        with col_score:
            st.subheader("🎯 7. 심사점수 대표 수치 수정 (시트 영구 저장)")
            with st.form("form_kpi5_score_edit"):
                s_t_txt = st.text_input("목표 점수 문구", value=info5["target_text"])
                s_a_txt = st.text_input("실적 점수 문구", value=info5["actual_text"])
                s_badge = st.text_input("대비/보조 배지 문구", value=info5["sub_badge"])
                n1, n2 = st.columns(2)
                with n1:
                    s_t_num = st.number_input("목표 점수(숫자)", value=float(info5["target_num"]), step=0.01)
                with n2:
                    s_a_num = st.number_input("실적 점수(숫자)", value=float(info5["actual_num"]), step=0.01)
                sig_opts = ["green", "yellow", "red", "gray"]
                sig_labels = {"green": "🟢 양호 (초록)", "yellow": "🟡 주의 (노랑)", "red": "🔴 경고 (빨강)", "gray": "⚪ 대기 (회색)"}
                s_sig = st.selectbox(
                    "카드 신호등 색상",
                    sig_opts,
                    index=sig_opts.index(info5["signal"]) if info5["signal"] in sig_opts else 0,
                    format_func=lambda x: sig_labels[x]
                )
                if st.form_submit_button("💾 대표 점수 저장"):
                    updated_k5 = {
                        **info5,
                        "target_text": s_t_txt.strip(),
                        "actual_text": s_a_txt.strip(),
                        "compact_val": s_a_txt.split(",")[0].strip(),
                        "sub_badge": s_badge.strip(),
                        "target_num": float(s_t_num),
                        "actual_num": float(s_a_num),
                        "signal": s_sig
                    }
                    st.session_state["manual_kpis"]["kpi_5"] = updated_k5
                    ok_m, msg_m = save_manual_kpi_to_sheet("kpi_5", updated_k5)
                    if ok_m:
                        st.success(msg_m)
                        st.rerun()
                    else:
                        st.warning(msg_m)

        st.markdown("---")
        st.subheader("🌡️ 등록된 심사 일정 진행현황 실시간 변경 및 전체 목록")

        if df_audit_sched.empty:
            st.info("아직 등록된 심사 일정이 없습니다. 위 '신규 심사 일정 등록'에서 날짜와 심사 내용을 추가해 주세요.")
        else:
            df_sorted_aud = df_audit_sched.sort_values("심사일자", ascending=True).reset_index(drop=True)
            opt_labels = [
                f"[{r['심사일자']}] {r['심사명']} (현재: {r['진행현황']})"
                for _, r in df_sorted_aud.iterrows()
            ]
            sel_idx = st.selectbox("상태를 변경하거나 수정·삭제할 심사 선택", range(len(opt_labels)), format_func=lambda i: opt_labels[i])
            sel_row = df_sorted_aud.iloc[sel_idx]
            sel_uid = sel_row["고유ID"]

            with st.form("form_update_audit_status"):
                u1, u2, u3 = st.columns([1.0, 1.6, 1.1])
                with u1:
                    parsed_d = pd.to_datetime(sel_row["심사일자"], errors="coerce")
                    def_d = parsed_d.date() if pd.notna(parsed_d) else now_kst().date()
                    up_dt = st.date_input("심사 일자 수정", value=def_d)
                with u2:
                    up_nm = st.text_input("심사명 수정", value=str(sel_row["심사명"]))
                with u3:
                    cur_st_idx = AUDIT_STATUS_LIST.index(sel_row["진행현황"]) if sel_row["진행현황"] in AUDIT_STATUS_LIST else 0
                    up_st = st.selectbox("🌡️ 실시간 진행현황 선택", AUDIT_STATUS_LIST, index=cur_st_idx)

                u4, u5 = st.columns([1.0, 2.0])
                with u4:
                    up_sc = st.text_input("획득 점수", value=str(sel_row.get("점수", "")))
                with u5:
                    up_memo = st.text_input("비고 / 특이사항", value=str(sel_row.get("비고", "")))

                b_col_save, b_col_del = st.columns([3, 1])
                with b_col_save:
                    do_update = st.form_submit_button("✅ 선택한 심사 진행현황·내용 즉시 반영")
                with b_col_del:
                    do_delete = st.form_submit_button("🗑️ 이 일정 삭제")

                if do_update:
                    df_mod = df_audit_sched.copy()
                    mask = df_mod["고유ID"] == sel_uid
                    df_mod.loc[mask, "심사일자"] = up_dt.strftime("%Y-%m-%d")
                    df_mod.loc[mask, "심사명"] = up_nm.strip()
                    df_mod.loc[mask, "진행현황"] = up_st
                    df_mod.loc[mask, "점수"] = up_sc.strip()
                    df_mod.loc[mask, "비고"] = up_memo.strip()
                    df_mod.loc[mask, "수정일시"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
                    ok_u, msg_u = save_audit_schedule_df_to_sheet(df_mod)
                    if ok_u:
                        st.success(msg_u)
                        st.rerun()
                    else:
                        st.error(msg_u)

                if do_delete:
                    df_rem = df_audit_sched[df_audit_sched["고유ID"] != sel_uid].copy()
                    ok_d, msg_d = save_audit_schedule_df_to_sheet(df_rem)
                    if ok_d:
                        st.success("선택한 심사 일정이 삭제되었습니다.")
                        st.rerun()
                    else:
                        st.error(msg_d)

            aud_cols = [
                {"key": "dday", "label": "구분", "width": "10%", "align": "center"},
                {"key": "dt", "label": "심사일자", "width": "12%", "align": "center"},
                {"key": "nm", "label": "심사명 (내용)", "width": "30%", "align": "left"},
                {"key": "st", "label": "진행현황 (게이지)", "width": "16%", "align": "center"},
                {"key": "sc", "label": "결과 점수", "width": "10%", "align": "center"},
                {"key": "memo", "label": "비고", "width": "22%", "align": "left"}
            ]
            today_d_obj = now_kst().date()
            aud_html_rows = []
            for _, ar in df_sorted_aud.iterrows():
                a_dt = pd.to_datetime(ar["심사일자"], errors="coerce")
                if pd.notna(a_dt):
                    diff_d = (a_dt.date() - today_d_obj).days
                    if diff_d == 0:
                        d_txt, d_cls = "🚨 금일심사", "cell-red"
                    elif diff_d > 0:
                        d_txt, d_cls = f"D-{diff_d}", "cell-yellow" if diff_d <= 7 else ""
                    else:
                        d_txt, d_cls = f"경과({abs(diff_d)}일)", "cell-gray"
                else:
                    d_txt, d_cls = "-", ""

                st_v = ar["진행현황"]
                pct_v = AUDIT_STATUS_CONFIG.get(st_v, {"pct": 20})["pct"]
                st_c = "cell-green" if st_v == "심사종료" else ("cell-yellow" if st_v in ["심사중", "서류심사중", "현장심사중"] else "")

                aud_html_rows.append({
                    "dday": {"text": d_txt, "cls": d_cls},
                    "dt": {"text": ar["심사일자"], "cls": "cell-red" if d_txt == "🚨 금일심사" else ""},
                    "nm": {"text": ar["심사명"], "cls": ""},
                    "st": {"text": f"{st_v} ({pct_v}%)", "cls": st_c},
                    "sc": {"text": ar["점수"] if str(ar["점수"]).strip() else "-", "cls": "cell-green" if str(ar["점수"]).strip() else ""},
                    "memo": {"text": ar["비고"] if str(ar["비고"]).strip() else "-", "cls": ""}
                })
            st.markdown(render_html_table(aud_cols, aud_html_rows), unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # [식품안전팀] 표시사항 진행 현황 (검토중 목록 + 특이사항 메모 편집 + 전년비 증가 분석)
    # ------------------------------------------------------------------
    elif view == "label_status":
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>🏷️ 표시사항 진행 현황 — 현재 검토중 품목 · 특이사항 관리 · 전년 대비 업무량 분석</span></div>", unsafe_allow_html=True)
        if df_label_status.empty:
            st.error("표시사항 현황 시트 데이터를 불러오지 못했습니다.")
        else:
            if broken_date_cnt > 0:
                st.warning(f"참고: 시트 원본에 텍스트 '#######'로 저장되어 연도 분류에서 제외된 행이 {broken_date_cnt}건 있습니다.")

            df_valid_lb = df_label_status[df_label_status["분류"] != "제외(개시/준비·보류)"].copy()
            df_2025 = df_valid_lb[df_valid_lb["_yr_num"] == 2025]
            df_2026 = df_valid_lb[df_valid_lb["_yr_num"] == 2026]

            cnt_25_all = len(df_2025)
            cnt_26_all = len(df_2026)

            max_m_26 = int(df_2026["_mo_num"].max()) if not df_2026.empty and df_2026["_mo_num"].max() > 0 else now_kst().month
            active_m_25 = max(int(df_2025[df_2025["_mo_num"] > 0]["_mo_num"].nunique()), 1) if not df_2025.empty else 12
            active_m_26 = max(int(df_2026[df_2026["_mo_num"] > 0]["_mo_num"].nunique()), 1) if not df_2026.empty else max_m_26

            cnt_25_ytd = len(df_2025[(df_2025["_mo_num"] >= 1) & (df_2025["_mo_num"] <= max_m_26)])
            cnt_26_ytd = len(df_2026[(df_2026["_mo_num"] >= 1) & (df_2026["_mo_num"] <= max_m_26)])
            ytd_diff = cnt_26_ytd - cnt_25_ytd
            ytd_pct = round((ytd_diff / cnt_25_ytd) * 100, 1) if cnt_25_ytd > 0 else 0.0

            m_avg_25 = round(cnt_25_all / active_m_25, 1) if cnt_25_all > 0 else 0.0
            m_avg_26 = round(cnt_26_all / active_m_26, 1) if cnt_26_all > 0 else 0.0
            avg_diff = round(m_avg_26 - m_avg_25, 1)

            tab_lb1, tab_lb2, tab_lb3 = st.tabs([
                f"🔴 현재 검토중 목록 ({reviewing_cnt}건) & 표시사항 특이사항 메모",
                "📈 전년 대비(2025 vs 2026) 업무량 증가 및 급증 제품군 분석",
                "📋 전체 표시사항 심의 이력 통합 검색"
            ])

            with tab_lb1:
                show_cols = [c for c in ["*docNo", "상태", "제목", "요청부서", "대분류(마케팅 카테고리)", "보관방법", "생산처", "검토 포장재 유형", "등록일자", "최종수정자"] if c in df_label_status.columns]
                st.subheader(f"📌 현재 [식품안전팀 검토중] 전체 목록 ({reviewing_cnt}건)")
                st.dataframe(df_label_status[df_label_status["분류"] == "식품안전팀 검토중"][show_cols], use_container_width=True, hide_index=True)

                st.markdown("---")
                st.subheader("📝 표시사항 특이사항 메모 관리 (메인 통합 관제판과 실시간 공유)")
                with st.form("form_detail_lbl_memo"):
                    edit_lm = st.text_area("원자재 변경 · 신규 알레르기 · 법규 개정 점검 메모", value=st.session_state.get("label_special_memo", ""), height=120)
                    if st.form_submit_button("💾 표시사항 특이사항 메모 저장"):
                        ok_l, msg_l = save_special_boards_to_sheet(edit_lm.strip(), st.session_state["claim_special_list"])
                        if ok_l:
                            st.success(msg_l)
                        else:
                            st.warning(msg_l)
                        st.rerun()

                if "요청부서" in df_valid_lb.columns:
                    st.subheader("🏢 요청부서(등록팀)별 2025년 vs 2026년 의뢰 현황")
                    d25 = df_2025.groupby("요청부서").size().rename("2025년")
                    d26 = df_2026.groupby("요청부서").size().rename("2026년")
                    d_now = df_valid_lb[df_valid_lb["분류"] == "식품안전팀 검토중"].groupby("요청부서").size().rename("현재_검토중")
                    dept_cmp = pd.concat([d25, d26, d_now], axis=1).fillna(0).astype(int).reset_index()
                    dept_cmp["증감(26-25)"] = dept_cmp["2026년"] - dept_cmp["2025년"]
                    dept_cmp = dept_cmp.sort_values("2026년", ascending=False)
                    st.dataframe(dept_cmp, use_container_width=True, hide_index=True)

            with tab_lb2:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(f"2026년 누적 검토 (1~{max_m_26}월)", f"{cnt_26_all:,} 건", f"동기간 전년비 {ytd_diff:+,}건 ({ytd_pct:+.1f}%)")
                m2.metric("전년도(2025년) 연간 실적", f"{cnt_25_all:,} 건", f"25년 1~{max_m_26}월 동기간 {cnt_25_ytd:,}건")
                m3.metric("월평균 검토 처리량 변화", f"월 {m_avg_26} 건", f"25년 월 {m_avg_25}건 대비 {avg_diff:+.1f}건/월")
                m4.metric("현재 실시간 검토 진행", f"{reviewing_cnt:,} 건", f"누적 완료 총 {completed_cnt:,}건")

                cat_col_nm = "대분류(마케팅 카테고리)" if "대분류(마케팅 카테고리)" in df_valid_lb.columns else None
                top_growth_txt = "-"
                df_cat_cmp = pd.DataFrame()
                if cat_col_nm:
                    c25 = df_2025.groupby(cat_col_nm).size().rename("2025년_건수")
                    c26 = df_2026.groupby(cat_col_nm).size().rename("2026년_건수")
                    df_cat_cmp = pd.concat([c25, c26], axis=1).fillna(0).astype(int).reset_index()
                    df_cat_cmp[cat_col_nm] = df_cat_cmp[cat_col_nm].replace("", "미분류")
                    df_cat_cmp["증감(건)"] = df_cat_cmp["2026년_건수"] - df_cat_cmp["2025년_건수"]
                    df_cat_cmp["26년_비중(%)"] = round(df_cat_cmp["2026년_건수"] / max(cnt_26_all, 1) * 100, 1)
                    df_cat_cmp = df_cat_cmp.sort_values("2026년_건수", ascending=False)
                    if not df_cat_cmp.empty:
                        top_g = df_cat_cmp.sort_values("증감(건)", ascending=False).iloc[0]
                        top_growth_txt = f"{top_g[cat_col_nm]} (25년 {top_g['2025년_건수']}건 → 26년 {top_g['2026년_건수']}건, {top_g['증감(건)']:+d}건)"

                st.markdown(f"""
                <div class="forecast-box">
                    <b>📊 표시사항 심의·검토 업무량 증가 팩트 요약</b><br>
                    • <b>동기간 처리량 비교 :</b> 1~{max_m_26}월 동기간 기준 2025년 <b>{cnt_25_ytd:,}건</b>에서 2026년 <b>{cnt_26_ytd:,}건</b>으로 <b>{ytd_diff:+,}건({ytd_pct:+.1f}%)</b> 변동했으며, 월평균 처리 건수는 <b>{m_avg_25}건/월 → {m_avg_26}건/월({avg_diff:+.1f}건/월)</b> 수준입니다.<br>
                    • <b>최다 증가 제품 카테고리 :</b> <b>{html.escape(top_growth_txt)}</b> 제품군을 중심으로 표시사항 신규·변경 검토 건수가 집중되고 있습니다.
                </div>
                """, unsafe_allow_html=True)

                g_left, g_right = st.columns(2)
                with g_left:
                    m_cmp_rows = [
                        {"월": f"{m_i}월", "2025년": int((df_2025["_mo_num"] == m_i).sum()), "2026년": int((df_2026["_mo_num"] == m_i).sum())}
                        for m_i in range(1, 13)
                    ]
                    df_mcmp = pd.DataFrame(m_cmp_rows)
                    fig_mcmp = go.Figure()
                    fig_mcmp.add_trace(go.Bar(x=df_mcmp["월"], y=df_mcmp["2025년"], name="2025년 건수", marker_color="#CBD5E1", text=df_mcmp["2025년"], textposition="outside"))
                    fig_mcmp.add_trace(go.Bar(x=df_mcmp["월"], y=df_mcmp["2026년"], name="2026년 건수", marker_color="#003876", text=df_mcmp["2026년"], textposition="outside"))
                    fig_mcmp.update_layout(barmode="group", height=350, title="📅 월별 표시사항 심의 건수 비교 (2025년 vs 2026년)", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                    st.plotly_chart(fig_mcmp, use_container_width=True)

                with g_right:
                    if not df_cat_cmp.empty:
                        fig_cat = go.Figure()
                        fig_cat.add_trace(go.Bar(x=df_cat_cmp[cat_col_nm], y=df_cat_cmp["2025년_건수"], name="2025년", marker_color="#94A3B8", text=df_cat_cmp["2025년_건수"], textposition="outside"))
                        fig_cat.add_trace(go.Bar(x=df_cat_cmp[cat_col_nm], y=df_cat_cmp["2026년_건수"], name="2026년", marker_color="#0052A5", text=df_cat_cmp["2026년_건수"], textposition="outside"))
                        fig_cat.update_layout(barmode="group", height=350, title="🥛 제품 대분류(카테고리)별 검토 건수 증가 비교", paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF")
                        st.plotly_chart(fig_cat, use_container_width=True)

                b_col1, b_col2, b_col3 = st.columns(3)
                with b_col1:
                    st.markdown("##### 📦 제품 카테고리별 증감표")
                    if not df_cat_cmp.empty:
                        st.dataframe(df_cat_cmp, use_container_width=True, hide_index=True)
                with b_col2:
                    st.markdown("##### 🏭 2026년 주요 생산처 TOP 10")
                    if "생산처" in df_2026.columns and not df_2026.empty:
                        prod_site_df = df_2026["생산처"].replace("", "미기입").value_counts().head(10).reset_index()
                        prod_site_df.columns = ["생산처(자체/OEM)", "2026년_검토건수"]
                        st.dataframe(prod_site_df, use_container_width=True, hide_index=True)
                with b_col3:
                    st.markdown("##### 🏷️ 2026년 포장재 유형")
                    if "검토 포장재 유형" in df_2026.columns and not df_2026.empty:
                        pkg_df = df_2026["검토 포장재 유형"].replace("", "미기입").value_counts().head(10).reset_index()
                        pkg_df.columns = ["검토 포장재 유형", "2026년_검토건수"]
                        st.dataframe(pkg_df, use_container_width=True, hide_index=True)

            with tab_lb3:
                show_cols = [c for c in ["*docNo", "상태", "제목", "요청부서", "대분류(마케팅 카테고리)", "보관방법", "생산처", "검토 포장재 유형", "등록일자", "최종수정자"] if c in df_label_status.columns]
                kw_lb = st.text_input("🔍 품목 제목 / 요청부서 / 생산처 검색")
                df_lv = df_label_status[show_cols + ["분류", "등록연도", "등록월"]]
                if kw_lb:
                    df_lv = df_lv[df_lv.astype(str).apply(lambda x: x.str.contains(kw_lb, case=False, na=False)).any(axis=1)]
                st.dataframe(df_lv, use_container_width=True, hide_index=True, height=440)

    # ------------------------------------------------------------------
    # [식품안전팀] 원자재 표시사항 DB (원재료·제조원·알레르기 검증)
    # ------------------------------------------------------------------
    elif view == "label_issue":
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>🧬 원자재 표시사항 DB — 원재료·공급사 검증 및 신규 알레르기 현황</span></div>", unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("전체 원재료 마스터 수", f"{raw_master_cnt:,} 건")
        r2.metric("원자재 표시사항 등록 건수", f"{sub_raw_cnt:,} 건")
        r3.metric("검증 완료 건수", f"{verified_raw_cnt:,} 건")
        r4.metric("신규 알레르기 감지 건수", f"{allergy_raw_cnt:,} 건")

        if df_raw_sub.empty:
            st.info("현재 '원자재 표시사항 DB'의 제출 시트에 데이터가 비어 있거나 시트 연동 확인이 필요합니다.")
        else:
            raw_kw = st.text_input("🔍 원재료명 / 제조원 / 공급사(판매원) 검색")
            df_rv = df_raw_sub[df_raw_sub.astype(str).apply(lambda x: x.str.contains(raw_kw, case=False, na=False)).any(axis=1)] if raw_kw else df_raw_sub
            st.dataframe(df_rv, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # [식품안전팀] HACCP 강화 · 법적 RISK 관리 (3번 KPI & 8번 KPI 통합/개별 진입 모두 호환)
    # ------------------------------------------------------------------
    elif view in ("fs_haccp_risk", "kpi_8", "kpi_12"):
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>🛡️ 식품안전 및 HACCP 강화 · 법적 RISK 최소화 관리</span></div>", unsafe_allow_html=True)
        if view == "kpi_12":
            t_order = ["⚖️ 8. 식품안전 법적 RISK 최소화", "🛡️ 3. 식품안전 및 HACCP 강화"]
            k_order = ["kpi_12", "kpi_8"]
        else:
            t_order = ["🛡️ 3. 식품안전 및 HACCP 강화", "⚖️ 8. 식품안전 법적 RISK 최소화"]
            k_order = ["kpi_8", "kpi_12"]

        ft1, ft2 = st.tabs(t_order)
        with ft1:
            render_manual_kpi_editor_section(k_order[0], key_suffix="fs1")
        with ft2:
            render_manual_kpi_editor_section(k_order[1], key_suffix="fs2")

    # ------------------------------------------------------------------
    # [품질관리팀] 핵심불량 저감 · 부자재 폐기 관리 (4번 KPI & 5번 KPI 통합/개별 진입 모두 호환)
    # ------------------------------------------------------------------
    elif view in ("qc_defect_sub", "kpi_9", "kpi_10"):
        st.markdown("<div class='yonsei-header-bar'><span class='yonsei-title'>📦 핵심불량(클레임) 저감화 · 부자재 관리 고도화</span></div>", unsafe_allow_html=True)
        if view == "kpi_10":
            qt_order = ["📦 5. 부자재 관리 고도화 (폐기 Zero)", "🎯 4. 핵심불량(클레임) 발생 저감화"]
            qk_order = ["kpi_10", "kpi_9"]
        else:
            qt_order = ["🎯 4. 핵심불량(클레임) 발생 저감화", "📦 5. 부자재 관리 고도화 (폐기 Zero)"]
            qk_order = ["kpi_9", "kpi_10"]

        qt1, qt2 = st.tabs(qt_order)
        with qt1:
            render_manual_kpi_editor_section(qk_order[0], key_suffix="qc1")
        with qt2:
            render_manual_kpi_editor_section(qk_order[1], key_suffix="qc2")
# ============================ [PART 4 / 4 끝] ============================
