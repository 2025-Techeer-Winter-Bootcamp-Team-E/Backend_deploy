#!/usr/bin/env python
"""모든 상품 가격 이력 저장 스크립트"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

import logging
logging.disable(logging.DEBUG)

from modules.products.models import ProductModel
from modules.price_prediction.models import PriceHistoryModel
from modules.products.crawlers.danawa import DanawaCrawler
from django.utils import timezone
from datetime import datetime


def main():
    products = ProductModel.objects.filter(deleted_at__isnull=True)
    print(f"총 {products.count()}개 상품 가격 이력 저장 시작\n")
    print("=" * 60)

    crawler = DanawaCrawler(delay_range=(0.5, 1))
    total_saved = 0

    for product in products:
        pcode = product.danawa_product_id

        # 기존 가격 이력 확인
        existing = PriceHistoryModel.objects.filter(product=product).count()
        if existing > 0:
            print(f"✓ [{pcode}] {product.name[:30]}: 이미 {existing}개 존재")
            total_saved += existing
            continue

        # 가격 이력 크롤링
        try:
            price_history = crawler.get_price_history(pcode, months=24)

            saved = 0
            for ph in price_history:
                if ph.price is None:
                    continue

                recorded_date = None
                if ph.date:
                    try:
                        parts = ph.date.split('-')
                        if len(parts) == 2:
                            first, second = parts
                            if int(first) > 12:
                                year = 2000 + int(first)
                                month = int(second)
                                recorded_date = timezone.make_aware(datetime(year, month, 1))
                            else:
                                month = int(first)
                                current_year = timezone.now().year
                                recorded_date = timezone.make_aware(datetime(current_year, month, 1))
                    except Exception:
                        continue

                if not recorded_date:
                    continue

                try:
                    PriceHistoryModel.objects.update_or_create(
                        product=product,
                        recorded_at__year=recorded_date.year,
                        recorded_at__month=recorded_date.month,
                        defaults={
                            'lowest_price': ph.price,
                            'recorded_at': recorded_date,
                        }
                    )
                    saved += 1
                except Exception:
                    pass

            print(f"✓ [{pcode}] {product.name[:30]}: {saved}개 저장")
            total_saved += saved

        except Exception as e:
            print(f"✗ [{pcode}] {product.name[:30]}: 오류 - {str(e)[:50]}")

    crawler.close()

    print("=" * 60)
    print(f"\n총 {total_saved}개 가격 이력 저장 완료!")

    # 최종 확인
    final_count = PriceHistoryModel.objects.count()
    print(f"DB 내 전체 가격 이력 레코드: {final_count}개")


if __name__ == '__main__':
    main()
