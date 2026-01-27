"""
Orders module service layer.
"""
from datetime import datetime
from typing import Optional, List

from django.db import transaction

from .models import (
    CartModel,
    CartItemModel,
    OrderModel,
    OrderItemModel,
    OrderHistoryModel,
    ReviewModel,
)
from .exceptions import (
    OrderNotFoundError,
    CartNotFoundError,
    EmptyCartError,
    InvalidRechargeAmountError,
    InsufficientTokenBalanceError,
)


class CartService:
    """
    Cart (장바구니) business logic service.
    """

    def get_or_create_cart(self, user_id: int) -> CartModel:
        """Get or create cart for a user."""
        cart, created = CartModel.objects.get_or_create(
            user_id=user_id,
            deleted_at__isnull=True
        )
        return cart

    def get_cart_items(self, cart_id: int) -> List[CartItemModel]:
        """Get all items in a cart."""
        return list(
            CartItemModel.objects.filter(
                cart_id=cart_id,
                deleted_at__isnull=True
            ).select_related('product').prefetch_related('product__mall_information')
        )

    def add_item(
        self,
        cart_id: int,
        danawa_product_id: str,
        quantity: int = 1,
    ) -> CartItemModel:
        """Add item to cart."""
        cart_item, created = CartItemModel.objects.get_or_create(
            cart_id=cart_id,
            product_id=danawa_product_id,
            deleted_at__isnull=True,
            defaults={'quantity': quantity}
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.save()

        return cart_item

    def update_item_quantity(
        self,
        cart_id: int,
        cart_item_id: int,
        quantity: int,
    ) -> Optional[CartItemModel]:
        """장바구니 수량을  cart_item_id 기반으로 업데이트함"""
        try:
            cart_item = CartItemModel.objects.get(
                cart_id=cart_id,
                id=cart_item_id,
                deleted_at__isnull=True
            )
            if quantity <= 0:
                cart_item.deleted_at = datetime.now()
                cart_item.save()
                return None
            else:
                cart_item.quantity = quantity
                cart_item.save()
                return cart_item
        except CartItemModel.DoesNotExist:
            raise CartNotFoundError(f"Cart {cart_id}")

    def remove_item(self, cart_id: int, cart_item_id: int) -> bool:
        """Remove item from cart (soft delete)."""
        try:
            cart_item = CartItemModel.objects.get(
                id=cart_item_id, # Lookup by cart_item_id
                cart_id=cart_id, # Ensure the item belongs to the user's cart
                deleted_at__isnull=True
            ) 
            cart_item.deleted_at = datetime.now()
            cart_item.save()
            return True
        except CartItemModel.DoesNotExist:
            return False

    def clear_cart(self, cart_id: int) -> bool:
        """Clear all items from cart (soft delete)."""
        CartItemModel.objects.filter(
            cart_id=cart_id,
            deleted_at__isnull=True
        ).update(deleted_at=datetime.now())
        return True


class OrderService:
    """
    Order business logic service.
    """

    def __init__(self):
        self.cart_service = CartService()

    def get_order_by_id(self, order_id: int) -> Optional[OrderModel]:
        """Get order by ID."""
        try:
            return OrderModel.objects.prefetch_related('items').get(
                id=order_id,
                deleted_at__isnull=True
            )
        except OrderModel.DoesNotExist:
            return None

    def get_user_orders(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> List[OrderModel]:
        """Get all orders for a user."""
        return list(
            OrderModel.objects.filter(user_id=user_id, deleted_at__isnull=True)
            .prefetch_related('items')
            .order_by('-created_at')[offset:offset + limit]
        )

    @transaction.atomic
    def create_order_from_cart(self, user_id: int) -> OrderModel:
        """Create order from user's cart items."""
        cart = self.cart_service.get_or_create_cart(user_id)
        cart_items = self.cart_service.get_cart_items(cart.id)
        if not cart_items:
            raise EmptyCartError()

        # Create order
        order = OrderModel.objects.create(user_id=user_id)

        # Create order items from cart items
        for cart_item in cart_items:
            # Use the product's danawa_product_id
            danawa_product_id = cart_item.product.danawa_product_id if cart_item.product else ''
            OrderItemModel.objects.create(
                order=order,
                danawa_product_id=danawa_product_id,
                quantity=cart_item.quantity,
            )

        # Clear the cart
        self.cart_service.clear_cart(cart.id)

        return order


class OrderHistoryService:
    """
    Order history business logic service.
    """

    def __init__(self):
        self.cart_service = CartService()

    def get_user_order_histories(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> List[OrderHistoryModel]:
        """Get order histories for a user."""
        return list(
            OrderHistoryModel.objects.filter(user_id=user_id, deleted_at__isnull=True)
            .order_by('-transaction_at')[offset:offset + limit]
        )

    def create_order_history(
        self,
        user_id: int,
        transaction_type: str,
        token_change: int,
        token_balance_after: int,
        danawa_product_id: str,
    ) -> OrderHistoryModel:
        """Create an order history record."""
        return OrderHistoryModel.objects.create(
            user_id=user_id,
            transaction_type=transaction_type,
            token_change=token_change,
            token_balance_after=token_balance_after,
            transaction_at=datetime.now(),
            danawa_product_id=danawa_product_id,
        )

    @transaction.atomic
    def recharge_token(self, user_id: int, recharge_amount: int) -> int:
        """
        토큰 충전 로직
        """
        MINIMUM_RECHARGE_AMOUNT = 1000
        
        if recharge_amount < MINIMUM_RECHARGE_AMOUNT:
            raise InvalidRechargeAmountError(MINIMUM_RECHARGE_AMOUNT)
        
        from modules.users.models import UserModel
        
        user = UserModel.objects.get(id=user_id, deleted_at__isnull=True)
        user.token_balance = (user.token_balance or 0) + recharge_amount
        user.save()
        
        return user.token_balance

    @transaction.atomic
    def purchase_with_tokens(
        self,
        user_id: int,
        product_code: str,
        quantity: int,
        total_price: int,
    ) -> tuple[OrderModel, int, 'ProductModel']:
        """
        Purchase product using tokens.
        
        Args:
            user_id: User ID
            product_code: Product code (danawa_product_id)
            quantity: Quantity to purchase
            total_price: Total price in tokens
            
        Returns:
            Tuple of (OrderModel, new_token_balance)
            
        Raises:
            InsufficientTokenBalanceError: If user doesn't have enough tokens
        """
        from modules.users.models import UserModel
        from modules.products.models import ProductModel
        
        # Get user and check token balance
        try:
            user = UserModel.objects.get(id=user_id, deleted_at__isnull=True)
        except UserModel.DoesNotExist:
            raise OrderNotFoundError(f"User {user_id}")
        
        current_balance = user.token_balance or 0
        if current_balance < total_price:
            raise InsufficientTokenBalanceError(required=total_price, available=current_balance)
        
        # Get product
        try:
            product = ProductModel.objects.get(danawa_product_id=product_code, deleted_at__isnull=True)
        except ProductModel.DoesNotExist:
            raise OrderNotFoundError(f"Product {product_code}")
        
        # Deduct tokens
        new_balance = current_balance - total_price
        user.token_balance = new_balance
        user.save()
        
        # Create order
        order = OrderModel.objects.create(user_id=user_id)
        
        # Create order item
        OrderItemModel.objects.create(
            order=order,
            danawa_product_id=product.danawa_product_id,
            quantity=quantity,
        )
        
        # Create order history (payment transaction)
        self.create_order_history(
            user_id=user_id,
            transaction_type='payment',
            token_change=-total_price,  # Negative for payment
            token_balance_after=new_balance,
            danawa_product_id=product.danawa_product_id,
        )
        
        return order, new_balance, product

    @transaction.atomic
    def purchase_cart_items_with_tokens(
        self,
        user_id: int,
        cart_item_ids_with_quantities: List[dict],
        total_price: int,
    ) -> tuple[OrderModel, int, List[CartItemModel]]:
        """
        Purchase cart items using tokens.
        
        Args:
            user_id: User ID
            cart_item_ids_with_quantities: List of dicts with {'cart_item_id': int, 'quantity': int}
            total_price: Total price in tokens
            
        Returns:
            Tuple of (OrderModel, new_token_balance, List[CartItemModel])
            
        Raises:
            InsufficientTokenBalanceError: If user doesn't have enough tokens
            OrderNotFoundError: If cart item or product not found
        """
        from modules.users.models import UserModel
        
        # Get user and check token balance
        try:
            user = UserModel.objects.get(id=user_id, deleted_at__isnull=True)
        except UserModel.DoesNotExist:
            raise OrderNotFoundError(f"User {user_id}")
        
        current_balance = user.token_balance or 0
        if current_balance < total_price:
            raise InsufficientTokenBalanceError(required=total_price, available=current_balance)
        
        # Get cart
        cart = self.cart_service.get_or_create_cart(user_id)
        
        # Get cart items
        cart_items = []
        for item_data in cart_item_ids_with_quantities:
            cart_item_id = item_data['cart_item_id']
            quantity = item_data['quantity']
            
            try:
                cart_item = CartItemModel.objects.select_related('product').get(
                    id=cart_item_id,
                    cart_id=cart.id,
                    deleted_at__isnull=True
                )
                cart_items.append(cart_item)
            except CartItemModel.DoesNotExist:
                raise OrderNotFoundError(f"Cart item {cart_item_id}")
        
        if not cart_items:
            raise OrderNotFoundError("No cart items found")
        
        # Deduct tokens
        new_balance = current_balance - total_price
        user.token_balance = new_balance
        user.save()
        
        # Create order
        order = OrderModel.objects.create(user_id=user_id)
        
        # Create order items from cart items
        first_product_id = None
        for item_data in cart_item_ids_with_quantities:
            cart_item_id = item_data['cart_item_id']
            quantity = item_data['quantity']
            
            cart_item = next((ci for ci in cart_items if ci.id == cart_item_id), None)
            if not cart_item:
                raise OrderNotFoundError(f"Cart item {cart_item_id} not found in cart")
            
            if not cart_item.product:
                raise OrderNotFoundError(f"Product not found for cart item {cart_item_id}")
            
            if first_product_id is None:
                first_product_id = cart_item.product.danawa_product_id
            
            OrderItemModel.objects.create(
                order=order,
                danawa_product_id=cart_item.product.danawa_product_id,
                quantity=quantity,
            )
            
            # Remove cart item (soft delete)
            cart_item.deleted_at = datetime.now()
            cart_item.save()
        
        # Create order history (payment transaction) - only once for total
        if not first_product_id:
            raise OrderNotFoundError("No valid products found in cart items")
        
        self.create_order_history(
            user_id=user_id,
            transaction_type='payment',
            token_change=-total_price,
            token_balance_after=new_balance,
            danawa_product_id=first_product_id,
        )
        
        return order, new_balance, cart_items


class ReviewService:
    """
    Review business logic service.
    """

    def get_product_reviews(
        self,
        danawa_product_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> List[ReviewModel]:
        """Get reviews for a product."""
        return list(
            ReviewModel.objects.filter(
                danawa_product_id=danawa_product_id,
                deleted_at__isnull=True
            ).order_by('-created_at')[offset:offset + limit]
        )

    def get_user_reviews(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20,
    ) -> List[ReviewModel]:
        """Get reviews by a user."""
        return list(
            ReviewModel.objects.filter(user_id=user_id, deleted_at__isnull=True)
            .order_by('-created_at')[offset:offset + limit]
        )

    def create_review(
        self,
        danawa_product_id: str,
        user_id: int,
        content: str = None,
        rating: int = None,
        mall_name: str = None,
        reviewer_name: str = None,
    ) -> ReviewModel:
        """Create a review."""
        return ReviewModel.objects.create(
            danawa_product_id=danawa_product_id,
            user_id=user_id,
            content=content,
            rating=rating,
            mall_name=mall_name,
            reviewer_name=reviewer_name,
        )
