"""
Danawa product crawler.

다나와에서 상품 정보를 크롤링하는 모듈입니다.
CSV 데이터 명세서 기준으로 구현되었습니다.
"""
import logging
import time
import random
import json
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from dateutil.relativedelta import relativedelta

import requests
from bs4 import BeautifulSoup

# Selenium imports for JavaScript-rendered content
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================
# 데이터 클래스 정의
# ============================================================

@dataclass
class ProductInfo:
    """크롤링된 상품 기본 정보."""
    # 기본정보
    pcode: str                                    # 상품코드
    product_name: str                             # 상품명
    brand: str                                    # 브랜드
    registration_date: Optional[str] = None       # 등록월
    product_status: Optional[str] = None          # 상품상태
    image_url: Optional[str] = None               # 대표이미지URL
    additional_images: List[str] = field(default_factory=list)  # 추가이미지URL목록
    detail_page_images: List[str] = field(default_factory=list)  # 상세페이지이미지URL
    product_description_images: List[str] = field(default_factory=list)  # 제품설명이미지URL

    # 카테고리
    category_1: Optional[str] = None              # 대분류
    category_2: Optional[str] = None              # 중분류
    category_3: Optional[str] = None              # 소분류
    category_4: Optional[str] = None              # 세분류

    # 가격정보
    price: int = 0                                # 현재가
    min_price: int = 0                            # 최저가

    # 스펙정보
    spec: Dict[str, Any] = field(default_factory=dict)  # 스펙테이블
    spec_summary: List[str] = field(default_factory=list)  # 주요스펙요약

    # 리뷰통계
    mall_review_count: int = 0                    # 쇼핑몰리뷰수
    review_rating: Optional[float] = None         # 평균 별점


@dataclass
class MallInfo:
    """쇼핑몰 가격 정보."""
    mall_name: str                                # 판매처명 (tasks.py 호환)
    price: int                                    # 현재가
    product_url: Optional[str] = None             # 판매페이지URL (tasks.py 호환)
    logo_url: Optional[str] = None                # 판매처로고 (tasks.py 호환)
    # 별칭 (CSV 명세서 호환)
    seller_name: Optional[str] = None
    seller_url: Optional[str] = None
    seller_logo: Optional[str] = None


@dataclass
class PriceHistory:
    """월별 가격 변동 정보."""
    month_offset: int                             # 몇 개월 전 (1~24)
    price: Optional[int] = None                   # 해당 월 최저가
    date: Optional[str] = None                    # 날짜 문자열 (예: "24-04", "25-01")
    fulldate: Optional[str] = None                # 전체 날짜 (예: "25-12-23")


@dataclass
class ReviewInfo:
    """다나와 리뷰 정보."""
    shop_name: Optional[str] = None               # 리뷰 쇼핑몰명
    reviewer_name: Optional[str] = None           # 리뷰 작성자 (tasks.py 호환)
    rating: Optional[int] = None                  # 리뷰 평점 (1-5)
    review_date: Optional[str] = None             # 리뷰 작성일
    content: Optional[str] = None                 # 리뷰 내용
    review_images: List[str] = field(default_factory=list)  # 리뷰 이미지
    # 별칭 (CSV 명세서 호환)
    reviewer: Optional[str] = None


# ============================================================
# 다나와 크롤러
# ============================================================

class DanawaCrawler:
    """
    다나와 크롤러.

    CSV 데이터 명세서의 모든 필드를 크롤링합니다.

    사용 예시:
        crawler = DanawaCrawler()

        # 상품 정보 크롤링
        product = crawler.get_product_info("44762393")

        # 판매처 정보 크롤링
        mall_list = crawler.get_mall_prices("44762393")

        # 가격 변동 이력 크롤링
        price_history = crawler.get_price_history("44762393")

        # 리뷰 크롤링
        reviews = crawler.get_reviews("44762393")
    """

    BASE_URL = "https://prod.danawa.com"
    SEARCH_URL = "https://search.danawa.com"
    CHART_API_URL = "https://prod.danawa.com/info/ajax/getChartData.ajax.php"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.danawa.com/',
    }

    def __init__(self, delay_range: tuple = (1, 3)):
        """
        Args:
            delay_range: 요청 간 딜레이 범위 (초). 서버 부하 방지용.
        """
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.delay_range = delay_range

    def _delay(self):
        """요청 간 랜덤 딜레이."""
        time.sleep(random.uniform(*self.delay_range))

    def _get_page(self, url: str, params: dict = None) -> Optional[BeautifulSoup]:
        """페이지 HTML 가져오기."""
        try:
            self._delay()
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def _get_json(self, url: str, params: dict = None) -> Optional[dict]:
        """JSON API 호출."""
        try:
            self._delay()
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Failed to fetch JSON from {url}: {e}")
            return None

    # ============================================================
    # 상품 기본 정보 크롤링
    # ============================================================

    def get_product_info(self, pcode: str) -> Optional[ProductInfo]:
        """
        상품 상세 정보 크롤링.

        Args:
            pcode: 다나와 상품 코드 (예: "44762393")

        Returns:
            ProductInfo 또는 None
        """
        url = f"{self.BASE_URL}/info/?pcode={pcode}"
        soup = self._get_page(url)

        if not soup:
            return None

        try:
            # 상품명 - .prod_tit 안의 .title span에서 가져옴
            name_elem = soup.select_one('.prod_tit .title')
            if not name_elem:
                name_elem = soup.select_one('.prod_tit')
            product_name = name_elem.get_text(strip=True) if name_elem else "Unknown"

            # 브랜드
            brand = self._parse_brand(soup)

            # 등록월
            registration_date = self._parse_registration_date(soup)

            # 상품상태
            product_status = self._parse_product_status(soup)

            # 최저가
            min_price = self._parse_min_price(soup)

            # 현재가 (= 최저가)
            price = min_price

            # 카테고리
            categories = self._parse_categories(soup)

            # 스펙 정보
            spec, spec_summary = self._parse_spec(soup)

            # 이미지 URL들
            image_url = self._parse_main_image(soup)
            additional_images = self._parse_additional_images(soup)
            detail_page_images = self._parse_detail_page_images(soup, pcode)
            product_description_images = self._parse_product_description_images(soup)

            # 쇼핑몰 리뷰 수 및 별점
            mall_review_count = self._parse_mall_review_count(soup)
            review_rating = self._parse_review_rating(soup)

            return ProductInfo(
                pcode=pcode,
                product_name=product_name,
                brand=brand,
                registration_date=registration_date,
                product_status=product_status,
                image_url=image_url,
                additional_images=additional_images,
                detail_page_images=detail_page_images,
                product_description_images=product_description_images,
                category_1=categories.get('category_1'),
                category_2=categories.get('category_2'),
                category_3=categories.get('category_3'),
                category_4=categories.get('category_4'),
                price=price,
                min_price=min_price,
                spec=spec,
                spec_summary=spec_summary,
                mall_review_count=mall_review_count,
                review_rating=review_rating,
            )

        except Exception as e:
            logger.error(f"Failed to parse product {pcode}: {e}")
            return None

    def _parse_brand(self, soup: BeautifulSoup) -> str:
        """브랜드 파싱."""
        import re

        # 1. spec_list에서 찾기
        brand_elem = soup.select_one('.spec_list .makerName')
        if brand_elem:
            return brand_elem.get_text(strip=True)

        # 2. made_info에서 제조사 추출
        maker_elem = soup.select_one('.made_info')
        if maker_elem:
            text = maker_elem.get_text(strip=True)

            # "제조사:" 뒤의 값 추출 (예: "제조사:APPLE")
            match = re.search(r'제조사[:\s]*([^ㅣ\|]+)', text)
            if match:
                brand = match.group(1).strip()
                # 빈 값이 아니고 ":"만 있는 경우가 아니면 반환
                if brand and brand != ':':
                    return brand

            # 3. 제조사가 비어있으면 "이미지출처"에서 추출 (예: "이미지출처: LG전자")
            match = re.search(r'이미지출처[:\s]*([^ㅣ\|]+)', text)
            if match:
                brand = match.group(1).strip()
                if brand:
                    return brand

        # 4. 상품명에서 브랜드 추출 시도 (첫 단어)
        prod_name = soup.select_one('.prod_tit .title')
        if prod_name:
            name_text = prod_name.get_text(strip=True)
            # 알려진 브랜드 패턴 매칭
            known_brands = ['삼성전자', 'LG전자', 'APPLE', 'MSI', 'ASUS', 'AULA', 'ATK', '로지텍', '레노버', 'HP', 'DELL']
            for brand in known_brands:
                if brand in name_text:
                    return brand
            # 첫 단어 추출
            first_word = name_text.split()[0] if name_text else ''
            if first_word and len(first_word) <= 10:
                return first_word

        return ""

    def _parse_registration_date(self, soup: BeautifulSoup) -> Optional[str]:
        """등록월 파싱."""
        import re

        # 1. spec_list에서 찾기
        reg_elem = soup.select_one('.spec_list .regDate')
        if reg_elem:
            return reg_elem.get_text(strip=True)

        # 2. made_info에서 등록월 추출 (예: "등록월: 2025.09.ㅣ...")
        maker_elem = soup.select_one('.made_info')
        if maker_elem:
            text = maker_elem.get_text(strip=True)
            match = re.search(r'등록월[:\s]*([\d.]+)', text)
            if match:
                return match.group(1).strip()

        return None

    def _parse_product_status(self, soup: BeautifulSoup) -> Optional[str]:
        """상품상태 파싱."""
        status_elem = soup.select_one('.prod_status')
        if status_elem:
            return status_elem.get_text(strip=True)
        return "판매중"

    def _parse_min_price(self, soup: BeautifulSoup) -> int:
        """최저가 파싱."""
        import re
        from collections import Counter

        # 1. 기존 선택자 시도
        price_elem = soup.select_one('.lowest_price .lwst_prc .prc')
        if price_elem:
            price_text = price_elem.get_text(strip=True).replace(',', '').replace('원', '')
            if price_text.isdigit():
                return int(price_text)

        # 2. summary_left 영역에서 가격 추출 (메인 가격 영역)
        summary_left = soup.select_one('.summary_left')
        if summary_left:
            summary_text = summary_left.get_text()
            prices = re.findall(r'([\d,]+)\s*원', summary_text)

            if prices:
                # 가격들을 정수로 변환
                valid_prices = []
                for p in prices:
                    try:
                        price_val = int(p.replace(',', ''))
                        # 최소 1,000원 이상 (배송비 등 제외)
                        if price_val >= 1000:
                            valid_prices.append(price_val)
                    except ValueError:
                        continue

                if valid_prices:
                    # 가격대별 그룹핑하여 가장 많이 나온 가격대의 최저가 반환
                    # 이렇게 하면 배송비, 포인트 등을 제외하고 실제 상품 가격을 찾을 수 있음
                    price_ranges = {}
                    for p in valid_prices:
                        # 가격대 구간 (만원 단위)
                        range_key = p // 10000
                        if range_key not in price_ranges:
                            price_ranges[range_key] = []
                        price_ranges[range_key].append(p)

                    # 가장 많은 가격이 속한 구간 찾기
                    if price_ranges:
                        most_common_range = max(price_ranges.keys(), key=lambda k: len(price_ranges[k]))
                        # 해당 구간의 최저가 반환
                        return min(price_ranges[most_common_range])

        # 3. 페이지 전체에서 가격 패턴 추출 (fallback)
        page_text = str(soup)
        prices = re.findall(r'([\d,]+)원', page_text)

        if prices:
            valid_prices = []
            for p in prices:
                try:
                    price_val = int(p.replace(',', ''))
                    if price_val >= 1000:  # 최소 1,000원 이상
                        valid_prices.append(price_val)
                except ValueError:
                    continue

            if valid_prices:
                # 같은 로직 적용
                price_ranges = {}
                for p in valid_prices:
                    range_key = p // 10000
                    if range_key not in price_ranges:
                        price_ranges[range_key] = []
                    price_ranges[range_key].append(p)

                if price_ranges:
                    most_common_range = max(price_ranges.keys(), key=lambda k: len(price_ranges[k]))
                    return min(price_ranges[most_common_range])

        return 0

    def _parse_categories(self, soup: BeautifulSoup) -> Dict[str, Optional[str]]:
        """카테고리 파싱."""
        import re

        categories = {
            'category_1': None,
            'category_2': None,
            'category_3': None,
            'category_4': None,
        }

        # 1. location_category 시도
        breadcrumb = soup.select('.location_category a')
        if breadcrumb:
            for i, item in enumerate(breadcrumb[:4], 1):
                categories[f'category_{i}'] = item.get_text(strip=True)
            return categories

        # 2. JavaScript 변수에서 카테고리 추출
        # 다나와 페이지의 스크립트에 Category 정보가 포함됨
        page_html = str(soup)

        # Category 변수 패턴 찾기 (예: Category: "태블릿/휴대폰")
        cat_matches = re.findall(r"['\"]?Category['\"]?\s*[=:]\s*['\"]([^'\"]+)['\"]", page_html)

        if cat_matches:
            # 중복 제거하고 유효한 카테고리만 필터링
            seen = set()
            unique_cats = []
            for cat in cat_matches:
                # 무효한 값 필터링
                if cat and cat not in seen and not cat.startswith('review') and len(cat) < 50:
                    seen.add(cat)
                    unique_cats.append(cat)

            # 카테고리 할당 (최대 4개)
            for i, cat in enumerate(unique_cats[:4], 1):
                categories[f'category_{i}'] = cat

            if any(categories.values()):
                return categories

        # 3. 카테고리 링크에서 추출
        cat_links = soup.select('.cate_wrap a')
        if cat_links:
            idx = 1
            for item in cat_links:
                text = item.get_text(strip=True)
                # VS검색, 메인 네비게이션 항목 제외
                if text and not text.startswith('VS') and idx <= 4:
                    if '·' not in text and len(text) < 30:  # 메인 카테고리 구분
                        categories[f'category_{idx}'] = text
                        idx += 1
            if any(categories.values()):
                return categories

        # 4. og:description 메타 태그에서 카테고리 추출 시도
        og_desc = soup.select_one('meta[property="og:description"]')
        if og_desc:
            content = og_desc.get('content', '')
            if '>' in content:
                parts = content.split('>')
                for i, part in enumerate(parts[:4], 1):
                    categories[f'category_{i}'] = part.strip()

        return categories

    def _parse_spec(self, soup: BeautifulSoup) -> tuple:
        """스펙 정보 파싱."""
        import re

        spec = {}
        spec_summary = []

        try:
            # 1. 스펙 테이블 파싱 (기존 방식)
            spec_items = soup.select('.spec_tbl tr')
            for row in spec_items:
                th = row.select_one('th')
                td = row.select_one('td')
                if th and td:
                    key = th.get_text(strip=True)
                    value = td.get_text(strip=True)
                    spec[key] = value

            # 2. .spec_list에서 "/" 구분 문자열 파싱
            # 다나와 스펙 형식: "스마트폰(바형)/화면:15.9cm/120Hz/램:8GB/..."
            spec_list_elem = soup.select_one('.spec_list')
            if spec_list_elem:
                spec_text = spec_list_elem.get_text(strip=True)

                # "/"로 분리
                spec_items_text = spec_text.split('/')

                for item in spec_items_text:
                    item = item.strip()
                    if not item:
                        continue

                    # spec_summary에 추가 (요약용)
                    spec_summary.append(item)

                    # key:value 형식이면 spec dict에 추가
                    if ':' in item:
                        parts = item.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            if key and value:
                                spec[key] = value
                    else:
                        # key:value가 아닌 경우 (예: "5G", "120Hz")
                        # 특성 이름으로 저장
                        spec[item] = True

            # 3. 주요 스펙 요약 (li 태그가 있는 경우)
            if not spec_summary:
                summary_items = soup.select('.spec_list li')
                for item in summary_items[:10]:
                    text = item.get_text(strip=True)
                    if text:
                        spec_summary.append(text)

        except Exception as e:
            logger.warning(f"Failed to parse spec: {e}")

        return spec, spec_summary

    def _parse_main_image(self, soup: BeautifulSoup) -> Optional[str]:
        """대표 이미지 URL 파싱."""
        img_elem = soup.select_one('.photo_w img')
        if img_elem:
            src = img_elem.get('src') or img_elem.get('data-src')
            if src:
                return src if src.startswith('http') else f"https:{src}"
        return None

    def _parse_additional_images(self, soup: BeautifulSoup) -> List[str]:
        """추가 이미지 URL 파싱 (썸네일/갤러리 이미지)."""
        images = []
        # 다나와 페이지의 여러 가능한 썸네일 선택자
        selectors = [
            # 메인 썸네일 갤러리
            '.thumb_list li img',
            '.thumb_list img',
            '#thumbArea li img',
            '#thumbArea img',
            # 슬라이드 갤러리
            '.photo_slide li img',
            '.thumb_slide li img',
            '.photo_slide_in li img',
            # 추가 이미지 영역
            '.add_thumb_list img',
            '.add_photo img',
            # 상품 이미지 영역
            '.prod_thumb img',
            '.prod_photo_list img',
            '.photo_list li img',
            # 대표 이미지 외 추가 이미지
            '.photo_w .thumb img',
            '.photo_w .add_img img',
        ]
        for selector in selectors:
            img_items = soup.select(selector)
            for img in img_items[:15]:
                src = img.get('src') or img.get('data-src') or img.get('data-original')
                if src:
                    # URL 정규화
                    if src.startswith('//'):
                        url = f"https:{src}"
                    elif not src.startswith('http'):
                        url = f"https://img.danawa.com{src}"
                    else:
                        url = src
                    # 플레이스홀더나 아이콘 제외
                    if url not in images and 'icon' not in url.lower() and 'noimg' not in url.lower():
                        images.append(url)
            if images:
                break
        return images

    def _parse_detail_page_images(self, soup: BeautifulSoup, pcode: str) -> List[str]:
        """상세페이지 이미지 URL 파싱 (상품 상세 설명 이미지)."""
        images = []
        # 다나와 상세페이지 이미지 선택자
        selectors = [
            # 상세정보 탭 내 이미지
            '#detail_info img',
            '.detail_cont img',
            '.detail_info img',
            # 상품 상세 이미지 영역
            '.prod_detail img',
            '.detail_img img',
            '.prod_detail_info img',
            # 제조사 제공 상세 이미지
            '.maker_detail img',
            '.mfr_detail img',
            # 상품 설명 영역
            '.prod_explain img',
            '.explain_cont img',
            # iframe 로드 영역 (있는 경우)
            '.detail_area img',
            '.info_cont img',
        ]
        for selector in selectors:
            detail_imgs = soup.select(selector)
            for img in detail_imgs[:30]:
                src = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy')
                if src:
                    # URL 정규화
                    if src.startswith('//'):
                        url = f"https:{src}"
                    elif not src.startswith('http'):
                        url = f"https://img.danawa.com{src}"
                    else:
                        url = src
                    # 유효한 이미지 URL만 추가 (아이콘, 플레이스홀더 제외)
                    if url not in images and 'icon' not in url.lower() and 'noimg' not in url.lower() and 'blank' not in url.lower():
                        images.append(url)
        return images

    def _parse_product_description_images(self, soup: BeautifulSoup) -> List[str]:
        """제품설명 이미지 URL 파싱 (제조사 제공 제품 설명 이미지)."""
        images = []
        # 다나와 제품설명 이미지 선택자
        selectors = [
            # 제품 설명/소개 영역
            '.prod_desc img',
            '.prod_description img',
            '.prod_info_wrap img',
            '.prod_info img',
            # 제조사 정보 영역
            '.maker_info img',
            '.brand_info img',
            '.mfr_info img',
            # 상품 특징 영역
            '.prod_feature img',
            '.feature_info img',
            '.spec_info img',
            # 상품 요약 정보 이미지
            '.summary_info img',
            '.prod_summary img',
            # 메인 비주얼 이미지
            '.main_visual img',
            '.visual_area img',
        ]
        for selector in selectors:
            desc_imgs = soup.select(selector)
            for img in desc_imgs[:20]:
                src = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy')
                if src:
                    # URL 정규화
                    if src.startswith('//'):
                        url = f"https:{src}"
                    elif not src.startswith('http'):
                        url = f"https://img.danawa.com{src}"
                    else:
                        url = src
                    # 유효한 이미지만 추가
                    if url not in images and 'icon' not in url.lower() and 'noimg' not in url.lower() and 'blank' not in url.lower():
                        images.append(url)
        return images

    def get_product_images_with_selenium(self, pcode: str) -> Dict[str, Any]:
        """
        Selenium을 사용하여 상품 이미지 크롤링.

        Args:
            pcode: 다나와 상품 코드

        Returns:
            이미지 딕셔너리 {
                'main_image': str,
                'additional_images': List[str],
                'detail_images': List[str],
                'description_images': List[str],
            }
        """
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium not available")
            return {}

        import os
        result = {
            'main_image': None,
            'additional_images': [],
            'detail_images': [],
            'description_images': [],
        }
        driver = None

        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

            chrome_bin = os.environ.get('CHROME_BIN')
            chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')

            if chrome_bin and os.path.exists(chrome_bin):
                options.binary_location = chrome_bin

            if chromedriver_path and os.path.exists(chromedriver_path):
                service = Service(chromedriver_path)
            else:
                service = Service(ChromeDriverManager().install())

            driver = webdriver.Chrome(service=service, options=options)

            url = f'{self.BASE_URL}/info/?pcode={pcode}'
            driver.get(url)
            time.sleep(3)

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # 대표 이미지
            main_img = soup.select_one('.photo_w img, #imgView img')
            if main_img:
                src = main_img.get('src') or main_img.get('data-src')
                if src:
                    result['main_image'] = src if src.startswith('http') else f"https:{src}"

            # 추가 이미지 (썸네일)
            result['additional_images'] = self._parse_additional_images(soup)

            # 상세 이미지
            result['detail_images'] = self._parse_detail_page_images(soup, pcode)

            # 제품설명 이미지
            result['description_images'] = self._parse_product_description_images(soup)

            logger.info(f"Crawled images for {pcode}: main={bool(result['main_image'])}, "
                       f"additional={len(result['additional_images'])}, "
                       f"detail={len(result['detail_images'])}")

        except Exception as e:
            logger.error(f"Failed to crawl images with Selenium for {pcode}: {e}")

        finally:
            if driver:
                driver.quit()

        return result

    def _parse_mall_review_count(self, soup: BeautifulSoup) -> int:
        """쇼핑몰 리뷰 수 파싱 (JSON-LD에서 추출)."""
        review_count, _ = self._parse_review_data(soup)
        return review_count

    def _parse_review_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """리뷰 평균 별점 파싱 (JSON-LD에서 추출)."""
        _, rating = self._parse_review_data(soup)
        return rating

    def _parse_review_data(self, soup: BeautifulSoup) -> tuple:
        """JSON-LD에서 리뷰 수와 별점 추출."""
        import re

        review_count = 0
        review_rating = None

        # JSON-LD 스크립트 태그 찾기
        script_tags = soup.select('script[type="application/ld+json"]')
        for script in script_tags:
            try:
                data = json.loads(script.string)
                # AggregateRating 찾기
                if isinstance(data, dict):
                    if data.get('@type') == 'AggregateRating':
                        review_count = int(data.get('reviewCount', 0))
                        rating_val = data.get('ratingValue')
                        if rating_val:
                            review_rating = float(rating_val)
                    elif 'aggregateRating' in data:
                        agg = data['aggregateRating']
                        review_count = int(agg.get('reviewCount', 0))
                        rating_val = agg.get('ratingValue')
                        if rating_val:
                            review_rating = float(rating_val)
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

        # JSON-LD에서 못 찾으면 HTML에서 정규식으로 추출
        if review_count == 0:
            html_text = str(soup)
            # "reviewCount": "7642" 패턴
            match = re.search(r'"reviewCount"[:\s]*"?(\d+)"?', html_text)
            if match:
                review_count = int(match.group(1))

            # "ratingValue": "4.7" 패턴
            match = re.search(r'"ratingValue"[:\s]*"?([\d.]+)"?', html_text)
            if match:
                review_rating = float(match.group(1))

        return review_count, review_rating

    # ============================================================
    # 판매처 정보 크롤링
    # ============================================================

    def get_mall_prices(self, pcode: str) -> List[MallInfo]:
        """
        쇼핑몰별 가격 정보 크롤링 (requests 기반).
        페이지 구조 변경으로 동작하지 않을 수 있음.
        get_mall_prices_with_selenium() 사용 권장.

        Args:
            pcode: 다나와 상품 코드

        Returns:
            MallInfo 리스트
        """
        url = f"{self.BASE_URL}/info/?pcode={pcode}"
        soup = self._get_page(url)

        if not soup:
            return []

        mall_list = []

        try:
            # 새 페이지 구조: #blog_content .diff_item
            mall_items = soup.select('#blog_content .diff_item')

            for item in mall_items:
                # 판매처명 및 로고 (여러 선택자 시도)
                seller_name = None
                seller_logo = None

                # 로고 이미지에서 판매처명과 로고 URL 추출
                logo_selectors = [
                    '.d_mall img',
                    '.mall_logo img',
                    '.logo_area img',
                    '.shop_logo img',
                    '.seller_logo img',
                    '.mall img',
                ]
                for selector in logo_selectors:
                    mall_img = item.select_one(selector)
                    if mall_img:
                        seller_name = mall_img.get('alt') or mall_img.get('title')
                        src = mall_img.get('src') or mall_img.get('data-src')
                        if src:
                            if src.startswith('//'):
                                seller_logo = f"https:{src}"
                            elif not src.startswith('http'):
                                seller_logo = f"https://img.danawa.com{src}"
                            else:
                                seller_logo = src
                        break

                # 판매처명이 없으면 텍스트에서 추출
                if not seller_name:
                    # 우선 d_mall 내의 링크 텍스트에서 추출 시도
                    d_mall_link = item.select_one('.d_mall a.link, .d_mall a.priceCompareBuyLink')
                    if d_mall_link:
                        link_text = d_mall_link.get_text(strip=True)
                        if link_text:
                            seller_name = link_text

                    # 아직 없으면 다른 선택자들 시도
                    if not seller_name:
                        name_selectors = ['.d_mall', '.mall_name', '.seller_name', '.shop_name']
                        for selector in name_selectors:
                            name_elem = item.select_one(selector)
                            if name_elem:
                                text = name_elem.get_text(strip=True)
                                # "신고" 버튼 텍스트 제거
                                if text.endswith('신고'):
                                    text = text[:-2].strip()
                                text = re.sub(r'신고$', '', text).strip()
                                if text:
                                    seller_name = text
                                    break

                # 가격 - 여러 선택자 시도
                price = 0
                price_selectors = [
                    '.prc_line .price em.prc_c',
                    '.prc_line em.prc_c',
                    '.price_sect .price',
                    '.price em',
                    '.prc_t',
                ]
                for selector in price_selectors:
                    price_elem = item.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True).replace(',', '').replace('원', '')
                        if price_text.isdigit():
                            price = int(price_text)
                            break

                # 판매페이지 URL
                link_selectors = ['a.link', 'a.priceCompareBuyLink', 'a.buy_link', 'a.go_mall']
                seller_url = None
                for selector in link_selectors:
                    link_elem = item.select_one(selector)
                    if link_elem:
                        seller_url = link_elem.get('href')
                        break

                if seller_name and price > 0:
                    mall_list.append(MallInfo(
                        mall_name=seller_name,
                        price=price,
                        product_url=seller_url,
                        logo_url=seller_logo,
                        seller_name=seller_name,
                        seller_url=seller_url,
                        seller_logo=seller_logo,
                    ))

        except Exception as e:
            logger.error(f"Failed to parse mall prices for {pcode}: {e}")

        return mall_list

    def get_mall_prices_with_selenium(self, pcode: str, limit: int = 20) -> List[MallInfo]:
        """
        Selenium을 사용하여 쇼핑몰별 가격 정보 크롤링.

        Args:
            pcode: 다나와 상품 코드
            limit: 최대 판매처 수

        Returns:
            MallInfo 리스트
        """
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium not available")
            return []

        import os
        mall_list = []
        driver = None

        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

            chrome_bin = os.environ.get('CHROME_BIN')
            chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')

            if chrome_bin and os.path.exists(chrome_bin):
                options.binary_location = chrome_bin

            if chromedriver_path and os.path.exists(chromedriver_path):
                service = Service(chromedriver_path)
            else:
                service = Service(ChromeDriverManager().install())

            driver = webdriver.Chrome(service=service, options=options)

            url = f'{self.BASE_URL}/info/?pcode={pcode}'
            driver.get(url)
            time.sleep(3)

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # 쇼핑몰 정보 파싱
            mall_items = soup.select('#blog_content .diff_item')[:limit]

            for item in mall_items:
                try:
                    # 판매처명 및 로고 (여러 선택자 시도)
                    seller_name = None
                    seller_logo = None

                    # 로고 이미지에서 판매처명과 로고 URL 추출
                    logo_selectors = [
                        '.d_mall img',
                        '.mall_logo img',
                        '.logo_area img',
                        '.shop_logo img',
                        '.seller_logo img',
                        '.mall img',
                    ]
                    for selector in logo_selectors:
                        mall_img = item.select_one(selector)
                        if mall_img:
                            seller_name = mall_img.get('alt') or mall_img.get('title')
                            src = mall_img.get('src') or mall_img.get('data-src')
                            if src:
                                if src.startswith('//'):
                                    seller_logo = f"https:{src}"
                                elif not src.startswith('http'):
                                    seller_logo = f"https://img.danawa.com{src}"
                                else:
                                    seller_logo = src
                            break

                    # 판매처명이 없으면 텍스트에서 추출
                    if not seller_name:
                        # 우선 d_mall 내의 링크 텍스트에서 추출 시도
                        d_mall_link = item.select_one('.d_mall a.link, .d_mall a.priceCompareBuyLink')
                        if d_mall_link:
                            # 링크 내부의 이미지가 아닌 텍스트 노드 확인
                            link_text = d_mall_link.get_text(strip=True)
                            if link_text:
                                seller_name = link_text

                        # 아직 없으면 다른 선택자들 시도
                        if not seller_name:
                            name_selectors = ['.d_mall', '.mall_name', '.seller_name', '.shop_name']
                            for selector in name_selectors:
                                name_elem = item.select_one(selector)
                                if name_elem:
                                    # "신고" 버튼 텍스트 제거
                                    text = name_elem.get_text(strip=True)
                                    # "신고"로 끝나면 제거
                                    if text.endswith('신고'):
                                        text = text[:-2].strip()
                                    # "네이버페이" 뒤의 "신고" 패턴 제거
                                    import re
                                    text = re.sub(r'신고$', '', text).strip()
                                    if text:
                                        seller_name = text
                                        break

                    # 가격 - 여러 선택자 시도
                    price = 0
                    price_selectors = [
                        '.prc_line .price em.prc_c',
                        '.prc_line em.prc_c',
                        '.price_sect .price',
                        '.price em',
                        '.prc_t',
                    ]
                    for selector in price_selectors:
                        price_elem = item.select_one(selector)
                        if price_elem:
                            price_text = price_elem.get_text(strip=True).replace(',', '').replace('원', '')
                            if price_text.isdigit():
                                price = int(price_text)
                                break

                    # 판매페이지 URL
                    link_selectors = ['a.link', 'a.priceCompareBuyLink', 'a.buy_link', 'a.go_mall']
                    seller_url = None
                    for selector in link_selectors:
                        link_elem = item.select_one(selector)
                        if link_elem:
                            seller_url = link_elem.get('href')
                            break

                    if seller_name and price > 0:
                        mall_list.append(MallInfo(
                            mall_name=seller_name,
                            price=price,
                            product_url=seller_url,
                            logo_url=seller_logo,
                            seller_name=seller_name,
                            seller_url=seller_url,
                            seller_logo=seller_logo,
                        ))
                except Exception as e:
                    logger.warning(f"Failed to parse mall item: {e}")
                    continue

            logger.info(f"Crawled {len(mall_list)} mall prices for product {pcode}")

        except Exception as e:
            logger.error(f"Failed to crawl mall prices with Selenium for {pcode}: {e}")

        finally:
            if driver:
                driver.quit()

        return mall_list

    # ============================================================
    # 가격 변동 이력 크롤링
    # ============================================================

    PRICE_HISTORY_API_URL = "https://prod.danawa.com/info/ajax/getProductPriceList.ajax.php"

    def get_price_history(self, pcode: str, months: int = 24) -> List[PriceHistory]:
        """
        월별 가격 변동 이력 크롤링.

        다나와 가격 그래프 API를 사용하여 최대 24개월간의 월별 최저가를 조회합니다.

        Args:
            pcode: 다나와 상품 코드
            months: 조회할 개월 수 (기본 24개월, 지원: 1, 3, 6, 12, 24)

        Returns:
            PriceHistory 리스트 (최신순)
        """
        # 가격 이력 API 호출
        params = {
            'productCode': pcode,
        }

        # API 요청 헤더 설정 (Ajax 요청임을 명시)
        ajax_headers = self.HEADERS.copy()
        ajax_headers.update({
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.BASE_URL}/info/?pcode={pcode}',
        })

        history = []

        try:
            self._delay()
            response = self.session.get(
                self.PRICE_HISTORY_API_URL,
                params=params,
                headers=ajax_headers,
                timeout=15
            )
            response.raise_for_status()
            data = response.json()

            # 요청한 개월 수에 해당하는 키 선택 (1, 3, 6, 12, 24 중)
            period_key = str(months) if str(months) in data else '24'
            period_data = data.get(period_key, {})

            result_list = period_data.get('result', [])

            # 결과를 PriceHistory 객체로 변환
            for i, item in enumerate(result_list):
                date_str = item.get('date', '')  # 예: "24-04" 또는 "01-06"
                fulldate_str = item.get('Fulldate', '')  # 예: "25-12-23"
                min_price = item.get('minPrice')

                history.append(PriceHistory(
                    month_offset=len(result_list) - i,  # 오래된 데이터가 먼저 오므로 역순 인덱스
                    price=min_price,
                    date=date_str,
                    fulldate=fulldate_str,
                ))

            logger.info(f"Fetched {len(history)} price history records for {pcode}")

        except requests.RequestException as e:
            logger.error(f"Failed to fetch price history for {pcode}: {e}")
            # API 실패 시 빈 이력 반환
            for i in range(1, months + 1):
                history.append(PriceHistory(month_offset=i, price=None))
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse price history response for {pcode}: {e}")
            for i in range(1, months + 1):
                history.append(PriceHistory(month_offset=i, price=None))

        return history

    def get_price_history_detailed(self, pcode: str) -> Dict[str, Any]:
        """
        상세 가격 이력 조회 (모든 기간 데이터 포함).

        Args:
            pcode: 다나와 상품 코드

        Returns:
            {
                '1': {'count': N, 'result': [...], 'minPrice': X, 'maxPrice': Y},
                '3': {...},
                '6': {...},
                '12': {...},
                '24': {...}
            }
        """
        params = {'productCode': pcode}

        ajax_headers = self.HEADERS.copy()
        ajax_headers.update({
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.BASE_URL}/info/?pcode={pcode}',
        })

        try:
            self._delay()
            response = self.session.get(
                self.PRICE_HISTORY_API_URL,
                params=params,
                headers=ajax_headers,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch detailed price history for {pcode}: {e}")
            return {}

    # ============================================================
    # 리뷰 크롤링
    # ============================================================

    def get_reviews(self, pcode: str, limit: int = 20) -> List[ReviewInfo]:
        """
        다나와 리뷰 크롤링.

        Args:
            pcode: 다나와 상품 코드
            limit: 최대 리뷰 수

        Returns:
            ReviewInfo 리스트
        """
        url = f"{self.BASE_URL}/info/?pcode={pcode}"
        soup = self._get_page(url)

        if not soup:
            return []

        reviews = []

        try:
            review_items = soup.select('.danawa_review_list .review_item')[:limit]

            for item in review_items:
                # 쇼핑몰명
                shop_elem = item.select_one('.shop_name')
                shop_name = shop_elem.get_text(strip=True) if shop_elem else None

                # 작성자
                reviewer_elem = item.select_one('.reviewer')
                reviewer = reviewer_elem.get_text(strip=True) if reviewer_elem else None

                # 평점
                rating_elem = item.select_one('.star_score')
                rating = None
                if rating_elem:
                    # 별점 파싱 (예: "4점" -> 4)
                    rating_text = rating_elem.get_text(strip=True).replace('점', '')
                    rating = int(rating_text) if rating_text.isdigit() else None

                # 작성일
                date_elem = item.select_one('.review_date')
                review_date = date_elem.get_text(strip=True) if date_elem else None

                # 내용
                content_elem = item.select_one('.review_content')
                content = content_elem.get_text(strip=True) if content_elem else None

                # 이미지
                review_images = []
                img_items = item.select('.review_img img')
                for img in img_items:
                    src = img.get('src') or img.get('data-src')
                    if src:
                        url = src if src.startswith('http') else f"https:{src}"
                        review_images.append(url)

                reviews.append(ReviewInfo(
                    shop_name=shop_name,
                    reviewer_name=reviewer,
                    reviewer=reviewer,  # 별칭
                    rating=rating,
                    review_date=review_date,
                    content=content,
                    review_images=review_images,
                ))

        except Exception as e:
            logger.error(f"Failed to parse reviews for {pcode}: {e}")

        return reviews

    def get_reviews_with_selenium(self, pcode: str, limit: int = 50) -> List[ReviewInfo]:
        """
        Selenium을 사용하여 다나와 개별 리뷰 크롤링.

        다나와 리뷰는 JavaScript로 동적 로드되므로 Selenium이 필요합니다.

        Args:
            pcode: 다나와 상품 코드
            limit: 최대 리뷰 수

        Returns:
            ReviewInfo 리스트
        """
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium not available. Install with: pip install selenium webdriver-manager")
            return []

        import os
        reviews = []
        driver = None

        try:
            # Chrome 옵션 설정 (Headless 모드)
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            # Docker 환경에서는 시스템 Chromium 사용
            chrome_bin = os.environ.get('CHROME_BIN')
            chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')

            if chrome_bin and os.path.exists(chrome_bin):
                options.binary_location = chrome_bin

            if chromedriver_path and os.path.exists(chromedriver_path):
                service = Service(chromedriver_path)
            else:
                # 로컬 환경에서는 webdriver-manager 사용
                service = Service(ChromeDriverManager().install())

            driver = webdriver.Chrome(service=service, options=options)

            # 상품 페이지 로드
            url = f'{self.BASE_URL}/info/?pcode={pcode}'
            driver.get(url)
            time.sleep(3)

            # 쇼핑몰 리뷰 탭 클릭
            try:
                review_tab = driver.find_element(
                    By.ID, 'danawa-prodBlog-productOpinion-button-tab-companyReview'
                )
                driver.execute_script('arguments[0].click();', review_tab)
                time.sleep(3)
            except Exception as e:
                logger.warning(f"Could not click review tab: {e}")
                # 탭이 없을 경우 기본 페이지에서 리뷰 찾기

            # 페이지 소스 파싱
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # 리뷰 아이템 파싱 (.rvw_list > li)
            review_items = soup.select('.rvw_list > li')[:limit]

            for item in review_items:
                try:
                    # 평점 (width % / 20 = 5점 만점 평점)
                    rating = None
                    star_mask = item.select_one('.star_mask')
                    if star_mask:
                        style = star_mask.get('style', '')
                        width_match = re.search(r'width:\s*(\d+)%', style)
                        if width_match:
                            rating = int(width_match.group(1)) // 20

                    # 쇼핑몰명
                    mall = item.select_one('.mall img')
                    shop_name = mall.get('alt') if mall else None

                    # 리뷰 날짜
                    date_elem = item.select_one('.date')
                    review_date = date_elem.get_text(strip=True) if date_elem else None

                    # 작성자
                    name_elem = item.select_one('.name')
                    reviewer_name = name_elem.get_text(strip=True) if name_elem else None

                    # 제목
                    title_elem = item.select_one('.tit')
                    title = title_elem.get_text(strip=True) if title_elem else ''

                    # 내용
                    content_elem = item.select_one('.atc')
                    content = content_elem.get_text(strip=True) if content_elem else ''

                    # 제목과 내용 결합
                    full_content = f"{title}\n\n{content}" if title and content else (title or content)

                    # 이미지 목록
                    review_images = []
                    images = item.select('.pto_thumb img, .pto_list img')
                    for img in images:
                        src = img.get('src')
                        if src:
                            # URL 정규화
                            if src.startswith('//'):
                                src = f'https:{src}'
                            elif not src.startswith('http'):
                                src = f'https://img.danawa.com{src}'
                            review_images.append(src)

                    reviews.append(ReviewInfo(
                        shop_name=shop_name,
                        reviewer_name=reviewer_name,
                        reviewer=reviewer_name,
                        rating=rating,
                        review_date=review_date,
                        content=full_content,
                        review_images=review_images,
                    ))

                except Exception as e:
                    logger.warning(f"Failed to parse review item: {e}")
                    continue

            logger.info(f"Crawled {len(reviews)} reviews for product {pcode} using Selenium")

        except Exception as e:
            logger.error(f"Failed to crawl reviews with Selenium for {pcode}: {e}")

        finally:
            if driver:
                driver.quit()

        return reviews

    # ============================================================
    # 검색 기능
    # ============================================================

    def search_products(
        self,
        keyword: str,
        category_code: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        상품 검색.

        Args:
            keyword: 검색 키워드
            category_code: 카테고리 코드 (선택)
            limit: 최대 결과 수

        Returns:
            검색 결과 리스트 (pcode, product_name, price)
        """
        params = {
            'query': keyword,
            'originalQuery': keyword,
            'volumeType': 'vmvs',
            'page': 1,
            'limit': limit,
        }

        if category_code:
            params['categoryCode'] = category_code

        url = f"{self.SEARCH_URL}/dsearch.php"
        soup = self._get_page(url, params)

        if not soup:
            return []

        results = []

        try:
            product_items = soup.select('.product_list .prod_item')[:limit]

            for item in product_items:
                # pcode는 data-pcode 또는 id에서 추출 (productItem12345678 형식)
                pcode = item.get('data-pcode', '')
                if not pcode:
                    item_id = item.get('id', '')
                    if item_id.startswith('productItem'):
                        pcode = item_id.replace('productItem', '')

                # 상품명
                name_elem = item.select_one('.prod_name a') or item.select_one('.prod_name')
                product_name = name_elem.get_text(strip=True) if name_elem else ""

                # 가격
                price_elem = item.select_one('.price_sect .price') or item.select_one('.price em')
                price = 0
                if price_elem:
                    import re
                    price_text = re.sub(r'[^\d]', '', price_elem.get_text(strip=True))
                    price = int(price_text) if price_text.isdigit() else 0

                if pcode:
                    results.append({
                        'danawa_product_id': pcode,
                        'pcode': pcode,
                        'name': product_name,
                        'product_name': product_name,
                        'price': price,
                    })

        except Exception as e:
            logger.error(f"Failed to search products for '{keyword}': {e}")

        return results

    # ============================================================
    # 전체 상품 데이터 크롤링 (통합)
    # ============================================================

    def crawl_full_product_data(
        self, pcode: str, use_selenium_reviews: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        상품의 모든 데이터를 한 번에 크롤링.

        Args:
            pcode: 다나와 상품 코드
            use_selenium_reviews: True면 Selenium으로 개별 리뷰 크롤링

        Returns:
            전체 상품 데이터 딕셔너리
        """
        logger.info(f"Starting full crawl for product {pcode}")

        # 1. 기본 정보
        product_info = self.get_product_info(pcode)
        if not product_info:
            return None

        # 2. 판매처 정보
        mall_list = self.get_mall_prices(pcode)

        # 3. 가격 변동 이력
        price_history = self.get_price_history(pcode)

        # 4. 리뷰
        if use_selenium_reviews and SELENIUM_AVAILABLE:
            reviews = self.get_reviews_with_selenium(pcode)
        else:
            reviews = self.get_reviews(pcode)

        return {
            'product': product_info,
            'product_info': product_info,  # 호환성을 위해 유지
            'mall_prices': mall_list,
            'mall_list': mall_list,  # 호환성을 위해 유지
            'price_history': price_history,
            'reviews': reviews,
        }

    def close(self):
        """세션 종료."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.close()
