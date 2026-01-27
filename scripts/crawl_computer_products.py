#!/usr/bin/env python
"""
컴퓨터/노트북/조립PC 카테고리 상품 병렬 크롤링 스크립트

다나와의 컴퓨터/노트북/조립PC 카테고리 하위 상품만 크롤링합니다:
- 노트북/데스크탑: 노트북, 게이밍 노트북, 브랜드PC, 조립PC, 게이밍PC
- 모니터/복합기: 모니터, 게이밍 모니터
- PC부품: CPU, 그래픽카드, SSD, RAM, 메인보드, 파워, 케이스, 쿨러
"""
import os
import sys
import re
import django
import requests
from bs4 import BeautifulSoup
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

import logging
logging.disable(logging.DEBUG)

from modules.products.models import ProductModel
from modules.products.tasks import crawl_product


# 컴퓨터/노트북/조립PC 하위 카테고리 검색어 목록
COMPUTER_CATEGORIES = {
    '노트북/데스크탑': [
        '노트북',
        '게이밍노트북',
        '울트라북',
        '브랜드PC',
        '조립PC',
        '게이밍PC',
        '미니PC',
    ],
    '노트북 브랜드': [
        '삼성 노트북',
        'LG 그램',
        'ASUS 노트북',
        'MSI 노트북',
        '레노버 노트북',
        'HP 노트북',
        'Dell 노트북',
        '에이서 노트북',
        '한성컴퓨터 노트북',
        '기가바이트 노트북',
        '레이저 노트북',
        '맥북',
        '맥북프로',
        '맥북에어',
        '갤럭시북',
        '씽크패드',
        'ROG 노트북',
        'OMEN 노트북',
    ],
    '모니터/복합기': [
        '모니터',
        '게이밍모니터',
        '커브드모니터',
        '4K모니터',
        '27인치모니터',
        '32인치모니터',
        '24인치모니터',
        'QHD모니터',
        'IPS모니터',
        '144Hz모니터',
        '240Hz모니터',
        '삼성모니터',
        'LG모니터',
        'ASUS모니터',
        'Dell모니터',
        '벤큐모니터',
    ],
    'PC부품': [
        'CPU',
        '인텔CPU',
        'AMD CPU',
        '그래픽카드',
        'RTX그래픽카드',
        'RTX4090',
        'RTX4080',
        'RTX4070',
        'RTX4060',
        'RTX5090',
        'RTX5080',
        'RTX5070',
        'RX7900',
        'RX7800',
        'SSD',
        'NVMe SSD',
        'SATA SSD',
        '외장SSD',
        'HDD',
        '외장하드',
        'RAM',
        'DDR5',
        'DDR4',
        '메인보드',
        '인텔메인보드',
        'AMD메인보드',
        '파워서플라이',
        '시소닉파워',
        'PC케이스',
        '미들타워케이스',
        '풀타워케이스',
        'CPU쿨러',
        '수냉쿨러',
        '공랭쿨러',
        '타워쿨러',
    ],
    'PC부품 브랜드': [
        'ASUS그래픽카드',
        'MSI그래픽카드',
        '기가바이트그래픽카드',
        '조텍그래픽카드',
        'EVGA그래픽카드',
        '삼성SSD',
        'SK하이닉스SSD',
        'WD SSD',
        '씨게이트HDD',
        'CORSAIR',
        'G.SKILL',
        'NZXT',
        '리안리케이스',
    ],
    '주변기기': [
        '기계식키보드',
        '게이밍키보드',
        '무선키보드',
        '게이밍마우스',
        '무선마우스',
        '로지텍마우스',
        '게이밍헤드셋',
        '무선헤드셋',
        '웹캠',
        'PC스피커',
        '마우스패드',
        '모니터암',
        '노트북거치대',
        '노트북쿨러',
    ],
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# 스레드 안전한 카운터
print_lock = Lock()
success_count = 0
fail_count = 0


def search_products(keyword: str, limit: int = 100) -> list:
    """다나와 검색으로 상품 코드 목록 추출"""
    url = f"https://search.danawa.com/dsearch.php?query={keyword}&limit={limit}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'lxml')

        products = soup.select('.product_list .prod_item')

        result = []
        for item in products:
            # pcode 추출
            pcode = None
            item_id = item.get('id', '')
            if item_id.startswith('productItem'):
                pcode = item_id.replace('productItem', '')

            if not pcode:
                link = item.select_one('a[href*="pcode"]')
                if link:
                    href = link.get('href', '')
                    pcode_match = re.search(r'pcode=(\d+)', href)
                    if pcode_match:
                        pcode = pcode_match.group(1)

            if pcode and pcode.isdigit():
                # 상품명 추출
                name_elem = item.select_one('.prod_name a') or item.select_one('.prod_name')
                name = name_elem.get_text(strip=True) if name_elem else 'Unknown'

                result.append({
                    'pcode': pcode,
                    'name': name[:50],
                })

        return result

    except Exception as e:
        print(f"검색 오류 ({keyword}): {e}")
        return []


def crawl_single_product(args):
    """단일 상품 크롤링 (병렬 처리용)"""
    global success_count, fail_count

    idx, total, pcode, name = args

    try:
        # 서버 부하 방지를 위한 랜덤 딜레이
        time.sleep(random.uniform(0.1, 0.3))

        result = crawl_product(pcode)

        with print_lock:
            if result.get('success'):
                action = result.get('action', 'saved')
                history_count = result.get('history_count', 0)
                success_count += 1
                print(f"[{idx}/{total}] ✓ [{pcode}] {name[:30]} - {action} (가격이력: {history_count}개)")
                return True
            else:
                error = result.get('error', 'Unknown error')
                fail_count += 1
                print(f"[{idx}/{total}] ✗ [{pcode}] {name[:30]} - 실패: {error[:30]}")
                return False

    except Exception as e:
        with print_lock:
            fail_count += 1
            print(f"[{idx}/{total}] ✗ [{pcode}] {name[:30]} - 오류: {str(e)[:30]}")
        return False


def main():
    global success_count, fail_count

    parser = argparse.ArgumentParser(description='컴퓨터 상품 병렬 크롤링')
    parser.add_argument('--workers', type=int, default=8, help='병렬 워커 수 (기본: 8)')
    parser.add_argument('--limit', type=int, default=100, help='카테고리당 검색 제한 (기본: 100)')
    parser.add_argument('--max-products', type=int, default=2000, help='최대 크롤링 상품 수 (기본: 2000)')
    args = parser.parse_args()

    print("=" * 70)
    print(f"컴퓨터/노트북/조립PC 카테고리 상품 병렬 크롤링")
    print(f"워커 수: {args.workers} | 카테고리당 검색: {args.limit}개 | 최대: {args.max_products}개")
    print("=" * 70)

    # 기존 상품 확인
    existing_pcodes = set(
        ProductModel.objects.filter(deleted_at__isnull=True)
        .values_list('danawa_product_id', flat=True)
    )
    print(f"\n기존 상품 수: {len(existing_pcodes)}개")

    # 크롤링할 상품 코드 수집
    all_products = []
    seen_pcodes = set()

    for category_name, keywords in COMPUTER_CATEGORIES.items():
        print(f"\n[{category_name}]")

        for keyword in keywords:
            time.sleep(random.uniform(0.3, 0.5))  # 서버 부하 방지

            products = search_products(keyword, limit=args.limit)
            new_products = [
                p for p in products
                if p['pcode'] not in existing_pcodes and p['pcode'] not in seen_pcodes
            ]

            print(f"  {keyword}: {len(products)}개 검색, {len(new_products)}개 신규")

            for p in new_products:
                seen_pcodes.add(p['pcode'])
                all_products.append(p)

            # 최대 상품 수 도달 시 중단
            if len(all_products) >= args.max_products:
                break

        if len(all_products) >= args.max_products:
            break

    # 최대 상품 수로 제한
    all_products = all_products[:args.max_products]

    print("\n" + "=" * 70)
    print(f"크롤링 대상: {len(all_products)}개 신규 상품")
    print(f"예상 소요 시간: 약 {len(all_products) * 9 // args.workers // 60}분 (병렬 {args.workers}개)")
    print("=" * 70)

    if not all_products:
        print("크롤링할 신규 상품이 없습니다.")
        return

    # 병렬 크롤링 실행
    start_time = time.time()
    total = len(all_products)

    # 크롤링 작업 생성
    tasks = [
        (i, total, p['pcode'], p['name'])
        for i, p in enumerate(all_products, 1)
    ]

    print(f"\n병렬 크롤링 시작 (워커 {args.workers}개)...\n")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(crawl_single_product, task) for task in tasks]

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"작업 오류: {e}")

    # 결과 요약
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 70)
    print("크롤링 완료!")
    print("=" * 70)
    print(f"  성공: {success_count}개")
    print(f"  실패: {fail_count}개")
    print(f"  소요 시간: {elapsed_time / 60:.1f}분 ({elapsed_time:.0f}초)")
    print(f"  평균 속도: {total / elapsed_time:.1f}개/초")

    # 최종 상품 수
    final_count = ProductModel.objects.filter(deleted_at__isnull=True).count()
    print(f"\n총 상품 수: {final_count}개")


if __name__ == '__main__':
    main()
