# Generated manually for changing CartItemModel FK to danawa_product_id

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_alter_orderhistorymodel_options_and_more"),
        ("products", "0004_add_product_ai_review_analysis"),
    ]

    operations = [
        # 1. 기존 FK 제약 조건 삭제
        migrations.RunSQL(
            sql="ALTER TABLE cart_items DROP CONSTRAINT IF EXISTS cart_items_product_id_d6dd8e2a_fk_products_id;",
            reverse_sql="ALTER TABLE cart_items ADD CONSTRAINT cart_items_product_id_d6dd8e2a_fk_products_id FOREIGN KEY (product_id) REFERENCES products(id) DEFERRABLE INITIALLY DEFERRED;",
        ),

        # 2. danawa_product_id 컬럼 추가
        migrations.RunSQL(
            sql="ALTER TABLE cart_items ADD COLUMN danawa_product_id VARCHAR(15);",
            reverse_sql="ALTER TABLE cart_items DROP COLUMN IF EXISTS danawa_product_id;",
        ),

        # 3. 기존 product_id를 danawa_product_id로 변환
        migrations.RunSQL(
            sql="""
                UPDATE cart_items ci
                SET danawa_product_id = p.danawa_product_id
                FROM products p
                WHERE ci.product_id = p.id;
            """,
            reverse_sql="""
                UPDATE cart_items ci
                SET product_id = p.id
                FROM products p
                WHERE ci.danawa_product_id = p.danawa_product_id;
            """,
        ),

        # 4. 기존 product_id 컬럼 삭제
        migrations.RunSQL(
            sql="ALTER TABLE cart_items DROP COLUMN product_id;",
            reverse_sql="ALTER TABLE cart_items ADD COLUMN product_id BIGINT;",
        ),

        # 5. danawa_product_id NOT NULL 제약 추가
        migrations.RunSQL(
            sql="ALTER TABLE cart_items ALTER COLUMN danawa_product_id SET NOT NULL;",
            reverse_sql="ALTER TABLE cart_items ALTER COLUMN danawa_product_id DROP NOT NULL;",
        ),

        # 6. 새로운 FK 제약 조건 추가
        migrations.RunSQL(
            sql="""
                ALTER TABLE cart_items
                ADD CONSTRAINT cart_items_danawa_product_id_fk
                FOREIGN KEY (danawa_product_id)
                REFERENCES products(danawa_product_id)
                ON DELETE CASCADE
                DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="ALTER TABLE cart_items DROP CONSTRAINT IF EXISTS cart_items_danawa_product_id_fk;",
        ),

        # 7. 인덱스 추가
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS cart_items_danawa_product_id_idx ON cart_items(danawa_product_id);",
            reverse_sql="DROP INDEX IF EXISTS cart_items_danawa_product_id_idx;",
        ),
    ]
