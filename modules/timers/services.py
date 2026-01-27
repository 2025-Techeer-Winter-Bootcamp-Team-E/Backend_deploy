"""
Timers business logic services.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from django.db import transaction
from django.utils import timezone

from .models import TimerModel, PriceHistoryModel
from .exceptions import (
    PredictionNotFoundError,
    InsufficientHistoryDataError,
    PredictionServiceError,
)

logger = logging.getLogger(__name__)


class TimerService:
    """Service for timer operations."""

    def get_timer_by_id(self, timer_id: int) -> Optional[TimerModel]:
        """Get timer by ID."""
        try:
            return TimerModel.objects.get(
                id=timer_id,
                deleted_at__isnull=True
            )
        except TimerModel.DoesNotExist:
            return None

    def get_timer_by_product(
        self,
        danawa_product_id: str,
        prediction_date: Optional[datetime] = None
    ) -> Optional[TimerModel]:
        """Get latest timer for a product."""
        queryset = TimerModel.objects.filter(
            danawa_product_id=danawa_product_id,
            deleted_at__isnull=True
        )
        if prediction_date:
            queryset = queryset.filter(prediction_date=prediction_date)
        return queryset.order_by('-created_at').first()

    def get_timers_for_product(
        self,
        danawa_product_id: str,
        days: int = 7
    ) -> List[TimerModel]:
        """Get timers for next N days."""
        today = timezone.now()
        end_date = today + timedelta(days=days)
        return list(
            TimerModel.objects.filter(
                danawa_product_id=danawa_product_id,
                prediction_date__gte=today,
                prediction_date__lte=end_date,
                deleted_at__isnull=True
            ).order_by('prediction_date')
        )

    def get_user_timers(
        self,
        user_id: int,
        is_notification_enabled: bool = None,
        offset: int = 0,
        limit: int = 20
    ) -> List[TimerModel]:
        """Get timers for a user."""
        queryset = TimerModel.objects.filter(
            user_id=user_id,
            deleted_at__isnull=True
        )
        if is_notification_enabled is not None:
            queryset = queryset.filter(is_notification_enabled=is_notification_enabled)
        return list(queryset.order_by('-created_at')[offset:offset + limit])

    @transaction.atomic
    def create_timer(
        self,
        danawa_product_id: str,
        user_id: int,
        target_price: int,
        prediction_date: datetime,
        model_version: str = 'v1.0'
    ) -> TimerModel:
        """Create a new price timer using AI."""
        # Get historical data
        history = self._get_price_history(danawa_product_id)

        # Calculate prediction
        predicted_price, confidence, suitability_score, guide_message = self._calculate_prediction(
            target_price,
            history,
            prediction_date
        )

        timer = TimerModel.objects.create(
            danawa_product_id=danawa_product_id,
            user_id=user_id,
            target_price=target_price,
            predicted_price=predicted_price,
            prediction_date=prediction_date,
            confidence_score=confidence,
            purchase_suitability_score=suitability_score,
            purchase_guide_message=guide_message,
            is_notification_enabled=True
        )

        logger.info(
            f"Created timer for product {danawa_product_id}: "
            f"{target_price} -> {predicted_price}"
        )
        return timer

    @transaction.atomic
    def update_timer(
        self,
        timer_id: int,
        target_price: int = None,
        is_notification_enabled: bool = None,
    ) -> TimerModel:
        """Update a timer."""
        timer = self.get_timer_by_id(timer_id)
        if not timer:
            raise PredictionNotFoundError(str(timer_id))

        if target_price is not None:
            timer.target_price = target_price
            
            # 목표가가 변경되면 구매 적합도 점수와 가이드 메시지 재계산
            if timer.predicted_price is not None:
                suitability_score, guide_message = self._calculate_suitability_and_message(
                    target_price,
                    timer.predicted_price
                )
                timer.purchase_suitability_score = suitability_score
                timer.purchase_guide_message = guide_message

        if is_notification_enabled is not None:
            timer.is_notification_enabled = is_notification_enabled

        timer.save()
        return timer

    @transaction.atomic
    def delete_timer(self, timer_id: int) -> bool:
        """Soft delete a timer."""
        timer = self.get_timer_by_id(timer_id)
        if not timer:
            return False

        timer.deleted_at = timezone.now()
        timer.is_notification_enabled = False
        timer.save()
        return True

    @transaction.atomic
    def record_price_history(
        self,
        danawa_product_id: str,
        lowest_price: int,
    ) -> PriceHistoryModel:
        """Record a price point for historical tracking."""
        return PriceHistoryModel.objects.create(
            danawa_product_id=danawa_product_id,
            lowest_price=lowest_price,
            recorded_at=timezone.now(),
        )

    def get_price_history(
        self,
        danawa_product_id: str,
        days: int = 30
    ) -> List[PriceHistoryModel]:
        """Get price history for a product."""
        start_date = timezone.now() - timedelta(days=days)
        return list(
            PriceHistoryModel.objects.filter(
                danawa_product_id=danawa_product_id,
                recorded_at__gte=start_date,
                deleted_at__isnull=True
            ).order_by('recorded_at')
        )

    def get_price_trend(
        self,
        danawa_product_id: str,
        days: int = 30
    ) -> dict:
        """Analyze price trend for a product."""
        start_date = timezone.now() - timedelta(days=days)
        history = PriceHistoryModel.objects.filter(
            danawa_product_id=danawa_product_id,
            recorded_at__gte=start_date,
            deleted_at__isnull=True
        ).order_by('recorded_at')

        if not history.exists():
            return {
                'trend': 'unknown',
                'change_percent': 0,
                'data_points': 0
            }

        prices = [h.lowest_price for h in history]
        first_price = prices[0]
        last_price = prices[-1]

        change_percent = ((last_price - first_price) / first_price) * 100 if first_price > 0 else 0

        if change_percent > 5:
            trend = 'increasing'
        elif change_percent < -5:
            trend = 'decreasing'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'change_percent': round(change_percent, 2),
            'data_points': len(prices),
            'min_price': min(prices),
            'max_price': max(prices),
            'avg_price': round(sum(prices) / len(prices), 2)
        }

    def _get_price_history(
        self,
        danawa_product_id: str,
        days: int = 30
    ) -> List[PriceHistoryModel]:
        """Get price history for prediction."""
        start_date = timezone.now() - timedelta(days=days)
        return list(
            PriceHistoryModel.objects.filter(
                danawa_product_id=danawa_product_id,
                recorded_at__gte=start_date,
                deleted_at__isnull=True
            ).order_by('recorded_at')
        )

    def _calculate_prediction(
        self,
        target_price: int,
        history: List[PriceHistoryModel],
        prediction_date: datetime
    ) -> tuple:
        """
        Calculate predicted price and purchase guidance using XGBoost.
        
        XGBoost를 활용한 기본적인 가격 예측 모델입니다.
        가격 이력 데이터를 특징으로 변환하여 예측합니다.
        """
        try:
            import xgboost as xgb
            import numpy as np
            import pandas as pd
        except ImportError:
            logger.warning("XGBoost not available, falling back to simple average")
            return self._simple_prediction_fallback(target_price, history, prediction_date)

        if not history or len(history) < 3:
            # 데이터가 부족한 경우 간단한 예측 사용
            return self._simple_prediction_fallback(target_price, history, prediction_date)

        try:
            # 가격 이력 데이터 준비
            prices = [h.lowest_price for h in history]
            dates = [h.recorded_at for h in history]
            
            # DataFrame 생성
            df = pd.DataFrame({
                'price': prices,
                'date': dates
            })
            df = df.sort_values('date')
            df['date'] = pd.to_datetime(df['date'])
            
            # 특징(feature) 생성
            features = []
            target = []
            
            # 시계열 윈도우 크기 (최근 7일 데이터 사용)
            window_size = min(7, len(df) - 1)
            
            for i in range(window_size, len(df)):
                window_prices = df['price'].iloc[i-window_size:i].values
                
                # 특징 추출
                feature_row = [
                    window_prices[-1],  # 최신 가격
                    np.mean(window_prices),  # 평균 가격
                    np.std(window_prices) if len(window_prices) > 1 else 0,  # 표준편차
                    window_prices[-1] - window_prices[0] if len(window_prices) > 1 else 0,  # 가격 변화
                    (window_prices[-1] - np.mean(window_prices)) / np.mean(window_prices) if np.mean(window_prices) > 0 else 0,  # 평균 대비 편차율
                    df['date'].iloc[i].dayofweek,  # 요일
                    df['date'].iloc[i].day,  # 일
                ]
                
                features.append(feature_row)
                target.append(df['price'].iloc[i])
            
            if len(features) < 2:
                return self._simple_prediction_fallback(target_price, history, prediction_date)
            
            # XGBoost 모델 학습
            X = np.array(features)
            y = np.array(target)
            
            model = xgb.XGBRegressor(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.1,
                random_state=42,
                objective='reg:squarederror'
            )
            model.fit(X, y)
            
            # 예측을 위한 최신 특징 생성
            recent_prices = df['price'].iloc[-window_size:].values
            days_ahead = (prediction_date.date() - timezone.now().date()).days
            days_ahead = max(1, min(days_ahead, 30))  # 1~30일 범위로 제한
            
            prediction_feature = [
                recent_prices[-1],  # 최신 가격
                np.mean(recent_prices),  # 평균 가격
                np.std(recent_prices) if len(recent_prices) > 1 else 0,  # 표준편차
                recent_prices[-1] - recent_prices[0] if len(recent_prices) > 1 else 0,  # 가격 변화
                (recent_prices[-1] - np.mean(recent_prices)) / np.mean(recent_prices) if np.mean(recent_prices) > 0 else 0,  # 평균 대비 편차율
                prediction_date.weekday(),  # 예측일 요일
                prediction_date.day,  # 예측일 일
            ]
            
            # 예측 수행
            predicted_price = model.predict(np.array([prediction_feature]))[0]
            predicted_price = max(0, int(predicted_price))  # 음수 방지
            
            # 시간이 지날수록 신뢰도 감소
            confidence = max(0.5, 0.95 - (days_ahead * 0.02))
            
            # 구매 적합도 점수 및 메시지 계산 (공통 로직 사용)
            suitability_score, guide_message = self._calculate_suitability_and_message(
                target_price, predicted_price
            )
            
            logger.info(
                f"XGBoost prediction: target={target_price}, predicted={predicted_price}, "
                f"confidence={confidence:.2f}, suitability={suitability_score}"
            )
            
            return predicted_price, confidence, suitability_score, guide_message
            
        except Exception as e:
            logger.error(f"XGBoost prediction failed: {str(e)}", exc_info=True)
            # XGBoost 예측 실패 시 폴백 사용
            return self._simple_prediction_fallback(target_price, history, prediction_date)
    
    def _simple_prediction_fallback(
        self,
        target_price: int,
        history: List[PriceHistoryModel],
        prediction_date: datetime
    ) -> tuple:
        """
        간단한 이동 평균 기반 예측 (폴백)
        """
        if not history:
            return target_price, 0.5, 50, "가격 이력이 부족합니다. 더 많은 데이터가 필요합니다."

        prices = [h.lowest_price for h in history[-7:]] if len(history) >= 7 else [h.lowest_price for h in history]
        avg_price = sum(prices) / len(prices)

        # Simple trend calculation
        if len(prices) >= 3:
            recent_avg = sum(prices[-3:]) / 3
            older_avg = sum(prices[:3]) / 3 if len(prices) >= 6 else prices[0]
            trend_factor = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
        else:
            trend_factor = 0

        # Days until prediction
        days_ahead = (prediction_date.date() - timezone.now().date()).days
        days_ahead = max(0, days_ahead)  # 음수 방지
        predicted = int(avg_price * (1 + trend_factor * days_ahead * 0.1))

        # Confidence decreases with time
        confidence = max(0.5, 0.95 - (days_ahead * 0.05))
        confidence = min(1.0, confidence)  # 최대 1.0 제한

        # 구매 적합도 점수 및 메시지 계산 (공통 로직 사용)
        suitability_score, guide_message = self._calculate_suitability_and_message(
            target_price, predicted
        )

        return predicted, confidence, suitability_score, guide_message

    def _calculate_suitability_and_message(self, target_price: int, predicted_price: int) -> tuple[int, str]:
        """구매 적합도 점수와 가이드 메시지를 계산합니다."""
        if predicted_price <= target_price:
            price_diff = target_price - predicted_price
            discount_rate = (price_diff / target_price * 100) if target_price > 0 else 0
            suitability_score = min(100, int(75 + discount_rate * 0.5))
            
            if discount_rate > 10:
                guide_message = "현재 역대 최저가에 근접한 저점 구간입니다. 구매를 강력 추천합니다."
            elif discount_rate > 5:
                guide_message = "예측 가격이 목표가보다 낮습니다. 구매를 권장합니다."
            else:
                guide_message = "예측 가격이 목표가와 유사합니다. 구매를 고려해볼 수 있습니다."
        else:
            price_diff = predicted_price - target_price
            premium_rate = (price_diff / target_price * 100) if target_price > 0 else 0
            suitability_score = max(0, int(50 - premium_rate * 0.5))
            
            if premium_rate > 10:
                guide_message = "예측 가격이 목표가보다 높습니다. 좀 더 기다려보세요."
            else:
                guide_message = "예측 가격이 목표가보다 약간 높습니다. 관찰을 권장합니다."
        
        return suitability_score, guide_message


class PriceHistoryService:
    """Service for price history operations."""

    def get_history_by_product(
        self,
        danawa_product_id: str,
        days: int = 30
    ) -> List[PriceHistoryModel]:
        """Get price history for a product."""
        start_date = timezone.now() - timedelta(days=days)
        return list(
            PriceHistoryModel.objects.filter(
                danawa_product_id=danawa_product_id,
                recorded_at__gte=start_date,
                deleted_at__isnull=True
            ).order_by('-recorded_at')
        )

    @transaction.atomic
    def create_history(
        self,
        danawa_product_id: str,
        lowest_price: int,
    ) -> PriceHistoryModel:
        """Create a new price history record."""
        return PriceHistoryModel.objects.create(
            danawa_product_id=danawa_product_id,
            lowest_price=lowest_price,
            recorded_at=timezone.now(),
        )

    @transaction.atomic
    def delete_history(self, history_id: int) -> bool:
        """Soft delete a price history record."""
        try:
            history = PriceHistoryModel.objects.get(
                id=history_id,
                deleted_at__isnull=True
            )
            history.deleted_at = timezone.now()
            history.save()
            return True
        except PriceHistoryModel.DoesNotExist:
            return False
