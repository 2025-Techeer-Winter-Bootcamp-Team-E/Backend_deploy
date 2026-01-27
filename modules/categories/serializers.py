"""
Categories serializers.
"""
from rest_framework import serializers

from .models import CategoryModel


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for categories."""

    parent_name = serializers.CharField(
        source='parent.name',
        read_only=True,
        allow_null=True
    )
    full_path = serializers.CharField(read_only=True)
    level = serializers.IntegerField(read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = CategoryModel
        fields = [
            'id',
            'name',
            'parent',
            'parent_name',
            'full_path',
            'level',
            'children_count',
            'created_at',
            'updated_at',
            'deleted_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_children_count(self, obj):
        """Get number of direct children."""
        return obj.children.filter(deleted_at__isnull=True).count()


class CategoryCreateSerializer(serializers.Serializer):
    """Serializer for creating category."""

    name = serializers.CharField(max_length=50)
    parent_id = serializers.IntegerField(required=False, allow_null=True)


class CategoryUpdateSerializer(serializers.Serializer):
    """Serializer for updating category."""

    name = serializers.CharField(max_length=50, required=False)
    parent_id = serializers.IntegerField(required=False, allow_null=True)


class CategoryTreeSerializer(serializers.Serializer):
    """Serializer for category tree structure."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    level = serializers.IntegerField()
    children = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class CategoryBreadcrumbSerializer(serializers.Serializer):
    """Serializer for category breadcrumbs."""

    id = serializers.IntegerField()
    name = serializers.CharField()
