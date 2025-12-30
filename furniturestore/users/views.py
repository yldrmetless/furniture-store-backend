from django.contrib.auth import get_user_model, authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth.password_validation import validate_password
from rest_framework.generics import ListAPIView
from users.serializers import UserListSerializer
from django.core.exceptions import ValidationError


User = get_user_model()


class RegisterAPIView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        email = request.data.get("email")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"message": "Kullanıcı adı ve şifre zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"message": "Bu kullanıcı adı zaten kullanılıyor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            username=username,
            email=email or "",
            password=password,
        )

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )
    


class LoginAPIView(APIView):
    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"status": 404, "message": "Kullanıcı adı ve şifre zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"status": 404, "message": "Kullanıcı adı veya şifre hatalı."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"status": 404, "nessage": "Kullanıcı aktif değil."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        minutes = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds() // 60)

        return Response(
            {
                "access": str(access),
                "refresh": str(refresh),
                "expires_time": minutes,
            },
            status=status.HTTP_200_OK,
        )
    


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        new_password2 = request.data.get("new_password2")

        email = request.data.get("email")
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")

        if not old_password or not new_password or not new_password2:
            return Response(
                {
                    "status": 400 ,"message": "Eski şifre, yeni şifre ve şifre tekrarla alanları zorunludur."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != new_password2:
            return Response(
                {"status": 400, "message": "Yeni şifreler eşleşmiyor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        if not user.check_password(old_password):
            return Response(
                {"status": 400, "message": "Eski şifre hatalı."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            return Response(
                {"status": 400, "message": e.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)

        if email is not None:
            user.email = email.strip()

        if first_name is not None:
            user.first_name = first_name.strip()

        if last_name is not None:
            user.last_name = last_name.strip()

        user.save(update_fields=["password", "email", "first_name", "last_name"])

        return Response(
            {
                "status": 200,
                "message": "Şifre ve kullanıcı bilgileri başarıyla güncellendi.",
            },
            status=status.HTTP_200_OK,
        )
    

class UserListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserListSerializer
    queryset = User.objects.all().order_by("-id")