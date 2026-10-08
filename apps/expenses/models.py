from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Category(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "user",
                name="unique_category_name_per_user",
            ),
        ]

    def __str__(self):
        return self.name
