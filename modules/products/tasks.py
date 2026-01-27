"""
Products module Celery tasks.
다나와 크롤링 데이터를 DB에 저장하는 태스크들.
"""
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ============================================================
# 카테고리 헬퍼 함수
# ============================================================

def get_or_create_category_hierarchy(
    category_1: Optional[str],
    category_2: Optional[str],
    category_3: Optional[str],
    category_4: Optional[str]
):
    """
    카테고리 계층 구조를 생성하거나 조회.

    Args:
        category_1: 대분류
        category_2: 중분류
        category_3: 소분류
        category_4: 세분류

    Returns:
        가장 하위 카테고리 모델 (없으면 None)
    """
    from modules.categories.models import CategoryModel

    categories = [category_1, category_2, category_3, category_4]
    categories = [c for c in categories if c]  # None 제거

    if not categories:
        return None

    parent = None
    current_category = None

    for name in categories:
        current_category, _ = CategoryModel.objects.get_or_create(
            name=name,
            parent=parent,
            defaults={'deleted_at': None}
        )
        parent = current_category

    return current_category


# ============================================================
# 크롤링 태스크
# ============================================================

@shared_task(name='products.crawl_product')
def crawl_product(danawa_product_id: str) -> dict:
    """
    단일 상품 전체 크롤링 및 DB 저장.

    CSV 데이터 명세서의 모든 필드를 크롤링하여 저장:
    - 상품 기본 정보 → ProductModel
    - 카테고리 → CategoryModel (계층 구조)
    - 쇼핑몰/판매자 정보 → MallInformationModel
    - 24개월 가격 이력 → PriceHistoryModel
    - 리뷰 → ReviewModel

    Args:
        danawa_product_id: 다나와 상품 ID (pcode)

    Returns:
        결과 딕셔너리
    """
    from .crawlers import DanawaCrawler
    from .models import ProductModel, MallInformationModel
    from modules.timers.models import PriceHistoryModel
    from modules.orders.models import ReviewModel
    from modules.users.models import UserModel

    try:
        with DanawaCrawler() as crawler:
            # 전체 상품 데이터 크롤링
            full_data = crawler.crawl_full_product_data(danawa_product_id)

            if not full_data:
                return {'success': False, 'error': 'Failed to crawl product data'}

            product_info = full_data.get('product')
            mall_prices = full_data.get('mall_prices', [])
            price_history = full_data.get('price_history', [])
            reviews = full_data.get('reviews', [])

            if not product_info:
                return {'success': False, 'error': 'No product info found'}

            # ========================================
            # 1. 카테고리 저장
            # ========================================
            category = get_or_create_category_hierarchy(
                product_info.category_1,
                product_info.category_2,
                product_info.category_3,
                product_info.category_4
            )

            # ========================================
            # 2. 상품 정보 저장 (ProductModel)
            # ========================================
            # detail_spec에 spec과 spec_summary 모두 저장
            detail_spec_data = {
                'spec': product_info.spec,
                'spec_summary': product_info.spec_summary,
            }

            product, created = ProductModel.objects.update_or_create(
                danawa_product_id=danawa_product_id,
                defaults={
                    'name': product_info.product_name,
                    'lowest_price': product_info.min_price or product_info.price,
                    'brand': product_info.brand or '',
                    'detail_spec': detail_spec_data,
                    'registration_month': product_info.registration_date,
                    'product_status': product_info.product_status,
                    'category': category,
                    'review_count': product_info.mall_review_count,
                    'review_rating': product_info.review_rating,
                }
            )

            action = 'created' if created else 'updated'
            logger.info(f"Product {danawa_product_id} {action}")

            # ========================================
            # 3. 쇼핑몰/판매자 정보 저장 (MallInformationModel)
            # ========================================
            mall_count = 0
            for mall in mall_prices:
                MallInformationModel.objects.update_or_create(
                    product=product,
                    mall_name=mall.mall_name,
                    defaults={
                        'current_price': mall.price,
                        'product_page_url': mall.product_url or '',
                        'seller_logo_url': mall.logo_url or '',
                        'representative_image_url': product_info.image_url or '',
                        'additional_image_urls': product_info.additional_images,
                        'detail_page_image_url': ', '.join(product_info.detail_page_images) if product_info.detail_page_images else '',
                        'product_description_image_url': ', '.join(product_info.product_description_images) if product_info.product_description_images else '',
                    }
                )
                mall_count += 1

            # 쇼핑몰 정보가 없을 경우에도 이미지 정보 저장을 위해 기본 레코드 생성
            if not mall_prices and product_info.image_url:
                MallInformationModel.objects.update_or_create(
                    product=product,
                    mall_name='다나와',
                    defaults={
                        'current_price': product_info.min_price or product_info.price,
                        'product_page_url': f'https://prod.danawa.com/info/?pcode={danawa_product_id}',
                        'representative_image_url': product_info.image_url or '',
                        'additional_image_urls': product_info.additional_images,
                        'detail_page_image_url': ', '.join(product_info.detail_page_images) if product_info.detail_page_images else '',
                        'product_description_image_url': ', '.join(product_info.product_description_images) if product_info.product_description_images else '',
                    }
                )
                mall_count = 1

            # ========================================
            # 4. 가격 이력 저장 (PriceHistoryModel) - 24개월
            # ========================================
            history_count = 0

            for ph in price_history:
                if ph.price is None:
                    continue

                # 날짜 문자열 파싱 (형식: "YY-MM" 또는 "MM-DD")
                recorded_date = None
                if ph.date:
                    try:
                        parts = ph.date.split('-')
                        if len(parts) == 2:
                            first, second = parts
                            # "YY-MM" 형식 (24-04, 25-01 등)
                            if int(first) > 12:
                                year = 2000 + int(first)
                                month = int(second)
                                recorded_date = timezone.make_aware(
                                    datetime(year, month, 1)
                                )
                            # "MM-DD" 형식 (01-06, 12-23 등) - 최근 데이터
                            else:
                                month = int(first)
                                day = int(second)
                                # 올해 또는 작년으로 추정
                                current_year = timezone.now().year
                                try:
                                    recorded_date = timezone.make_aware(
                                        datetime(current_year, month, day)
                                    )
                                    # 미래 날짜면 작년으로 조정
                                    if recorded_date > timezone.now():
                                        recorded_date = timezone.make_aware(
                                            datetime(current_year - 1, month, day)
                                        )
                                except ValueError:
                                    # 날짜가 유효하지 않으면 월의 1일로 설정
                                    recorded_date = timezone.make_aware(
                                        datetime(current_year, month, 1)
                                    )
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse date '{ph.date}': {e}")
                        continue

                if not recorded_date:
                    continue

                # 중복 방지: 해당 날짜에 이미 기록이 있으면 업데이트
                try:
                    PriceHistoryModel.objects.update_or_create(
                        danawa_product_id=product.danawa_product_id,
                        recorded_at__date=recorded_date.date(),
                        defaults={
                            'lowest_price': ph.price,
                            'recorded_at': recorded_date,
                        }
                    )
                    history_count += 1
                except Exception as e:
                    # 중복 키 등의 오류 시 월 단위로 재시도
                    try:
                        PriceHistoryModel.objects.update_or_create(
                            danawa_product_id=product.danawa_product_id,
                            recorded_at__year=recorded_date.year,
                            recorded_at__month=recorded_date.month,
                            defaults={
                                'lowest_price': ph.price,
                                'recorded_at': recorded_date,
                            }
                        )
                        history_count += 1
                    except Exception:
                        logger.warning(f"Failed to save price history for {recorded_date}: {e}")

            # ========================================
            # 5. 리뷰 요약 정보 저장 (ReviewModel)
            # ========================================
            # 다나와에서 개별 리뷰 콘텐츠는 JavaScript로 동적 로드되어 크롤링 어려움
            # 대신 상품의 리뷰 통계 정보(총 리뷰 수, 평균 별점)를 저장
            review_count = 0

            # 리뷰 통계가 있을 경우에만 저장
            if product_info.mall_review_count > 0:
                system_user = None
                try:
                    system_user = UserModel.objects.filter(email='system@danawa.com').first()
                    if not system_user:
                        system_user = UserModel.objects.first()
                except Exception:
                    pass

                if system_user:
                    # 상품당 하나의 리뷰 요약 레코드 생성/업데이트
                    review_obj, review_created = ReviewModel.objects.update_or_create(
                        danawa_product_id=product.danawa_product_id,
                        reviewer_name='다나와 통합 리뷰',  # 시스템 생성 리뷰 식별용
                        defaults={
                            'user': system_user,
                            'mall_name': '다나와 (외부 쇼핑몰 통합)',
                            'content': f'{product_info.product_name} 상품의 외부 쇼핑몰 리뷰 통계입니다. 총 {product_info.mall_review_count}개의 리뷰가 있으며 평균 별점은 {product_info.review_rating or "N/A"}점입니다.',
                            'rating': int(product_info.review_rating) if product_info.review_rating else None,
                            'external_review_count': product_info.mall_review_count,
                        }
                    )
                    review_count = 1 if review_created else 0
                    logger.info(f"Review summary for {danawa_product_id}: {product_info.mall_review_count} reviews, rating {product_info.review_rating}")

            return {
                'success': True,
                'product_id': product.id,
                'danawa_product_id': danawa_product_id,
                'action': action,
                'mall_count': mall_count,
                'history_count': history_count,
                'review_count': review_count,
            }

    except Exception as e:
        logger.error(f"Error crawling product {danawa_product_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='products.crawl_product_basic')
def crawl_product_basic(danawa_product_id: str) -> dict:
    """
    상품 기본 정보만 크롤링 (가격, 쇼핑몰 정보).
    빠른 가격 업데이트용.

    Args:
        danawa_product_id: 다나와 상품 ID

    Returns:
        결과 딕셔너리
    """
    from .crawlers import DanawaCrawler
    from .models import ProductModel, MallInformationModel

    try:
        with DanawaCrawler() as crawler:
            # 상품 정보 크롤링
            product_info = crawler.get_product_info(danawa_product_id)

            if not product_info:
                return {'success': False, 'error': 'Failed to crawl product'}

            # 카테고리 처리
            category = get_or_create_category_hierarchy(
                product_info.category_1,
                product_info.category_2,
                product_info.category_3,
                product_info.category_4
            )

            # detail_spec 구성
            detail_spec_data = {
                'spec': product_info.spec,
                'spec_summary': product_info.spec_summary,
            }

            # DB 저장 (upsert)
            product, created = ProductModel.objects.update_or_create(
                danawa_product_id=danawa_product_id,
                defaults={
                    'name': product_info.product_name,
                    'lowest_price': product_info.min_price or product_info.price,
                    'brand': product_info.brand or '',
                    'detail_spec': detail_spec_data,
                    'registration_month': product_info.registration_date,
                    'product_status': product_info.product_status,
                    'category': category,
                    'review_count': product_info.mall_review_count,
                    'review_rating': product_info.review_rating,
                }
            )

            # 쇼핑몰 가격 정보 크롤링
            mall_prices = crawler.get_mall_prices(danawa_product_id)

            for mall in mall_prices:
                MallInformationModel.objects.update_or_create(
                    product=product,
                    mall_name=mall.mall_name,
                    defaults={
                        'current_price': mall.price,
                        'product_page_url': mall.product_url or '',
                        'seller_logo_url': mall.logo_url or '',
                        'representative_image_url': product_info.image_url or '',
                        'additional_image_urls': product_info.additional_images,
                    }
                )

            action = 'created' if created else 'updated'
            logger.info(f"Product {danawa_product_id} {action}")

            return {
                'success': True,
                'product_id': product.id,
                'action': action,
                'mall_count': len(mall_prices),
            }

    except Exception as e:
        logger.error(f"Error crawling product {danawa_product_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='products.crawl_products_batch')
def crawl_products_batch(danawa_product_ids: list, full_crawl: bool = True) -> dict:
    """
    여러 상품 일괄 크롤링.

    Args:
        danawa_product_ids: 다나와 상품 ID 리스트
        full_crawl: True면 전체 크롤링, False면 기본 정보만

    Returns:
        결과 딕셔너리
    """
    results = {
        'total': len(danawa_product_ids),
        'success': 0,
        'failed': 0,
        'errors': [],
    }

    crawl_func = crawl_product if full_crawl else crawl_product_basic

    for product_id in danawa_product_ids:
        result = crawl_func(product_id)

        if result.get('success'):
            results['success'] += 1
        else:
            results['failed'] += 1
            results['errors'].append({
                'product_id': product_id,
                'error': result.get('error'),
            })

    logger.info(
        f"Batch crawl completed: {results['success']}/{results['total']} succeeded"
    )

    return results


@shared_task(name='products.search_and_crawl')
def search_and_crawl(keyword: str, limit: int = 10, full_crawl: bool = True) -> dict:
    """
    키워드로 검색 후 결과 상품들 크롤링.

    Args:
        keyword: 검색 키워드
        limit: 최대 크롤링 수
        full_crawl: True면 전체 크롤링 (가격이력, 리뷰 포함)

    Returns:
        결과 딕셔너리
    """
    from .crawlers import DanawaCrawler

    try:
        with DanawaCrawler() as crawler:
            # 검색
            search_results = crawler.search_products(keyword, limit=limit)

            if not search_results:
                return {'success': False, 'error': 'No search results'}

            # 검색된 상품들 크롤링 태스크 생성
            product_ids = [r['danawa_product_id'] for r in search_results]

            # 비동기로 크롤링 시작
            crawl_products_batch.delay(product_ids, full_crawl=full_crawl)

            return {
                'success': True,
                'keyword': keyword,
                'queued_count': len(product_ids),
                'product_ids': product_ids,
            }

    except Exception as e:
        logger.error(f"Error in search_and_crawl for '{keyword}': {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='products.update_all_prices')
def update_all_prices() -> dict:
    """
    모든 상품의 가격 정보 업데이트.
    주기적 실행용 (예: 매일 새벽).
    기본 정보만 업데이트 (빠른 실행).

    Returns:
        결과 딕셔너리
    """
    from .models import ProductModel

    products = ProductModel.objects.filter(
        deleted_at__isnull=True
    ).values_list('danawa_product_id', flat=True)

    product_ids = list(products)

    if not product_ids:
        return {'success': True, 'message': 'No products to update'}

    # 배치로 크롤링 시작 (기본 정보만)
    crawl_products_batch.delay(product_ids, full_crawl=False)

    logger.info(f"Queued {len(product_ids)} products for price update")

    return {
        'success': True,
        'queued_count': len(product_ids),
    }


@shared_task(name='products.full_update_all_products')
def full_update_all_products() -> dict:
    """
    모든 상품의 전체 정보 업데이트.
    주기적 실행용 (예: 매주).
    가격 이력, 리뷰 포함.

    Returns:
        결과 딕셔너리
    """
    from .models import ProductModel

    products = ProductModel.objects.filter(
        deleted_at__isnull=True
    ).values_list('danawa_product_id', flat=True)

    product_ids = list(products)

    if not product_ids:
        return {'success': True, 'message': 'No products to update'}

    # 배치로 전체 크롤링 시작
    crawl_products_batch.delay(product_ids, full_crawl=True)

    logger.info(f"Queued {len(product_ids)} products for full update")

    return {
        'success': True,
        'queued_count': len(product_ids),
    }


# ============================================================
# 가격 이력 태스크
# ============================================================

@shared_task(name='products.record_price_history')
def record_price_history(product_id: int) -> dict:
    """
    상품의 현재 최저가를 가격 이력에 기록.

    Args:
        product_id: 상품 ID

    Returns:
        결과 딕셔너리
    """
    from .models import ProductModel
    from modules.timers.models import PriceHistoryModel

    try:
        product = ProductModel.objects.get(id=product_id, deleted_at__isnull=True)

        PriceHistoryModel.objects.create(
            danawa_product_id=product.danawa_product_id,
            lowest_price=product.lowest_price,
            recorded_at=timezone.now(),
        )

        return {'success': True, 'product_id': product_id}

    except ProductModel.DoesNotExist:
        return {'success': False, 'error': 'Product not found'}
    except Exception as e:
        logger.error(f"Error recording price history for {product_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='products.record_all_price_histories')
def record_all_price_histories() -> dict:
    """
    모든 상품의 가격 이력 기록.
    주기적 실행용 (예: 매일).

    Returns:
        결과 딕셔너리
    """
    from .models import ProductModel

    products = ProductModel.objects.filter(deleted_at__isnull=True)
    count = 0

    for product in products:
        record_price_history.delay(product.id)
        count += 1

    return {
        'success': True,
        'queued_count': count,
    }


# ============================================================
# 리뷰 크롤링 태스크
# ============================================================

@shared_task(name='products.crawl_product_full_selenium')
def crawl_product_full_selenium(danawa_product_id: str) -> dict:
    """
    Selenium을 사용하여 상품 전체 크롤링 (쇼핑몰 정보 + 이미지 포함).

    requests 기반 크롤링으로 가져오지 못하는 데이터를 Selenium으로 수집:
    - 쇼핑몰별 가격 정보 (seller_logo_url 포함)
    - 상세 이미지, 추가 이미지, 제품설명 이미지

    Args:
        danawa_product_id: 다나와 상품 ID

    Returns:
        결과 딕셔너리
    """
    from .crawlers import DanawaCrawler
    from .models import ProductModel, MallInformationModel

    try:
        product = ProductModel.objects.get(
            danawa_product_id=danawa_product_id,
            deleted_at__isnull=True
        )
    except ProductModel.DoesNotExist:
        return {'success': False, 'error': 'Product not found in DB'}

    try:
        with DanawaCrawler(delay_range=(0.5, 1)) as crawler:
            # 쇼핑몰 가격 정보 크롤링 (Selenium)
            mall_prices = crawler.get_mall_prices_with_selenium(danawa_product_id, limit=30)

            # 이미지 크롤링 (Selenium)
            images = crawler.get_product_images_with_selenium(danawa_product_id)

            mall_count = 0
            for mall in mall_prices:
                MallInformationModel.objects.update_or_create(
                    product=product,
                    mall_name=mall.mall_name,
                    defaults={
                        'current_price': mall.price,
                        'product_page_url': mall.product_url or '',
                        'seller_logo_url': mall.logo_url or '',
                        'representative_image_url': images.get('main_image') or '',
                        'additional_image_urls': images.get('additional_images', []),
                        'detail_page_image_url': ', '.join(images.get('detail_images', [])),
                        'product_description_image_url': ', '.join(images.get('description_images', [])),
                    }
                )
                mall_count += 1

            # 쇼핑몰 정보가 없을 경우 기본 레코드 생성
            if not mall_prices and images.get('main_image'):
                MallInformationModel.objects.update_or_create(
                    product=product,
                    mall_name='다나와',
                    defaults={
                        'current_price': product.lowest_price,
                        'product_page_url': f'https://prod.danawa.com/info/?pcode={danawa_product_id}',
                        'representative_image_url': images.get('main_image') or '',
                        'additional_image_urls': images.get('additional_images', []),
                        'detail_page_image_url': ', '.join(images.get('detail_images', [])),
                        'product_description_image_url': ', '.join(images.get('description_images', [])),
                    }
                )
                mall_count = 1

            logger.info(f"Product {danawa_product_id} updated with Selenium: {mall_count} malls")

            return {
                'success': True,
                'product_id': product.id,
                'mall_count': mall_count,
                'images': {
                    'main': bool(images.get('main_image')),
                    'additional': len(images.get('additional_images', [])),
                    'detail': len(images.get('detail_images', [])),
                    'description': len(images.get('description_images', [])),
                }
            }

    except Exception as e:
        logger.error(f"Error crawling product {danawa_product_id} with Selenium: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='products.crawl_individual_reviews_selenium')
def crawl_individual_reviews_selenium(danawa_product_id: str, limit: int = 50) -> dict:
    """
    Selenium을 사용하여 개별 리뷰 크롤링 및 저장.

    다나와 리뷰는 JavaScript로 동적 로드되므로 Selenium을 사용합니다.
    크롤링한 개별 리뷰를 ReviewModel에 저장합니다.

    Args:
        danawa_product_id: 다나와 상품 ID
        limit: 최대 리뷰 수

    Returns:
        결과 딕셔너리
    """
    from .crawlers import DanawaCrawler
    from .models import ProductModel
    from modules.orders.models import ReviewModel
    from modules.users.models import UserModel

    try:
        product = ProductModel.objects.get(
            danawa_product_id=danawa_product_id,
            deleted_at__isnull=True
        )
    except ProductModel.DoesNotExist:
        return {'success': False, 'error': 'Product not found in DB'}

    try:
        with DanawaCrawler() as crawler:
            # Selenium으로 개별 리뷰 크롤링
            reviews = crawler.get_reviews_with_selenium(danawa_product_id, limit=limit)

            if not reviews:
                return {'success': True, 'message': 'No reviews found', 'count': 0}

            # 시스템 유저 조회 (크롤링된 리뷰는 시스템 유저로 저장)
            system_user = UserModel.objects.filter(email='system@danawa.com').first()
            if not system_user:
                system_user = UserModel.objects.first()

            if not system_user:
                return {'success': False, 'error': 'No user available for review creation'}

            created_count = 0
            updated_count = 0

            for review in reviews:
                # 리뷰 고유 식별: 상품ID + 작성자 + 날짜 + 내용 일부
                content_preview = (review.content or '')[:100]

                # 기존 리뷰 확인 (중복 방지)
                existing_review = ReviewModel.objects.filter(
                    danawa_product_id=danawa_product_id,
                    reviewer_name=review.reviewer_name or 'Unknown',
                    mall_name=review.shop_name,
                ).first()

                if existing_review:
                    # 기존 리뷰 업데이트
                    existing_review.content = review.content
                    existing_review.rating = review.rating
                    existing_review.review_images = review.review_images if review.review_images else None
                    existing_review.save(update_fields=['content', 'rating', 'review_images', 'updated_at'])
                    updated_count += 1
                else:
                    # 새 리뷰 생성
                    ReviewModel.objects.create(
                        danawa_product_id=danawa_product_id,
                        user=system_user,
                        mall_name=review.shop_name,
                        reviewer_name=review.reviewer_name or 'Unknown',
                        content=review.content,
                        rating=review.rating,
                        review_images=review.review_images if review.review_images else None,
                    )
                    created_count += 1

            logger.info(
                f"Reviews for {danawa_product_id}: {created_count} created, {updated_count} updated"
            )

            return {
                'success': True,
                'product_id': product.id,
                'total_reviews': len(reviews),
                'created': created_count,
                'updated': updated_count,
            }

    except Exception as e:
        logger.error(f"Error crawling individual reviews for {danawa_product_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='products.crawl_product_reviews')
def crawl_product_reviews(danawa_product_id: str) -> dict:
    """
    특정 상품의 리뷰 통계 정보 크롤링 및 저장.
    다나와에서 개별 리뷰 콘텐츠는 JavaScript로 동적 로드되어 크롤링 어려움.
    대신 상품의 리뷰 통계 정보(총 리뷰 수, 평균 별점)를 저장.

    Args:
        danawa_product_id: 다나와 상품 ID

    Returns:
        결과 딕셔너리
    """
    from .crawlers import DanawaCrawler
    from .models import ProductModel
    from modules.orders.models import ReviewModel
    from modules.users.models import UserModel

    try:
        product = ProductModel.objects.get(
            danawa_product_id=danawa_product_id,
            deleted_at__isnull=True
        )
    except ProductModel.DoesNotExist:
        return {'success': False, 'error': 'Product not found in DB'}

    try:
        with DanawaCrawler() as crawler:
            # 상품 정보에서 리뷰 통계 가져오기
            product_info = crawler.get_product_info(danawa_product_id)

            if not product_info:
                return {'success': False, 'error': 'Failed to get product info'}

            if product_info.mall_review_count == 0:
                return {'success': True, 'message': 'No reviews found', 'count': 0}

            # 시스템 유저 조회
            system_user = UserModel.objects.filter(email='system@danawa.com').first()
            if not system_user:
                system_user = UserModel.objects.first()

            if not system_user:
                return {'success': False, 'error': 'No user available for review creation'}

            # 리뷰 요약 레코드 생성/업데이트
            review_obj, review_created = ReviewModel.objects.update_or_create(
                danawa_product_id=danawa_product_id,
                reviewer_name='다나와 통합 리뷰',
                defaults={
                    'user': system_user,
                    'mall_name': '다나와 (외부 쇼핑몰 통합)',
                    'content': f'{product_info.product_name} 상품의 외부 쇼핑몰 리뷰 통계입니다. 총 {product_info.mall_review_count}개의 리뷰가 있으며 평균 별점은 {product_info.review_rating or "N/A"}점입니다.',
                    'rating': int(product_info.review_rating) if product_info.review_rating else None,
                    'external_review_count': product_info.mall_review_count,
                }
            )

            # ProductModel의 리뷰 정보도 업데이트
            product.review_count = product_info.mall_review_count
            product.review_rating = product_info.review_rating
            product.save(update_fields=['review_count', 'review_rating'])

            return {
                'success': True,
                'product_id': product.id,
                'review_count': product_info.mall_review_count,
                'review_rating': product_info.review_rating,
                'created': review_created,
            }

    except Exception as e:
        logger.error(f"Error crawling reviews for {danawa_product_id}: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================
# 이미지 크롤링 태스크
# ============================================================

@shared_task(name='products.update_mall_images')
def update_mall_images(danawa_product_id: str) -> dict:
    """
    Selenium을 사용하여 특정 상품의 이미지 정보만 업데이트.

    mall_information 테이블의 다음 필드를 업데이트:
    - seller_logo_url (판매처 로고)
    - product_description_image_url (제품설명 이미지)
    - detail_page_image_url (상세페이지 이미지)
    - additional_image_urls (추가 이미지)

    Args:
        danawa_product_id: 다나와 상품 ID

    Returns:
        결과 딕셔너리
    """
    from .crawlers import DanawaCrawler
    from .models import ProductModel, MallInformationModel

    try:
        product = ProductModel.objects.get(
            danawa_product_id=danawa_product_id,
            deleted_at__isnull=True
        )
    except ProductModel.DoesNotExist:
        return {'success': False, 'error': 'Product not found in DB'}

    try:
        with DanawaCrawler(delay_range=(0.5, 1)) as crawler:
            # 쇼핑몰 가격 정보 (로고 URL 포함) 크롤링
            mall_prices = crawler.get_mall_prices_with_selenium(danawa_product_id, limit=30)

            # 이미지 크롤링
            images = crawler.get_product_images_with_selenium(danawa_product_id)

            # 기존 MallInformation 레코드 업데이트
            updated_count = 0

            if mall_prices:
                for mall in mall_prices:
                    MallInformationModel.objects.update_or_create(
                        product=product,
                        mall_name=mall.mall_name,
                        defaults={
                            'current_price': mall.price,
                            'product_page_url': mall.product_url or '',
                            'seller_logo_url': mall.logo_url or '',
                            'representative_image_url': images.get('main_image') or '',
                            'additional_image_urls': images.get('additional_images', []),
                            'detail_page_image_url': ', '.join(images.get('detail_images', [])),
                            'product_description_image_url': ', '.join(images.get('description_images', [])),
                        }
                    )
                    updated_count += 1
            else:
                # 쇼핑몰 정보가 없을 경우 기존 레코드만 이미지 업데이트
                existing_malls = MallInformationModel.objects.filter(
                    product=product,
                    deleted_at__isnull=True
                )
                for mall_info in existing_malls:
                    mall_info.representative_image_url = images.get('main_image') or mall_info.representative_image_url
                    mall_info.additional_image_urls = images.get('additional_images', []) or mall_info.additional_image_urls
                    mall_info.detail_page_image_url = ', '.join(images.get('detail_images', [])) or mall_info.detail_page_image_url
                    mall_info.product_description_image_url = ', '.join(images.get('description_images', [])) or mall_info.product_description_image_url
                    mall_info.save()
                    updated_count += 1

            logger.info(f"Updated images for product {danawa_product_id}: {updated_count} mall records")

            return {
                'success': True,
                'product_id': product.id,
                'updated_count': updated_count,
                'images': {
                    'main': bool(images.get('main_image')),
                    'additional': len(images.get('additional_images', [])),
                    'detail': len(images.get('detail_images', [])),
                    'description': len(images.get('description_images', [])),
                }
            }

    except Exception as e:
        logger.error(f"Error updating images for {danawa_product_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task(name='products.update_all_mall_images')
def update_all_mall_images() -> dict:
    """
    모든 상품의 이미지 정보 업데이트 (Selenium).

    mall_information 테이블에서 이미지가 없는 상품들의 이미지를 크롤링합니다.

    Returns:
        결과 딕셔너리
    """
    from .models import ProductModel, MallInformationModel

    # 이미지가 비어있는 상품들 조회
    products_without_images = ProductModel.objects.filter(
        deleted_at__isnull=True
    ).exclude(
        mall_information__additional_image_urls__len__gt=0  # JSONField에 값이 있는 경우 제외
    ).values_list('danawa_product_id', flat=True).distinct()

    product_ids = list(products_without_images)

    if not product_ids:
        # 이미지가 없는 상품이 없으면 전체 상품 대상으로 업데이트
        product_ids = list(ProductModel.objects.filter(
            deleted_at__isnull=True
        ).values_list('danawa_product_id', flat=True))

    count = 0
    for product_id in product_ids:
        update_mall_images.delay(product_id)
        count += 1

    logger.info(f"Queued {count} products for image update")

    return {
        'success': True,
        'queued_count': count,
    }


# ============================================================
# 임베딩 태스크
# ============================================================

@shared_task(name='products.generate_product_embedding')
def generate_product_embedding(product_id: int) -> bool:
    """
    상품 임베딩 생성 (벡터 검색용).

    Args:
        product_id: 상품 ID

    Returns:
        성공 여부
    """
    from .models import ProductModel

    try:
        product = ProductModel.objects.get(id=product_id)
    except ProductModel.DoesNotExist:
        return False

    # 임베딩 텍스트 생성
    spec_summary = ''
    if product.detail_spec and isinstance(product.detail_spec, dict):
        spec_summary = ' '.join(product.detail_spec.get('spec_summary', []))

    text = f"{product.name}. {product.brand}. {spec_summary}"

    try:
        from shared.ai_clients import OpenAIClient
        client = OpenAIClient()
        embedding = client.create_embedding(text)

        product.detail_spec_vector = embedding
        product.save()
        return True
    except Exception as e:
        logger.error(f"Error generating embedding for product {product_id}: {e}")
        return False


@shared_task(name='products.generate_all_embeddings')
def generate_all_embeddings() -> dict:
    """
    임베딩이 없는 모든 상품에 대해 임베딩 생성.

    Returns:
        결과 딕셔너리
    """
    from .models import ProductModel

    products = ProductModel.objects.filter(
        deleted_at__isnull=True,
        detail_spec_vector__isnull=True
    )

    count = 0
    for product in products:
        generate_product_embedding.delay(product.id)
        count += 1

    return {
        'success': True,
        'queued_count': count,
    }
