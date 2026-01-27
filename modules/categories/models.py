"""
Categories models based on ERD.
"""
from django.db import models


class CategoryModel(models.Model):
    """Product category model with hierarchical structure."""

    name = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name='카테고리명'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='부모카테고리',
        help_text='자기참조'
    )
    level = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        verbose_name='카테고리 레벨',
        help_text='0=대분류, 1=중분류, 2=소분류, 3=세분류'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='생성시각'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='수정시각'
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='논리적삭제플래그'
    )

    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    @property
    def is_deleted(self) -> bool:
        """Check if category is soft deleted."""
        return self.deleted_at is not None

    @property
    def full_path(self) -> str:
        """Get full category path."""
        path_parts = [self.name]
        parent = self.parent
        while parent:
            path_parts.insert(0, parent.name)
            parent = parent.parent
        return ' > '.join(path_parts)

    def _calculate_level(self) -> int:
        """Calculate category depth level by traversing parents."""
        level = 0
        parent = self.parent
        while parent:
            level += 1
            parent = parent.parent
        return level

    def save(self, *args, **kwargs):
        """Override save to auto-calculate level."""
        self.level = self._calculate_level()
        super().save(*args, **kwargs)
