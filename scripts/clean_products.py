#!/usr/bin/env python
"""컴퓨터/노트북/조립PC 외 상품 삭제 스크립트"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

import logging
logging.disable(logging.DEBUG)

from modules.products.models import ProductModel, MallInformationModel
from modules.price_prediction.models import PriceHistoryModel
from modules.orders.models import ReviewModel


def main():
    # 삭제할 상품 (컴퓨터/노트북/조립PC와 무관)
    products_to_delete = [
        '78235382',  # 삼성전자 Q9000 에어컨
        '77961662',  # 삼성전자 Q9000 에어컨
        '17432099',  # LG전자 오브제컬렉션 냉장고
        '62273714',  # 삼성전자 비스포크 냉장고
        '101956046', # APPLE 아이폰17
    ]

    print("=" * 60)
    print("컴퓨터/노트북/조립PC 외 상품 삭제")
    print("=" * 60)

    for pcode in products_to_delete:
        try:
            product = ProductModel.objects.get(danawa_product_id=pcode)
            name = product.name[:30]

            # 관련 데이터 삭제
            mall_count = MallInformationModel.objects.filter(product=product).delete()[0]
            history_count = PriceHistoryModel.objects.filter(product=product).delete()[0]
            review_count = ReviewModel.objects.filter(product=product).delete()[0]

            # 상품 삭제
            product.delete()

            print(f"✓ [{pcode}] {name}")
            print(f"    삭제: 쇼핑몰 {mall_count}개, 가격이력 {history_count}개, 리뷰 {review_count}개")
        except ProductModel.DoesNotExist:
            print(f"✗ [{pcode}] 존재하지 않음")

    print("\n" + "=" * 60)
    print("삭제 완료! 남은 상품:")
    print("=" * 60)

    remaining = ProductModel.objects.filter(deleted_at__isnull=True)
    for p in remaining:
        print(f"  [{p.danawa_product_id}] {p.name[:40]}")

    print(f"\n총 {remaining.count()}개 상품")


if __name__ == '__main__':
    main()
