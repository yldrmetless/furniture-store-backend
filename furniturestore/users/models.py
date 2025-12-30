from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class Users(AbstractUser):
    user_type = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )