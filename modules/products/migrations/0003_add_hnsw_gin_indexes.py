# Generated manually for adding HNSW and GIN indexes

from django.db import migrations
from django.contrib.postgres.operations import TrigramExtension


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_add_review_fields"),
    ]

    operations = [
        # pg_trgm 확장 활성화 (GIN trigram 인덱스용)
        TrigramExtension(),

        # HNSW 인덱스 추가 (벡터 유사도 검색 최적화)
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS products_detail_spec_vector_hnsw_idx
                ON products USING hnsw (detail_spec_vector vector_l2_ops)
                WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="DROP INDEX IF EXISTS products_detail_spec_vector_hnsw_idx;",
        ),

        # GIN 인덱스 추가 (상품명 텍스트 검색 최적화)
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS products_name_gin_idx
                ON products USING gin (name gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS products_name_gin_idx;",
        ),
    ]
