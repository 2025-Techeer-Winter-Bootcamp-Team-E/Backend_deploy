#!/usr/bin/env python
"""가격 이력 DB 저장 테스트 스크립트"""
import os
import sys
import django

# Django 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from modules.products.crawlers.danawa import DanawaCrawler
from modules.products.models import ProductModel
from modules.price_prediction.models import PriceHistoryModel
from django.utils import timezone
from datetime import datetime

# 테스트 상품
PCODE = "44762393"


def main():
    print("=" * 60)
    print("1. 기존 가격 이력 확인")
    print("=" * 60)

    try:
        product = ProductModel.objects.get(danawa_product_id=PCODE)
        print(f"상품: {product.name} (ID: {product.id})")

        existing_count = PriceHistoryModel.objects.filter(product=product).count()
        print(f"기존 가격 이력: {existing_count}개")
    except ProductModel.DoesNotExist:
        print("상품이 DB에 없습니다. 먼저 상품을 크롤링해주세요.")
        return

    print("\n" + "=" * 60)
    print("2. 가격 이력 크롤링")
    print("=" * 60)

    crawler = DanawaCrawler(delay_range=(0.5, 1))
    price_history = crawler.get_price_history(PCODE, months=24)
    crawler.close()

    print(f"크롤링된 가격 이력: {len(price_history)}개")

    print("\n" + "=" * 60)
    print("3. 가격 이력 DB 저장")
    print("=" * 60)

    saved_count = 0
    for ph in price_history:
        if ph.price is None:
            continue

        # 날짜 파싱
        recorded_date = None
        if ph.date:
            try:
                parts = ph.date.split('-')
                if len(parts) == 2:
                    first, second = parts
                    # "YY-MM" 형식
                    if int(first) > 12:
                        year = 2000 + int(first)
                        month = int(second)
                        recorded_date = timezone.make_aware(
                            datetime(year, month, 1)
                        )
                    # "MM-DD" 형식
                    else:
                        month = int(first)
                        day = int(second)
                        current_year = timezone.now().year
                        try:
                            recorded_date = timezone.make_aware(
                                datetime(current_year, month, day)
                            )
                            if recorded_date > timezone.now():
                                recorded_date = timezone.make_aware(
                                    datetime(current_year - 1, month, day)
                                )
                        except ValueError:
                            recorded_date = timezone.make_aware(
                                datetime(current_year, month, 1)
                            )
            except (ValueError, IndexError) as e:
                print(f"날짜 파싱 오류: {ph.date} - {e}")
                continue

        if not recorded_date:
            continue

        # DB 저장
        try:
            obj, created = PriceHistoryModel.objects.update_or_create(
                product=product,
                recorded_at__year=recorded_date.year,
                recorded_at__month=recorded_date.month,
                defaults={
                    'lowest_price': ph.price,
                    'recorded_at': recorded_date,
                }
            )
            action = "생성" if created else "업데이트"
            saved_count += 1
            print(f"  {ph.date}: {ph.price:,}원 ({action})")
        except Exception as e:
            print(f"  {ph.date}: 저장 오류 - {e}")

    print(f"\n저장 완료: {saved_count}개")

    print("\n" + "=" * 60)
    print("4. 저장된 가격 이력 확인")
    print("=" * 60)

    histories = PriceHistoryModel.objects.filter(
        product=product
    ).order_by('recorded_at')

    print(f"\n총 {histories.count()}개 기록\n")
    print(f"{'날짜':^12} | {'최저가':>12}")
    print("-" * 30)

    for h in histories:
        date_str = h.recorded_at.strftime('%Y-%m') if h.recorded_at else "N/A"
        print(f"{date_str:^12} | {h.lowest_price:>10,}원")


if __name__ == '__main__':
    main()
