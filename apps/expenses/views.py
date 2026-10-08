from rest_framework import viewsets

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        # drf-spectacular calls this without a real user to build the API docs.
        if getattr(self, "swagger_fake_view", False):
            return Category.objects.none()
        return self.request.user.categories.all()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
