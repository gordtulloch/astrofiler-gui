"""Peewee migrations -- 012_add_variable_stars_table.py."""

import datetime as dt

import peewee as pw


def migrate(migrator, database, fake=False, **kwargs):
    @migrator.create_model
    class VariableStars(pw.Model):
        id = pw.AutoField()
        target_name = pw.TextField(unique=True)
        created_at = pw.DateTimeField(default=dt.datetime.now)

        class Meta:
            table_name = "VariableStars"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model("VariableStars")
